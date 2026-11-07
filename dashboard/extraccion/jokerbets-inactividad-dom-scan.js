/**
 * Escaneo DOM — inactividad (play) y error SALIR / 506.
 * Tras una apuesta manual: espera SIN F5 hasta overlay play; Enter captura.
 *
 * Uso: jokerbets/INACTIVIDAD_PASOS.txt
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { chromium } = require('playwright');
const dom = require('./jokerbets-dom.js');

const DIR = __dirname;
const CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const OUT_DIR = path.join(DIR, 'inactividad-scan');
const REGISTRO_JSONL = path.join(OUT_DIR, 'REGISTRO_INACTIVIDAD.jsonl');

const POLL_MS = 5000;
const MAX_ESPERA_MS = 35 * 60 * 1000;

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

async function escanearPagina(page, cuenta, faseId, stamp, extra = {}) {
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

  let inactividad = null;
  let playDet = null;
  let salirDet = null;
  if (frame) {
    inactividad = await dom.probeInactividadMesa(frame);
    playDet = await dom.detectPantallaInactividadPlay(frame);
    salirDet = await dom.detectPantallaErrorSalir(frame);
    try {
      await frame.locator('body').first().screenshot({
        path: path.join(OUT_DIR, `${suf}-iframe.png`),
      });
    } catch (_) {}
  }

  let mesa = { ok: false, why: 'sin-frame' };
  if (frame) {
    try {
      mesa = await dom.mesaListaParaApostar(frame);
    } catch (_) {}
  }

  return {
    cuentaId: cuenta.id,
    cuentaColor: cuenta.color,
    url: cuenta.url,
    fase: faseId,
    mainShot,
    barraPage,
    mesaBot: mesa,
    inactividad,
    detectPlay: playDet,
    detectErrorSalir: salirDet,
    ...extra,
  };
}

async function escanearTodos(contexts, faseId, stamp, extra = {}) {
  const out = [];
  for (const { cuenta, ctx } of contexts) {
    const page = ctx.pages().find(p => !p.isClosed()) || null;
    if (!page) {
      out.push({ cuentaId: cuenta.id, cuentaColor: cuenta.color, fase: faseId, error: 'sin pestaña' });
      continue;
    }
    out.push(await escanearPagina(page, cuenta, faseId, stamp, extra));
  }
  return out;
}

function appendRegistro(entry) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.appendFileSync(REGISTRO_JSONL, JSON.stringify(entry) + '\n', 'utf-8');
}

function resumenLinea(c) {
  const p = c.detectPlay;
  const e = c.detectErrorSalir;
  const parts = [
    c.cuentaColor,
    'PLAY=' + (p?.ok ? '1' : '0'),
    p?.topCandidate ? 'btn=' + (p.topCandidate.label || p.topCandidate.cls?.slice(0, 40) || '?') : '',
    p?.videoPausedLive ? 'vid-pausa' : '',
    'SALIR=' + (e?.ok ? '1' : '0'),
    e?.error506 ? '506' : '',
    'APUESTA=' + (c.barraPage?.apuesta ?? '?'),
  ];
  return parts.filter(Boolean).join(' · ');
}

function resumenFase(capturas) {
  return (capturas || []).map(resumenLinea).join('\n');
}

async function pollHastaPlayOError(contexts) {
  const t0 = Date.now();
  let ultimoLog = 0;
  console.log('');
  console.log('--- Espera activa (sin F5) hasta PLAY o error SALIR ---');
  console.log('    Poll cada', POLL_MS / 1000, 's · máx', MAX_ESPERA_MS / 60000, 'min');
  console.log('    Ctrl+C aborta. Enter manual: fase opcional error_salir al final.');
  console.log('');

  while (Date.now() - t0 < MAX_ESPERA_MS) {
    let anyPlay = false;
    let anySalir = false;
    const lineas = [];

    for (const { cuenta, ctx } of contexts) {
      const page = ctx.pages().find(p => !p.isClosed()) || null;
      if (!page) continue;
      const frame = await dom.findGameFrame(page);
      if (!frame) {
        lineas.push(cuenta.color + ': sin iframe');
        continue;
      }
      const play = await dom.detectPantallaInactividadPlay(frame);
      const salir = await dom.detectPantallaErrorSalir(frame);
      if (play.ok) anyPlay = true;
      if (salir.ok) anySalir = true;
      lineas.push(
        cuenta.color +
          ' PLAY=' +
          (play.ok ? 'SÍ' : 'no') +
          (play.topCandidate ? ' [' + (play.topCandidate.label || 'play') + ']' : '') +
          ' SALIR=' +
          (salir.ok ? 'SÍ' : 'no')
      );
    }

    const now = Date.now();
    if (now - ultimoLog >= POLL_MS) {
      ultimoLog = now;
      const mins = Math.floor((now - t0) / 60000);
      console.log('[' + mins + ' min] ' + lineas.join(' | '));
    }

    if (anySalir) {
      console.log('');
      console.log('*** ERROR SALIR / 506 detectado en al menos una ventana ***');
      console.log('    En prod: F5 (reload). Ahora: Enter para capturar fase error_salir.');
      return { motivo: 'error_salir', faseCaptura: 'error_salir' };
    }
    if (anyPlay) {
      console.log('');
      console.log('*** PLAY / inactividad detectado ***');
      console.log('    En prod: clic play. Ahora: Enter para capturar fase inactividad_play.');
      return { motivo: 'play', faseCaptura: 'inactividad_play' };
    }

    await new Promise(r => setTimeout(r, POLL_MS));
  }

  console.log('');
  console.log('Tiempo máximo de espera agotado sin PLAY ni SALIR.');
  return { motivo: 'timeout', faseCaptura: 'inactividad_play' };
}

async function main() {
  const etiqueta = (process.argv[2] || 'inactividad').toLowerCase();
  const cuentas = leerCuentas();
  if (cuentas.length < 1) {
    console.error('Sin cuentas en config.json');
    process.exit(1);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportPath = path.join(OUT_DIR, `REPORTE-${etiqueta}-${stamp}.txt`);

  console.log('');
  console.log('=== Escaneo inactividad / play / SALIR · etiqueta:', etiqueta, '===');
  console.log('Cierra antes los 3 Chrome de Cuentas (Detener), si no Chrome bloquea el perfil.');
  console.log('NO hace F5 en esta corrida.');
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
    console.log('1) Apostá a mano (chip $50 + centro) en las ventanas que quieras.');
    console.log('2) Enter → captura apuesta_ultimo_clic (desde el último clic).');
    console.log('3) NO refresques. El script espera hasta PLAY o pantalla SALIR.');
    console.log('4) Enter → captura automática según lo detectado.');
    console.log('5) (Opcional) Clic PLAY a mano → Enter → mesa_viva_post_play.');
    console.log('6) (Opcional) Si ves SALIR sin poll: Enter → error_salir_manual.');
    console.log('============================================================');
    console.log('');

    await esperarEnter('>>> Enter tras tu apuesta (último clic al centro)... ');
    const ts1 = new Date().toISOString();
    capturasPorFase.apuesta_ultimo_clic = await escanearTodos(contexts, 'apuesta_ultimo_clic', stamp, {
      ts: ts1,
    });
    console.log('');
    console.log('--- apuesta_ultimo_clic ---');
    console.log(resumenFase(capturasPorFase.apuesta_ultimo_clic));
    console.log('');

    const espera = await pollHastaPlayOError(contexts);
    const fase2 = espera.faseCaptura || 'inactividad_play';
    await esperarEnter('>>> Enter para capturar fase ' + fase2 + '... ');
    const ts2 = new Date().toISOString();
    capturasPorFase[fase2] = await escanearTodos(contexts, fase2, stamp, {
      ts: ts2,
      esperaMotivo: espera.motivo,
    });
    console.log('');
    console.log('--- ' + fase2 + ' ---');
    console.log(resumenFase(capturasPorFase[fase2]));
    console.log('');

    console.log('Opcional: clic PLAY en cada Chrome y deja correr la mesa.');
    await esperarEnter('>>> Enter para mesa_viva_post_play (o Enter vacío si saltás)... ');
    const ts3 = new Date().toISOString();
    capturasPorFase.mesa_viva_post_play = await escanearTodos(contexts, 'mesa_viva_post_play', stamp, {
      ts: ts3,
    });
    console.log('');
    console.log('--- mesa_viva_post_play ---');
    console.log(resumenFase(capturasPorFase.mesa_viva_post_play));
    console.log('');

    console.log('Si alguna vez ves la pantalla negra SALIR / error 506, Enter aquí (sin F5).');
    await esperarEnter('>>> Enter para error_salir_manual (solo si la ves ahora; sino Enter)... ');
    const ts4 = new Date().toISOString();
    capturasPorFase.error_salir_manual = await escanearTodos(contexts, 'error_salir_manual', stamp, {
      ts: ts4,
      nota: 'Captura manual; prod debe F5 cuando detectErrorSalir',
    });
    console.log('');
    console.log('--- error_salir_manual ---');
    console.log(resumenFase(capturasPorFase.error_salir_manual));

    const tsIso = new Date().toISOString();
    const registro = {
      ts: tsIso,
      etiqueta,
      espera,
      cuentas: cuentas.map(c => ({ id: c.id, color: c.color, url: c.url })),
      fases: capturasPorFase,
      cableObjetivo: {
        play: 'detectPantallaInactividadPlay → clic topCandidate / overlay',
        salir: 'detectPantallaErrorSalir → page.reload() (F5)',
      },
    };
    appendRegistro(registro);

    const lineas = [];
    lineas.push('REPORTE inactividad DOM · ' + tsIso);
    lineas.push('Etiqueta: ' + etiqueta);
    lineas.push('Registro append: ' + REGISTRO_JSONL);
    lineas.push('Espera: ' + JSON.stringify(espera));
    lineas.push('');
    for (const [faseId, cap] of Object.entries(capturasPorFase)) {
      lineas.push('########## FASE: ' + faseId + ' ##########');
      lineas.push(resumenFase(cap));
      lineas.push('');
      for (const c of cap) {
        lineas.push('--- ' + c.cuentaColor + ' ---');
        lineas.push(JSON.stringify(c, null, 2));
        lineas.push('');
      }
    }
    lineas.push('Fin. Cablear bot: play auto · F5 solo en errorSalir.');
    fs.writeFileSync(reportPath, lineas.join('\n'), 'utf-8');

    console.log('');
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
