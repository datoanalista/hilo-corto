/**
 * Escaneo DOM pantalla “TOMA TU DECISIÓN” — mismo script para cualquier bono color
 * (Dice, Luck, Deluxe, Show, Betano, etc.). No apuesta al centro; no elige por ti.
 *
 * Flujo: escaneo ANTES → tú clic manual en cada Chrome → escaneo DESPUÉS.
 * Registro acumulativo: bono-scan/REGISTRO_BONO.jsonl (no borra runs anteriores).
 *
 * Uso: ver jokerbets/BONO_DICE_PASOS.txt
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { chromium } = require('playwright');
const dom = require('./jokerbets-dom.js');

const DIR = __dirname;
const CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const OUT_DIR = path.join(DIR, 'bono-scan');
const REGISTRO_JSONL = path.join(OUT_DIR, 'REGISTRO_BONO.jsonl');

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

async function escanearFrame(frame, cuenta) {
  let pantalla = false;
  try {
    pantalla = await dom.pantallaDecision(frame);
  } catch (_) {}

  const botones = await frame
    .evaluate(() => {
      const sel =
        '[class*="bonus-action-button"], [class*="decision-color"], [class*="decision"] button, [class*="decision"] [role="button"], button, [role="button"]';
      const raw = Array.from(document.querySelectorAll(sel));
      const area = document.getElementById('game-area');
      const ar = area?.getBoundingClientRect();
      const txt = (document.body?.innerText || '').slice(0, 800);
      const filas = raw
        .map(el => {
          const r = el.getBoundingClientRect();
          const cls = (el.className || '').toString();
          const clsL = cls.toLowerCase();
          const aria =
            el.getAttribute('aria-pressed') ||
            el.getAttribute('aria-selected') ||
            el.getAttribute('aria-checked') ||
            '';
          const marcado =
            /active|selected|chosen|picked|on|blink/.test(clsL) ||
            aria === 'true' ||
            el.matches('[class*="active"], [class*="selected"]');
          return {
            tag: el.tagName,
            cls: cls.slice(0, 120),
            marcado,
            w: Math.round(r.width),
            h: Math.round(r.height),
            x: Math.round(r.left),
            y: Math.round(r.top),
            dice: /icon-dice|dice-action/i.test(cls),
            visible: r.width > 8 && r.height > 8 && r.bottom > 0,
            enArea:
              !ar ||
              (r.top >= ar.top + ar.height * 0.2 &&
                r.bottom <= ar.bottom + 8 &&
                r.left >= ar.left - 20 &&
                r.right <= ar.right + 20),
          };
        })
        .filter(b => b.visible)
        .sort((a, b) => a.y - b.y || a.x - b.x);

      const triadaCandidatos = filas.filter(b => !b.dice && b.enArea);
      const diceCandidatos = filas.filter(b => b.dice && b.enArea);
      const triadaOrd = [...triadaCandidatos].sort((a, b) => a.x - b.x);
      const marcadosSinDice = triadaOrd
        .map((b, i) => (b.marcado ? i : -1))
        .filter(i => i >= 0);
      const colorPorIdx = ['rojo', 'azul', 'verde'];

      return {
        url: location.href.slice(0, 200),
        decisionText: /toma tu decisi|make your decision/i.test(txt),
        nBotonesVisibles: filas.length,
        nSinDiceEnArea: triadaCandidatos.length,
        nDiceEnArea: diceCandidatos.length,
        marcadosIdxSinDice: marcadosSinDice,
        colorElegidoEstimado: marcadosSinDice.length
          ? marcadosSinDice.map(i => colorPorIdx[i] || 'idx' + i).join(',')
          : null,
        sinDice: triadaCandidatos.slice(0, 12),
        conDice: diceCandidatos.slice(0, 12),
        snippet: txt.replace(/\s+/g, ' ').slice(0, 400),
      };
    })
    .catch(e => ({ error: String(e.message || e).slice(0, 120) }));

  return { cuenta: cuenta.color, id: cuenta.id, pantalla, botones };
}

async function escanearPagina(page, cuenta, fase, stamp) {
  const frame = await dom.findGameFrame(page);
  const suf = `${cuenta.color}-${fase}-${stamp}`;
  const mainShot = path.join(OUT_DIR, `${suf}-pagina.png`);
  try {
    await page.screenshot({ path: mainShot, fullPage: false });
  } catch (_) {}

  const frames = page.frames();
  const informes = [];
  if (frame) {
    informes.push(await escanearFrame(frame, cuenta));
    try {
      await frame.locator('body').first().screenshot({
        path: path.join(OUT_DIR, `${suf}-iframe.png`),
      });
    } catch (_) {}
  } else {
    informes.push({
      cuenta: cuenta.color,
      id: cuenta.id,
      pantalla: false,
      botones: { error: 'sin iframe juego (findGameFrame null)' },
    });
  }

  for (const f of frames) {
    const u = (f.url() || '').toLowerCase();
    if (!u.includes('sw420101') && !u.includes('live-client-jokers') && !u.includes('skywind')) continue;
    if (frame && f === frame) continue;
    informes.push(await escanearFrame(f, { ...cuenta, color: cuenta.color + '+frame' }));
  }

  return {
    cuentaId: cuenta.id,
    cuentaColor: cuenta.color,
    bonoColorConfig: cuenta.bonoColor || null,
    url: cuenta.url,
    mainShot,
    informes,
  };
}

async function escanearTodos(contexts, fase, stamp) {
  const out = [];
  for (const { cuenta, ctx } of contexts) {
    const page = ctx.pages().find(p => !p.isClosed()) || null;
    if (!page) {
      out.push({
        cuentaId: cuenta.id,
        cuentaColor: cuenta.color,
        error: 'sin pestaña',
      });
      continue;
    }
    out.push(await escanearPagina(page, cuenta, fase, stamp));
  }
  return out;
}

function appendRegistro(entry) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.appendFileSync(REGISTRO_JSONL, JSON.stringify(entry) + '\n', 'utf-8');
}

async function main() {
  const modo = (process.argv[2] || 'dice').toLowerCase();
  const cuentas = leerCuentas();
  if (cuentas.length < 1) {
    console.error('Sin cuentas en config.json');
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportPath = path.join(OUT_DIR, `REPORTE-${modo}-${stamp}.txt`);

  console.log('');
  console.log('=== Escaneo bono color · etiqueta juego:', modo, '===');
  console.log('Cierra antes los 3 Chrome de Cuentas (Detener), si no Chrome bloquea el perfil.');
  console.log('');

  const contexts = [];
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
    console.log('LISTO. Mira ESTA ventana (PowerShell), no los Chrome.');
    console.log('Nada se escanea solo al entrar al bono: TÚ pulsas Enter.');
    console.log('============================================================');
    console.log('Cada Chrome = tarjeta rojo / azul / verde en Cuentas.');
    console.log('');
    console.log('1) Entra al juego en las 3 ventanas y espera TOMA TU DECISIÓN.');
    console.log('2) Enter aquí → escaneo ANTES (sin elegir color aún).');
    console.log('3) Elige color a mano en cada Chrome.');
    console.log('4) Enter otra vez → escaneo DESPUÉS + guarda reporte.');
    console.log('');

    await esperarEnter('>>> Enter con TOMA TU DECISIÓN visible (escaneo ANTES)... ');

    const tsIso = new Date().toISOString();
    const antes = await escanearTodos(contexts, 'antes', stamp);

    console.log('');
    console.log('Ahora haz clic en el color en cada Chrome (rojo/azul/verde = tarjeta Cuentas).');
    console.log('Betano = tarjeta verde · Jugabet = tarjetas rojo y azul.');
    await esperarEnter('>>> Enter después de elegir color en cada ventana (escaneo DESPUÉS)... ');

    const despues = await escanearTodos(contexts, 'despues', stamp);

    const registro = {
      ts: tsIso,
      juego: modo,
      cuentas: cuentas.map(c => ({
        id: c.id,
        color: c.color,
        bonoColorConfig: c.bonoColor,
      })),
      antes,
      despues,
    };
    appendRegistro(registro);

    const lineas = [];
    lineas.push('REPORTE bono DOM · ' + tsIso);
    lineas.push('Juego (etiqueta): ' + modo);
    lineas.push('Registro append: ' + REGISTRO_JSONL);
    lineas.push('');

    for (let i = 0; i < cuentas.length; i += 1) {
      const c = cuentas[i];
      const a = antes[i];
      const d = despues[i];
      lineas.push('========== ' + c.color + ' · ' + c.id + ' ==========');
      lineas.push('bonoColor config: ' + (c.bonoColor || '?'));
      lineas.push('URL: ' + (c.url || ''));
      if (a?.informes?.[0]?.botones) {
        lineas.push('ANTES color estimado: ' + (a.informes[0].botones.colorElegidoEstimado || '—'));
      }
      if (d?.informes?.[0]?.botones) {
        lineas.push('DESPUÉS color elegido (DOM): ' + (d.informes[0].botones.colorElegidoEstimado || '—'));
      }
      lineas.push('Capturas: *-' + stamp + '-antes/despues-*.png');
      lineas.push(JSON.stringify({ antes: a, despues: d }, null, 2));
      lineas.push('');
    }

    lineas.push('Fin. Mismo script para cualquier bono con TOMA TU DECISIÓN.');
    fs.writeFileSync(reportPath, lineas.join('\n'), 'utf-8');
    console.log('');
    console.log('Reporte:', reportPath);
    console.log('Historial (no se pisa):', REGISTRO_JSONL);
    console.log('Capturas en:', OUT_DIR);
    console.log('');
  } finally {
    for (const { ctx } of contexts) {
      try {
        await ctx.close();
      } catch (_) {}
    }
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
