/**
 * Escaneo DOM — ciclo de apuesta mesa (cuenta regresiva → apuesta → cierre → fin bono).
 * Mismo patrón que jokerbets-bono-dom-scan.js: 3 Chrome, Enter por fase, registro JSONL.
 *
 * Uso: jokerbets/APUESTA_MESA_PASOS.txt
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { chromium } = require('playwright');
const dom = require('./jokerbets-dom.js');

const DIR = __dirname;
const CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const OUT_DIR = path.join(DIR, 'apuesta-scan');
const REGISTRO_JSONL = path.join(OUT_DIR, 'REGISTRO_APUESTA.jsonl');

const FASES = [
  {
    id: 'cuenta_regresiva',
    prompt:
      '>>> Enter con cuenta regresiva visible (HAGAN JUEGO / timer ~12s, barra ABIERTA)... ',
    hint: 'Justo cuando puedes apostar, antes de clicar centro.',
  },
  {
    id: 'apuesta_hecha',
    prompt:
      '>>> Enter DESPUÉS de apostar a mano (centro / $50 en los 4 bonos)... ',
    hint: 'Tras tu apuesta; ideal esperar 1–2 s para que actualice la barra.',
  },
  {
    id: 'mesa_cerrada',
    prompt:
      '>>> Enter con mesa CERRADA (ESPERE SIGUIENTE RONDA o sin poder sumar apuesta)... ',
    hint: 'Pasados ~12s o ruleta girando; fichas congeladas.',
  },
  {
    id: 'fin_bono',
    prompt:
      '>>> Enter al terminar el bono (o Enter vacío si esta ronda no hubo bono)... ',
    hint: 'Vuelve mesa normal / resultado; si no hubo bono, Enter igual cierra la captura.',
  },
];

function leerCuentas() {
  const raw = fs.readFileSync(CONFIG_FILE, 'utf-8').replace(/^\uFEFF/, '');
  const cfg = JSON.parse(raw);
  const nb = (cfg.notebooks || []).find(n => n.id === cfg.activeNotebookId) || cfg.notebooks?.[0];
  return nb?.cuentas || [];
}

function chromePath() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ].filter(Boolean);
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return undefined;
}

function limpiarLocks(perfil) {
  for (const name of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
    try {
      fs.unlinkSync(path.join(perfil, name));
    } catch (_) {}
  }
}

function esperarEnter(msg) {
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(msg, () => {
      rl.close();
      resolve();
    });
  });
}

async function escanearMesaEnFrame(frame, cuenta, faseId) {
  let mesa = { ok: false, why: 'sin-frame' };
  let espera = false;
  let decision = false;
  try {
    mesa = await dom.mesaListaParaApostar(frame);
  } catch (_) {}
  try {
    espera = await dom.esperaSiguienteRonda(frame);
  } catch (_) {}
  try {
    decision = await dom.pantallaDecision(frame);
  } catch (_) {}

  let chip = null;
  try {
    chip = await dom.chipSeleccionado(frame);
  } catch (_) {}

  const domSnap = await frame
    .evaluate(() => {
      const txt = (document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 2500);
      const txtL = txt.toLowerCase();
      const pickCountdown = () => {
        const m1 = txt.match(/hagan\s+juego[\s\S]{0,40}?(\d{1,2})\b/i);
        if (m1) return { src: 'near-hagan', n: Number(m1[1]) };
        const nodes = Array.from(document.querySelectorAll('[class*="timer" i], [class*="countdown" i], [class*="Timer"]'));
        for (const el of nodes) {
          const t = (el.textContent || '').trim();
          const m = /^(\d{1,2})$/.exec(t);
          if (m) return { src: 'timer-node', n: Number(m[1]), cls: (el.className || '').toString().slice(0, 80) };
        }
        return null;
      };
      const spots = [];
      for (const el of document.querySelectorAll('[data-bet-selector]')) {
        const sel = el.getAttribute('data-bet-selector') || '';
        const cls = (el.className || '').toString();
        const r = el.getBoundingClientRect();
        const disabled = /disabled/i.test(cls);
        const childTxt = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
        spots.push({
          selector: sel,
          disabled,
          cls: cls.slice(0, 100),
          w: Math.round(r.width),
          h: Math.round(r.height),
          snippet: childTxt,
        });
      }
      const center = document.querySelector('[data-bet-selector="bonusType"]');
      const videos = Array.from(document.querySelectorAll('video')).map(v => ({
        paused: v.paused,
        readyState: v.readyState,
        w: v.videoWidth,
        h: v.videoHeight,
      }));
      const saldoM = txt.match(/SALDO\s*\$?\s*([\d.,]+)\s*(K|M)?/i);
      const apuestaM = txt.match(/Apuesta\s*\$?\s*([\d.,]+)\s*(K|M)?/i);
      const premioM = txt.match(/Premio\s*\$?\s*([\d.,]+)\s*(K|M)?/i);

      return {
        url: location.href.slice(0, 220),
        faseJuego: {
          haganJuego: /hagan\s+juego|place your bets/i.test(txtL),
          espereSiguiente: /espere[\s\S]{0,20}siguiente|wait[\s\S]{0,12}next/i.test(txtL),
          tomaDecision: /toma tu decisi|make your decision/i.test(txtL),
        },
        countdown: pickCountdown(),
        barraEnTexto: {
          saldo: saldoM ? saldoM[0] : null,
          apuesta: apuestaM ? apuestaM[0] : null,
          premio: premioM ? premioM[0] : null,
        },
        panelBonusOculto: document
          .getElementById('game-panel')
          ?.classList.contains('game-panel-desktop_hidden'),
        spots,
        nSpots: spots.length,
        centroDisabled: center ? /disabled/i.test((center.className || '').toString()) : null,
        videos,
        snippet: txt.slice(0, 500),
      };
    })
    .catch(e => ({ error: String(e.message || e).slice(0, 120) }));

  return {
    cuenta: cuenta.color,
    id: cuenta.id,
    fase: faseId,
    mesaBot: mesa,
    esperaSiguienteRonda: espera,
    pantallaDecision: decision,
    chipSeleccionado: chip,
    dom: domSnap,
  };
}

async function escanearPagina(page, cuenta, faseId, stamp) {
  const frame = await dom.findGameFrame(page);
  const suf = `${cuenta.color}-${faseId}-${stamp}`;
  const mainShot = path.join(OUT_DIR, `${suf}-pagina.png`);
  try {
    await page.screenshot({ path: mainShot, fullPage: false });
  } catch (_) {}

  let barraPage = null;
  try {
    barraPage = await dom.readBarraSaldoFromPage(page);
  } catch (_) {}

  const informes = [];
  if (frame) {
    informes.push(await escanearMesaEnFrame(frame, cuenta, faseId));
    try {
      await frame.locator('body').first().screenshot({
        path: path.join(OUT_DIR, `${suf}-iframe.png`),
      });
    } catch (_) {}
  } else {
    informes.push({
      cuenta: cuenta.color,
      id: cuenta.id,
      fase: faseId,
      error: 'sin iframe juego (findGameFrame null)',
    });
  }

  return {
    cuentaId: cuenta.id,
    cuentaColor: cuenta.color,
    url: cuenta.url,
    fase: faseId,
    mainShot,
    barraPage,
    informes,
  };
}

async function escanearTodos(contexts, faseId, stamp) {
  const out = [];
  for (const { cuenta, ctx } of contexts) {
    const page = ctx.pages().find(p => !p.isClosed()) || null;
    if (!page) {
      out.push({ cuentaId: cuenta.id, cuentaColor: cuenta.color, fase: faseId, error: 'sin pestaña' });
      continue;
    }
    out.push(await escanearPagina(page, cuenta, faseId, stamp));
  }
  return out;
}

function appendRegistro(entry) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.appendFileSync(REGISTRO_JSONL, JSON.stringify(entry) + '\n', 'utf-8');
}

function resumenFase(capturas) {
  const lineas = [];
  for (const c of capturas) {
    const inf = c.informes?.[0];
    const d = inf?.dom || {};
    const m = inf?.mesaBot || {};
    lineas.push(
      [
        c.cuentaColor,
        'mesa=' + (m.ok ? 'lista' : 'no:' + (m.why || '?')),
        d.faseJuego?.haganJuego ? 'HAGAN' : '',
        d.faseJuego?.espereSiguiente ? 'ESPERE' : '',
        d.countdown ? 'cd=' + d.countdown.n : '',
        'APUESTA=' + (c.barraPage?.apuesta ?? d.barraEnTexto?.apuesta ?? '?'),
        'centroDis=' + (d.centroDisabled === true ? '1' : d.centroDisabled === false ? '0' : '?'),
      ]
        .filter(Boolean)
        .join(' · ')
    );
  }
  return lineas.join('\n');
}

async function main() {
  const etiqueta = (process.argv[2] || 'mesa').toLowerCase();
  const cuentas = leerCuentas();
  if (cuentas.length < 1) {
    console.error('Sin cuentas en config.json');
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportPath = path.join(OUT_DIR, `REPORTE-${etiqueta}-${stamp}.txt`);

  console.log('');
  console.log('=== Escaneo apuesta mesa · etiqueta:', etiqueta, '===');
  console.log('Cierra antes los 3 Chrome de Cuentas (Detener), si no Chrome bloquea el perfil.');
  console.log('');

  const contexts = [];
  const capturasPorFase = {};

  try {
    for (const c of cuentas) {
      const perfil = path.join(DIR, 'perfiles', c.id);
      fs.mkdirSync(perfil, { recursive: true });
      limpiarLocks(perfil);
      const ctx = await chromium.launchPersistentContext(perfil, {
        headless: false,
        executablePath: chromePath(),
        args: ['--start-maximized', '--disable-blink-features=AutomationControlled'],
        viewport: null,
      });
      contexts.push({ cuenta: c, ctx });
      let page = ctx.pages()[0] || (await ctx.newPage());
      if (c.url) {
        console.log('Abriendo', c.color, '→', c.url.slice(0, 70));
        try {
          await page.goto(c.url, { waitUntil: 'domcontentloaded', timeout: 90000 });
        } catch (e) {
          console.log('  (goto:', String(e.message || e).slice(0, 60), ')');
        }
      }
    }

    console.log('');
    console.log('============================================================');
    console.log('LISTO. Mira ESTA ventana (PowerShell), no solo los Chrome.');
    console.log('4 Enter — una fase cada uno (rojo / azul / verde en paralelo).');
    console.log('============================================================');
    for (let i = 0; i < FASES.length; i += 1) {
      const f = FASES[i];
      console.log(String(i + 1) + ') ' + f.id + ' — ' + f.hint);
    }
    console.log('');

    for (const fase of FASES) {
      await esperarEnter(fase.prompt);
      const ts = new Date().toISOString();
      const cap = await escanearTodos(contexts, fase.id, stamp);
      capturasPorFase[fase.id] = cap;
      console.log('');
      console.log('--- ' + fase.id + ' @ ' + ts + ' ---');
      console.log(resumenFase(cap));
      console.log('');
    }

    const tsIso = new Date().toISOString();
    const registro = {
      ts: tsIso,
      etiqueta,
      cuentas: cuentas.map(c => ({ id: c.id, color: c.color, url: c.url })),
      fases: capturasPorFase,
    };
    appendRegistro(registro);

    const lineas = [];
    lineas.push('REPORTE apuesta mesa DOM · ' + tsIso);
    lineas.push('Etiqueta: ' + etiqueta);
    lineas.push('Registro append: ' + REGISTRO_JSONL);
    lineas.push('');
    for (const fase of FASES) {
      lineas.push('########## FASE: ' + fase.id + ' ##########');
      lineas.push(resumenFase(capturasPorFase[fase.id] || []));
      lineas.push('');
      for (const c of capturasPorFase[fase.id] || []) {
        lineas.push('--- ' + c.cuentaColor + ' ---');
        lineas.push(JSON.stringify(c, null, 2));
        lineas.push('');
      }
    }
    lineas.push('Fin. Cablear bot con mesaBot + barraPage + spots + faseJuego.');
    fs.writeFileSync(reportPath, lineas.join('\n'), 'utf-8');

    console.log('Reporte:', reportPath);
    console.log('Historial:', REGISTRO_JSONL);
    console.log('Capturas:', OUT_DIR);
    console.log('');
  } finally {
    for (const { ctx } of contexts) {
      try {
        await ctx.close();
      } catch (_) {}
    }
  }
}

if (require.main === module) {
  main().catch(e => {
    console.error(e);
    process.exit(1);
  });
}
