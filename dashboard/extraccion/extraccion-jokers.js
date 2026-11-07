/*
 * Extraccion en vivo de Jokers Wheel: conecta al WS del juego (Skywind) y
 * convierte cada ronda al vuelo al formato de la cinta (h{hora}-{ddMMyy} /
 * MM:SS-MM:SS G1..G4|R [valor]). No toca consolidado-jocker.json: esto es
 * exclusivo para la vista "Extraccion" del dashboard.
 *
 * Agnostico al casino: detecta el juego por el WS de Skywind (GAME_WS_HOST)
 * en cualquier pestaña ya abierta de la misma sesión de Chrome, sin navegar
 * a ninguna URL fija. El usuario abre el casino que quiera manualmente.
 *
 * Estado de "lista para pegar en la cinta" = FastAPI/React deciden; este
 * script solo captura y muestra.
 */
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

const EXTRACTOR_REV = '2026-09-18c';
const DIR          = __dirname;
const PERFIL_DIR   = path.join(DIR, 'perfil-jugabet');
const LINEAS_FILE  = path.join(DIR, 'extraccion-en-vivo.txt');
const ESTADO_FILE  = path.join(DIR, 'extraccion-estado.json');
const LIMPIAR_FILE = path.join(DIR, 'extraccion-limpiar.flag');
const INYECTAR_FILE = path.join(DIR, 'extraccion-inyectar.json');
const PAUSA_FILE   = path.join(DIR, 'extraccion-pausa.flag');
const PID_FILE     = path.join(DIR, 'extraccion.pid');
const URL_MESA_FILE = path.join(DIR, 'ultima-url-mesa.txt');
const JOKERBETS_CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const CUENTAS_ESTADO_FILE = path.join(DIR, 'jokerbets-cuentas-estado.json');
const GAME_WS_HOST = 'sw420101.com';
const FAILOVER_WS_MS = 45 * 1000;

function esWsJuego(wsUrl) {
  const u = String(wsUrl || '').toLowerCase();
  return u.includes(GAME_WS_HOST) && u.includes('socket-v4');
}

function esPaginaBasura(url) {
  const u = String(url || '').toLowerCase();
  if (!u || u === 'about:blank') return true;
  if (u.startsWith('chrome://') || u.startsWith('chrome-extension://') || u.startsWith('edge://')) {
    return true;
  }
  if (u.includes(GAME_WS_HOST)) return false;
  return /cookiebot|consentcdn|cookie-script|onetrust|cookielaw|doubleclick|googlesyndication|googleads|googletagmanager|google-analytics|facebook\.com|scorecardresearch|quantserve|adnxs|criteo|taboola|outbrain|pubmatic|rubiconproject|openx|moatads|amazon-adsystem|rfihub|rocketfuel|casalemedia|adsystem|adservice|pagead|adform|bidswitch|hotjar|clarity\.ms/.test(u);
}

function asegurarHoraReloj() {
  const ahora = new Date();
  const key =
    ahora.getFullYear() +
    '-' +
    ahora.getMonth() +
    '-' +
    ahora.getDate() +
    '-' +
    ahora.getHours();
  if (horaActualKey === key) return;
  if (lineas.length && lineas[lineas.length - 1] !== '') lineas.push('');
  lineas.push(headerDe(ahora));
  horaActualKey = key;
  guardarLineas();
  log('Hora reloj abierta: ' + headerDe(ahora));
}
const SILENCIO_MAX = 3 * 60 * 1000;
// F5 periódico solo en extracción single-tab. En jokerbets ×3 Chrome: play + F5
// 5 min sin cambio de enCurso (jokerbets-bot.js), no keep-alive cada 8 min.
const F5_INTERVAL  = 8 * 60 * 1000;
const F5_MAX       = 9 * 60 * 1000;
const PRIMERA_RONDA_MS = 90 * 1000;
const PENDIENTE_MAX = 6 * 60 * 1000;
const F5_FALLOS_PARA_BACKOFF = 3;
const F5_BACKOFF_MS = 15 * 60 * 1000;
/**
 * Multi ×3: una cuenta cada 2 min (rojo→azul→verde→…).
 * Cada navegador se refresca cada 6 min; nunca los 3 a la vez.
 */
const F5_ROTACION_ENTRE_MS = 2 * 60 * 1000;
const F5_ROTACION_TICK_MS = 30 * 1000;
const MAX_HORAS_BUFFER = 120;

const SPECIAL_TO_GROUP = { deluxe: 'G1', luck: 'G2', dice: 'G3', wheel: 'G4' };

function buscarChrome() {
  const rutas = [
    path.join(process.env['ProgramFiles']      || 'C:\\Program Files',       'Google\\Chrome\\Application\\chrome.exe'),
    path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'Google\\Chrome\\Application\\chrome.exe'),
    path.join(process.env['LOCALAPPDATA']      || '', 'Google\\Chrome\\Application\\chrome.exe'),
  ];
  for (const r of rutas) { if (r && fs.existsSync(r)) return r; }
  return null;
}

// Si una corrida anterior murió sin cerrar Chrome prolijamente (kill forzado),
// quedan estos locks y el próximo intento de abrir el mismo perfil falla.
function limpiarLocksHuerfanos(perfilDir = PERFIL_DIR) {
  for (const nombre of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
    try { fs.rmSync(path.join(perfilDir, nombre), { force: true }); } catch (_) {}
  }
}

function leerJokerbetsCuentas() {
  try {
    if (!fs.existsSync(JOKERBETS_CONFIG_FILE)) return null;
    const cfg = JSON.parse(fs.readFileSync(JOKERBETS_CONFIG_FILE, 'utf-8'));
    const id = cfg.activeNotebookId || cfg.notebooks?.[0]?.id;
    const nb = (cfg.notebooks || []).find(n => n.id === id) || cfg.notebooks?.[0];
    if (!nb?.cuentas?.length) return null;
    return nb.cuentas.map(c => ({
      id: c.id,
      color: c.color,
      bonoColor: c.bonoColor || c.color,
      url: String(c.url || '').trim(),
      wsPrimaria: Boolean(c.wsPrimaria),
    }));
  } catch (_) {
    return null;
  }
}

/** @type {null | { cuenta: object, context: import('playwright').BrowserContext }[]} */
let contextsMulti = null;
const pageCuentaMap = new WeakMap();
let activeCuentaId = null;
let cuentasFailoverOrden = [];
let lastFrameAt = 0;
/** @type {Record<string, { ultimoSaldo?: string, ultimoGesto?: string }>} */
let botRuntimeByCuenta = {};
let botInterval = null;
let senalSyncTimer = null;
let f5RotacionTimer = null;
let f5RotacionIdx = 0;
let f5RotacionUltimoAt = 0;
let lastUiPulseSeq = 0;
let lastEstadoCuentasAt = 0;
/** @type {Record<string, unknown>} */
let lastBotEstadoExtra = {};
const ESTADO_CUENTAS_MIN_MS = 120_000;

function manualApuestaPendiente() {
  try {
    const manual = require('./jokerbets-manual.js');
    return manual.permitirTick(manual.leerManual());
  } catch (_) {
    return false;
  }
}

async function refrescarF5UnaCuenta({ cuenta, context }, motivo) {
  if (refrescando) return { ok: false, why: 'ocupado' };
  if (Date.now() < proximoF5Permitido) {
    log('F5 rotación omitido (backoff): ' + motivo);
    return { ok: false, why: 'backoff' };
  }
  refrescando = true;
  ultimoRefresh = Date.now();
  let page = null;
  try {
    try {
      page = context.pages().find(p => !p.isClosed()) || null;
    } catch (_) {
      page = null;
    }
    if (!page) {
      try {
        page = await context.newPage();
      } catch (e) {
        log('F5 ' + cuenta.color + ' sin pestaña: ' + String(e.message || e).slice(0, 60));
        return { ok: false, why: 'sin-pestaña' };
      }
    }
    const urlObjetivo = String(cuenta.url || '').trim() || ultimaUrlMesa;
    let urlAhora = '';
    try {
      urlAhora = page.url();
    } catch (_) {}
    try {
      await page.bringToFront();
      const irMesa =
        Boolean(urlObjetivo) &&
        (!esUrlMesa(urlAhora) || /about:blank/i.test(urlAhora));
      if (irMesa) {
        await page.goto(urlObjetivo, { waitUntil: 'commit', timeout: 30000 });
        log('F5 goto ' + cuenta.color + ' (' + motivo + ')');
      } else {
        await page.reload({ waitUntil: 'commit', timeout: 30000 });
        log('F5 reload ' + cuenta.color + ' (' + motivo + ')');
      }
      recordarUrlMesa(urlObjetivo || urlAhora);
      fallosF5Seguidos = 0;
      return { ok: true, color: cuenta.color };
    } catch (e) {
      const msg = String(e.message || e).slice(0, 80);
      log('F5 fallo ' + cuenta.color + ': ' + msg);
      if (urlObjetivo) {
        try {
          await page.goto(urlObjetivo, { waitUntil: 'commit', timeout: 30000 });
          log('F5 fallback goto ' + cuenta.color);
          fallosF5Seguidos = 0;
          return { ok: true, color: cuenta.color };
        } catch (e2) {
          log('F5 fallback ' + cuenta.color + ' fallo: ' + String(e2.message || e2).slice(0, 60));
        }
      }
      fallosF5Seguidos += 1;
      if (fallosF5Seguidos >= F5_FALLOS_PARA_BACKOFF) {
        proximoF5Permitido = Date.now() + F5_BACKOFF_MS;
        log('F5 en backoff 15 min tras ' + fallosF5Seguidos + ' fallos.');
      }
      return { ok: false, why: msg };
    }
  } finally {
    refrescando = false;
  }
}

async function mesaEnTramoApuestaOBono(page) {
  const dom = require('./jokerbets-dom.js');
  let frame = null;
  try {
    frame = await dom.findGameFrame(page);
  } catch (_) {
    frame = null;
  }
  if (!frame) return false;
  try {
    if (await dom.pantallaDecision(frame)) return true;
    const ventana = await dom.ventanaApuestaAbierta(frame);
    return !!ventana.ok;
  } catch (_) {
    return false;
  }
}

async function tickF5Rotacion() {
  if (!contextsMulti?.length || pausadoManual || manualApuestaPendiente()) return;
  const ahora = Date.now();
  if (ahora - f5RotacionUltimoAt < F5_ROTACION_ENTRE_MS) return;
  const slot = contextsMulti[f5RotacionIdx % contextsMulti.length];
  let page = null;
  try {
    page = slot.context.pages().find(p => !p.isClosed()) || null;
  } catch (_) {
    page = null;
  }
  if (page && (await mesaEnTramoApuestaOBono(page))) {
    log(
      'F5 rotación pospuesto · ' +
        (slot?.cuenta?.color || '?') +
        ' en ventana apuesta/bono (reintento ~45 s)'
    );
    return;
  }
  f5RotacionIdx += 1;
  f5RotacionUltimoAt = ahora;
  const next = contextsMulti[f5RotacionIdx % contextsMulti.length]?.cuenta?.color || '?';
  log(
    'F5 rotación · toca ' +
      (slot?.cuenta?.color || '?') +
      ' · próxima en ~2 min (' +
      next +
      ') · ciclo ~6 min/cuenta'
  );
  await refrescarF5UnaCuenta(slot, 'rotacion-memoria-6m');
}

function sincronizarEstadoCuentasPorPulso(extra) {
  try {
    const jlog = require('./jokerbets-log.js');
    const pulse = jlog.readUiPulse();
    const seq = pulse?.seq || 0;
    const now = Date.now();
    const pulsoNuevo = seq && seq !== lastUiPulseSeq;
    const tocaFallback = now - lastEstadoCuentasAt >= ESTADO_CUENTAS_MIN_MS;
    if (!pulsoNuevo && !tocaFallback) return;
    if (pulsoNuevo) lastUiPulseSeq = seq;
    lastEstadoCuentasAt = now;
    actualizarEstadoCuentas(extra || {});
  } catch (_) {}
}

function iniciarF5Rotacion() {
  if (f5RotacionTimer) clearInterval(f5RotacionTimer);
  f5RotacionIdx = 0;
  f5RotacionUltimoAt = Date.now();
  log(
    'F5 rotación activo: 1 cuenta / 2 min · cada navegador cada 6 min (sin F5×3 simultáneo).'
  );
  f5RotacionTimer = setInterval(() => {
    tickF5Rotacion().catch(e =>
      log('F5 rotación error: ' + String(e.message || e).slice(0, 80))
    );
  }, F5_ROTACION_TICK_MS);
}

function contextsActivos() {
  if (contextsMulti) return contextsMulti.map(x => x.context);
  return contextRef ? [contextRef] : [];
}

function cuentaPorId(id) {
  if (!contextsMulti) return null;
  return contextsMulti.find(x => x.cuenta.id === id)?.cuenta || null;
}

function actualizarEstadoCuentas(extra) {
  if (!contextsMulti) return;
  try {
    const payload = {
      actualizado: new Date().toISOString(),
      fuenteWsId: activeCuentaId,
      fuenteWsColor: cuentaPorId(activeCuentaId)?.color || null,
      cuentas: contextsMulti.map(({ cuenta, context }) => {
        let urlAbierta = '';
        try {
          const p = context.pages().find(pg => !pg.isClosed());
          if (p) urlAbierta = p.url() || '';
        } catch (_) {}
        return {
          id: cuenta.id,
          color: cuenta.color,
          wsPrimaria: cuenta.wsPrimaria,
          urlConfig: cuenta.url,
          urlAbierta: urlAbierta.slice(0, 240),
          wsActiva: cuenta.id === activeCuentaId,
          chromeAbierto: (() => {
            try {
              return context.pages().some(p => !p.isClosed());
            } catch (_) {
              return false;
            }
          })(),
          saldoDom: botRuntimeByCuenta[cuenta.id]?.ultimoSaldo || null,
          apuestaDom: botRuntimeByCuenta[cuenta.id]?.ultimoApuesta || null,
          ultimoGesto: botRuntimeByCuenta[cuenta.id]?.ultimoGesto || null,
        };
      }),
      ...extra,
    };
    fs.writeFileSync(CUENTAS_ESTADO_FILE, JSON.stringify(payload, null, 2), 'utf-8');
  } catch (_) {}
}

function elegirFailover() {
  if (!contextsMulti || !cuentasFailoverOrden.length) return;
  const idx = cuentasFailoverOrden.indexOf(activeCuentaId);
  const next = cuentasFailoverOrden[(idx + 1) % cuentasFailoverOrden.length];
  if (next === activeCuentaId) return;
  activeCuentaId = next;
  const slot = contextsMulti.find(x => x.cuenta.id === activeCuentaId);
  if (slot) contextRef = slot.context;
  lastFrameAt = Date.now();
  log('Failover WS → cuenta ' + (slot?.cuenta?.color || activeCuentaId));
  guardarEstado(
    'conectado',
    'WS backup: extracción desde cuenta ' + (slot?.cuenta?.color || '') + '.'
  );
  actualizarEstadoCuentas({ ultimoFailover: new Date().toISOString() });
}

function pad2(n) { return String(n).padStart(2, '0'); }
function formatMS(dt) { return pad2(dt.getMinutes()) + ':' + pad2(dt.getSeconds()); }
function headerDe(dt) {
  return 'h' + dt.getHours() + '-' + pad2(dt.getDate()) + pad2(dt.getMonth() + 1) + String(dt.getFullYear()).slice(-2);
}
function log(m) {
  const d = new Date();
  console.log('[' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()) + '] ' + m);
}

function sumBonusResult(bonusResult) {
  if (!bonusResult || typeof bonusResult !== 'object') return 0;
  let total = 0;
  for (const v of Object.values(bonusResult)) {
    const n = parseInt(v, 10);
    if (!Number.isNaN(n)) total += n;
  }
  return total;
}

// ── Estado en memoria de la cinta que se va mostrando ───────────────────────────
const lineas = [];
let horaActualKey = null;
let pendiente = null; // { idx, startDt, label, valor }
// Serializa registrarRonda(): esta función hace un await (el reload de F5) en
// medio de su ejecución; sin esta cola, una segunda ronda que termine durante
// ese await corre en paralelo y pisa "pendiente", dejando tramos huérfanos.
let colaEventos = Promise.resolve();

// ── Estado de conexión y refresh de la página del juego ─────────────────────────
let paginaJuego = null;
let paginaWsJuego = null;
let contextRef = null;
let ultimaUrlMesa = '';
try {
  if (fs.existsSync(URL_MESA_FILE)) {
    ultimaUrlMesa = fs.readFileSync(URL_MESA_FILE, 'utf-8').trim();
  }
} catch (_) {}
let ultimaSenal = Date.now();
let ultimaRonda = 0;
let wsConectadoDesde = 0;
let eventosWsLog = 0;
let framesWs = 0;
let ultimoDiag = 0;
let refrescando = false;
let ultimoRefresh = Date.now();
let refrescoPendiente = false; // pedido de refresh a la espera del próximo hueco entre rondas
let wsJuegoAbiertos = 0;
let fallosF5Seguidos = 0;
let proximoF5Permitido = 0;

function esHeaderHora(l) {
  return /^h\d{1,2}-\d{6}$/i.test((l || '').trim());
}
function esTramoCerrado(l) {
  return /^\d{1,2}:\d{2}-\d{1,2}:\d{2}\s+(R|G\d?)(?:\s+\d+)?\s*$/i.test((l || '').trim());
}
function esEnJuego(l) {
  return /en juego/i.test(l || '');
}
function esInterrumpido(l) {
  return /interrumpido/i.test(l || '');
}

// Nunca escribimos "[interrumpido por refresh]". F5 no corta el tramo: solo
// recarga la página. Cualquier "en juego" viejo o con ese sufijo es basura.
function purgarBasuraEnMemoria() {
  let quitados = 0;
  for (let i = lineas.length - 1; i >= 0; i -= 1) {
    const l = lineas[i];
    const vivoActual = pendiente && pendiente.idx === i;
    if (esInterrumpido(l) || (esEnJuego(l) && !vivoActual)) {
      lineas.splice(i, 1);
      if (pendiente && pendiente.idx > i) pendiente.idx -= 1;
      quitados += 1;
    }
  }
  return quitados;
}

function horaKeyDesdeHeader(header) {
  const m = /^h(\d{1,2})-(\d{2})(\d{2})(\d{2})$/i.exec((header || '').trim());
  if (!m) return null;
  const hora = Number(m[1]);
  const dia = Number(m[2]);
  const mes = Number(m[3]) - 1;
  const anio = 2000 + Number(m[4]);
  return anio + '-' + mes + '-' + dia + '-' + hora;
}

// Al arrancar: conservar historial válido y tirar basura del F5 viejo.
function cargarBufferExistente() {
  if (!fs.existsSync(LINEAS_FILE)) return;
  let raw;
  try {
    raw = fs.readFileSync(LINEAS_FILE, 'utf-8').split(/\r?\n/);
  } catch (_) {
    return;
  }
  let ultimoHeader = null;
  for (const l of raw) {
    const s = (l || '').trim();
    if (!s) {
      if (lineas.length && lineas[lineas.length - 1] !== '') lineas.push('');
      continue;
    }
    if (esHeaderHora(s)) {
      lineas.push(s);
      ultimoHeader = s;
      continue;
    }
    if (esTramoCerrado(s)) {
      lineas.push(s);
      continue;
    }
    // en juego / interrumpido / basura → se descartan al cargar
  }
  pendiente = null;
  horaActualKey = ultimoHeader ? horaKeyDesdeHeader(ultimoHeader) : null;
  const n = purgarBasuraEnMemoria();
  guardarLineas();
  if (n || raw.length !== lineas.length) {
    log('Buffer cargado y saneado (' + lineas.length + ' líneas; basura F5 descartada).');
  }
}

// page.reload() (CDP Page.reload) hace el mismo reload de red/sesión que un F5
// manual exitoso, pero sin depender del foco de la ventana ni del acelerador
// de teclado de Chrome (a diferencia de keyboard.press('F5'), que en algunas
// instalaciones nunca llega a disparar el reload real).
function paginaTieneMesa(page) {
  try {
    if (page.isClosed()) return false;
    const u = String(page.url() || '').toLowerCase();
    if (u.includes(GAME_WS_HOST) || /joker|skywind/.test(u)) return true;
    for (const f of page.frames()) {
      const fu = String(f.url() || '').toLowerCase();
      if (fu.includes(GAME_WS_HOST) || /joker|skywind/.test(fu)) return true;
    }
  } catch (_) {}
  return false;
}

function urlsAbiertas() {
  const ctxs = contextsActivos();
  if (!ctxs.length) return '(sin Chrome)';
  const out = [];
  for (const ctx of ctxs) {
    for (const p of ctx.pages()) {
      try {
        if (!p.isClosed()) {
          const cid = pageCuentaMap.get(p);
          const tag = cid ? `[${cid}] ` : '';
          out.push(tag + (p.url() || '(vacía)'));
        }
      } catch (_) {}
    }
  }
  return out.length ? out.join(' | ') : '(ninguna pestaña)';
}

function esUrlMesa(url) {
  const u = String(url || '').toLowerCase();
  return u.includes(GAME_WS_HOST) || /joker|skywind/.test(u);
}

function recordarUrlMesa(url) {
  const u = String(url || '').trim();
  if (u && esUrlMesa(u) && !u.startsWith('about:')) {
    ultimaUrlMesa = u;
    try { fs.writeFileSync(URL_MESA_FILE, u, 'utf-8'); } catch (_) {}
  }
}

function paginaParaF5() {
  const abiertas = [];
  const ctxs = contextsActivos();
  for (const ctx of ctxs) {
    for (const p of ctx.pages()) {
      try {
        if (!p.isClosed()) abiertas.push(p);
      } catch (_) {}
    }
  }
  if (activeCuentaId) {
    const prefer = abiertas.filter(p => pageCuentaMap.get(p) === activeCuentaId);
    if (prefer.length) {
      const conMesaP = prefer.filter(paginaTieneMesa);
      if (conMesaP.length) return conMesaP[0];
      return prefer[0];
    }
  }
  const conMesa = abiertas.filter(paginaTieneMesa);
  if (paginaJuego && conMesa.includes(paginaJuego)) return paginaJuego;
  if (conMesa.length) return conMesa[0];
  const limpias = abiertas.filter((p) => {
    try { return !esPaginaBasura(p.url()); } catch (_) { return false; }
  });
  if (paginaJuego && limpias.includes(paginaJuego)) return paginaJuego;
  if (limpias.length) return limpias[0];
  if (paginaWsJuego && !paginaWsJuego.isClosed()) return paginaWsJuego;
  if (paginaJuego && !paginaJuego.isClosed()) return paginaJuego;
  return abiertas[0] || null;
}

function soltarPendienteColgado() {
  if (!pendiente) return false;
  if (Date.now() - pendiente.startDt.getTime() < PENDIENTE_MAX) return false;
  log('Tramo en juego abandonado (>6 min). Lo suelto.');
  try {
    if (pendiente.idx >= 0 && pendiente.idx < lineas.length) {
      lineas.splice(pendiente.idx, 1);
    }
  } catch (_) {}
  pendiente = null;
  guardarLineas();
  return true;
}

async function refrescarF5TodasCuentas(motivo) {
  if (refrescando) return;
  if (!contextsMulti?.length) {
    await refrescarF5(motivo);
    return;
  }
  if (Date.now() < proximoF5Permitido) {
    log('F5×3 omitido (backoff): ' + motivo);
    return;
  }
  refrescando = true;
  ultimoRefresh = Date.now();
  try {
    for (const { cuenta, context } of contextsMulti) {
      let page = null;
      try {
        page = context.pages().find(p => !p.isClosed()) || null;
      } catch (_) {
        page = null;
      }
      if (!page) {
        try {
          page = await context.newPage();
        } catch (e) {
          log('F5 ' + cuenta.color + ' sin pestaña: ' + String(e.message || e).slice(0, 60));
          continue;
        }
      }
      const urlObjetivo = String(cuenta.url || '').trim() || ultimaUrlMesa;
      let urlAhora = '';
      try {
        urlAhora = page.url();
      } catch (_) {}
      try {
        await page.bringToFront();
        const irMesa =
          Boolean(urlObjetivo) &&
          (!esUrlMesa(urlAhora) || /about:blank/i.test(urlAhora));
        if (irMesa) {
          await page.goto(urlObjetivo, { waitUntil: 'commit', timeout: 30000 });
          log('F5 goto ' + cuenta.color + ' (' + motivo + ')');
        } else {
          await page.reload({ waitUntil: 'commit', timeout: 30000 });
          log('F5 reload ' + cuenta.color + ' (' + motivo + ')');
        }
        recordarUrlMesa(urlObjetivo || urlAhora);
      } catch (e) {
        const msg = String(e.message || e).slice(0, 80);
        log('F5 fallo ' + cuenta.color + ': ' + msg);
        if (urlObjetivo) {
          try {
            await page.goto(urlObjetivo, { waitUntil: 'commit', timeout: 30000 });
            log('F5 fallback goto ' + cuenta.color);
          } catch (e2) {
            log('F5 fallback ' + cuenta.color + ' fallo: ' + String(e2.message || e2).slice(0, 60));
          }
        }
      }
      await new Promise(r => setTimeout(r, 2500));
    }
    fallosF5Seguidos = 0;
  } finally {
    refrescando = false;
  }
}

function f5KeepAliveExtraccionActivo() {
  return !(contextsMulti && contextsMulti.length);
}

async function refrescarKeepAlive(motivo) {
  if (contextsMulti?.length) {
    if (!f5KeepAliveExtraccionActivo()) {
      log('F5×3 omitido (multi usa rotación 1/5 min): ' + motivo);
      return;
    }
    await refrescarF5TodasCuentas(motivo);
    return;
  }
  await refrescarF5(motivo);
}

async function refrescarF5(motivo) {
  if (refrescando) return;
  if (Date.now() < proximoF5Permitido) {
    log('F5 omitido (backoff tras Frame was detached): ' + motivo);
    return;
  }
  let target = paginaParaF5();
  if ((!target || target.isClosed()) && contextRef) {
    try {
      target = await contextRef.newPage();
      log('F5: pestaña nueva');
    } catch (e) {
      log('F5 omitido (no pude abrir pestaña): ' + String(e.message || e).slice(0, 80));
      return;
    }
  }
  if (!target) {
    log('F5 omitido (sin Chrome): ' + motivo + ' · abiertas: ' + urlsAbiertas());
    return;
  }
  paginaJuego = target;
  refrescando = true;
  let urlAhora = '';
  try { urlAhora = target.url(); } catch (_) {}
  try {
    ultimoRefresh = Date.now();
    try { await target.bringToFront(); } catch (_) {}
    const cuentaActiva = activeCuentaId ? cuentaPorId(activeCuentaId) : null;
    const urlObjetivo = (cuentaActiva && cuentaActiva.url) || ultimaUrlMesa;
    const irMesa =
      Boolean(urlObjetivo) &&
      (!esUrlMesa(urlAhora) || /about:blank/i.test(urlAhora));
    if (irMesa) {
      await target.goto(urlObjetivo, { waitUntil: 'commit', timeout: 30000 });
      log('F5 goto mesa (' + motivo + ') · ' + urlObjetivo.slice(0, 90));
    } else {
      await target.reload({ waitUntil: 'commit', timeout: 30000 });
      log('F5 keep-alive (' + motivo + ') · ' + String(urlAhora).slice(0, 90));
    }
    fallosF5Seguidos = 0;
  } catch (e) {
    const msg = String(e.message || e).slice(0, 80);
    log('F5 keep-alive fallo: ' + msg);
    const cuentaActivaFb = activeCuentaId ? cuentaPorId(activeCuentaId) : null;
    const urlFb = (cuentaActivaFb && cuentaActivaFb.url) || ultimaUrlMesa;
    if (urlFb) {
      try {
        await target.goto(urlFb, { waitUntil: 'commit', timeout: 30000 });
        log('F5 fallback goto · ' + urlFb.slice(0, 90));
        fallosF5Seguidos = 0;
      } catch (e2) {
        log('F5 fallback goto fallo: ' + String(e2.message || e2).slice(0, 80));
      }
    }
    if (/frame was detached/i.test(msg)) {
      fallosF5Seguidos += 1;
      if (fallosF5Seguidos >= F5_FALLOS_PARA_BACKOFF) {
        proximoF5Permitido = Date.now() + F5_BACKOFF_MS;
        log('F5 en backoff 15 min tras ' + fallosF5Seguidos + ' fallos Frame was detached.');
      }
    }
  } finally {
    refrescando = false;
  }
}

function guardarEstado(estado, mensaje) {
  try {
    fs.writeFileSync(ESTADO_FILE, JSON.stringify({
      estado, mensaje, actualizado: new Date().toISOString(),
    }), 'utf-8');
  } catch (_) {}
}

function recortarBufferHoras() {
  const headers = [];
  for (let i = 0; i < lineas.length; i += 1) {
    if (esHeaderHora(lineas[i])) headers.push(i);
  }
  if (headers.length <= MAX_HORAS_BUFFER) return;
  const cut = headers[headers.length - MAX_HORAS_BUFFER];
  lineas.splice(0, cut);
  if (pendiente) {
    if (pendiente.idx < cut) pendiente = null;
    else pendiente.idx -= cut;
  }
}

function guardarLineas() {
  purgarBasuraEnMemoria();
  sanejarDuplicadosPorInicio();
  recortarBufferHoras();
  // Atomic replace: evita que /api/extraccion/estado lea el .txt a medias
  // (eso hacía saltar luces/chips en el tablero a cada poll).
  try {
    const tmp = LINEAS_FILE + '.tmp';
    const body = lineas.join('\n') + '\n';
    fs.writeFileSync(tmp, body, 'utf-8');
    try {
      fs.renameSync(tmp, LINEAS_FILE);
    } catch (_) {
      fs.writeFileSync(LINEAS_FILE, body, 'utf-8');
      try { fs.rmSync(tmp, { force: true }); } catch (__) {}
    }
  } catch (_) {}
  try {
    const senalSync = require('./jokerbets-senal-sync.js');
    senalSync.syncDesdeExtraccion({
      pendienteStart: pendiente?.startDt || null,
      lineasMemoria: lineas,
    });
  } catch (_) {}
}

// El backend borra el .txt y deja este flag para el botón "Limpiar": si no
// vaciamos también el buffer en memoria, la próxima ronda reescribe lo viejo.
function chequearLimpiar() {
  if (!fs.existsSync(LIMPIAR_FILE)) return;
  try { fs.rmSync(LIMPIAR_FILE, { force: true }); } catch (_) {}
  lineas.length = 0;
  pendiente = null;
  horaActualKey = null;
  guardarLineas();
  log('Buffer limpiado a pedido del dashboard.');
}

let pausadoManual = false;

function chequearPausa() {
  const existe = fs.existsSync(PAUSA_FILE);
  if (existe && !pausadoManual) {
    pausadoManual = true;
    log('Pausa manual activada (sala detenida).');
    if (pendiente) {
      log('Descartando tramo abierto ' + formatMS(pendiente.startDt) + ' debido a pausa manual.');
      try {
        if (pendiente.idx >= 0 && pendiente.idx < lineas.length) {
          lineas.splice(pendiente.idx, 1);
        }
      } catch (_) {}
      pendiente = null;
      guardarLineas();
    }
    guardarEstado('pausado', 'Extracción en pausa manual (sala detenida).');
  } else if (!existe && pausadoManual) {
    pausadoManual = false;
    log('Pausa manual desactivada. Reanudando extracción y forzando F5...');
    guardarEstado('conectado', 'Reanudando extracción...');
    refrescoPendiente = false;
    ultimaSenal = Date.now();
    ultimoRefresh = Date.now();
    colaEventos = colaEventos
      .then(() => refrescarKeepAlive('reanudación manual tras pausa'))
      .catch(e => log('Error en refresh por reanudación: ' + e.message.slice(0, 80)));
  }
}

function inicioKey(l) {
  const m = /^(\d{1,2}):(\d{1,2})/.exec((l || '').trim());
  if (!m) return null;
  return pad2(Number(m[1])) + ':' + pad2(Number(m[2]));
}

function inicioKeyFromDt(dt) {
  return pad2(dt.getMinutes()) + ':' + pad2(dt.getSeconds());
}

/** Rango [ini, fin) del bloque de la hora actual en `lineas`. */
function rangoBloqueHoraActual() {
  if (!horaActualKey) return null;
  let headerIdx = -1;
  for (let i = lineas.length - 1; i >= 0; i -= 1) {
    const s = (lineas[i] || '').trim();
    if (!esHeaderHora(s)) continue;
    if (horaKeyDesdeHeader(s) === horaActualKey) {
      headerIdx = i;
      break;
    }
  }
  if (headerIdx < 0) return null;
  let fin = lineas.length;
  for (let i = headerIdx + 1; i < lineas.length; i += 1) {
    const s = (lineas[i] || '').trim();
    if (esHeaderHora(s)) {
      fin = i;
      break;
    }
  }
  return { ini: headerIdx + 1, fin };
}

/** Primer tramo cerrado de la hora con mismo MM:SS de inicio (live gana). */
function findTramoCerradoPorInicio(inicioK, excluirIdx) {
  const r = rangoBloqueHoraActual();
  if (!r || !inicioK) return -1;
  for (let i = r.ini; i < r.fin; i += 1) {
    if (i === excluirIdx) continue;
    const t = normTramo(lineas[i]);
    if (t && inicioKey(t) === inicioK) return i;
  }
  return -1;
}

/**
 * Quita tramos cerrados duplicados por inicio (MM:SS) dentro de cada hora.
 * Gana el primero (suele ser Cargar live).
 */
function sanejarDuplicadosPorInicio() {
  let i = 0;
  while (i < lineas.length) {
    const s = (lineas[i] || '').trim();
    if (!esHeaderHora(s)) {
      i += 1;
      continue;
    }
    const seen = new Set();
    let j = i + 1;
    while (j < lineas.length) {
      const t = (lineas[j] || '').trim();
      if (!t) {
        j += 1;
        continue;
      }
      if (esHeaderHora(t)) break;
      if (esEnJuego(t)) {
        j += 1;
        continue;
      }
      const nt = normTramo(t);
      if (nt) {
        const k = inicioKey(nt);
        if (k && seen.has(k)) {
          lineas.splice(j, 1);
          if (pendiente) {
            if (pendiente.idx === j) pendiente = null;
            else if (pendiente.idx > j) pendiente.idx -= 1;
          }
          continue;
        }
        if (k) seen.add(k);
      }
      j += 1;
    }
    i = j;
  }
}

function normTramo(l) {
  const m = /^(\d{1,2}):(\d{1,2})-(\d{1,2}):(\d{1,2})\s+(R|G\d?)(?:\s+(\d+))?\s*$/i.exec(
    (l || '').trim()
  );
  if (!m) return null;
  const m0 = Number(m[1]);
  const s0 = Number(m[2]);
  const m1 = Number(m[3]);
  const s1 = Number(m[4]);
  if ([m0, s0, m1, s1].some((n) => n > 59)) return null;
  const base =
    pad2(m0) + ':' + pad2(s0) + '-' + pad2(m1) + ':' + pad2(s1) +
    ' ' + String(m[5] || 'R').toUpperCase();
  return m[6] != null ? base + ' ' + m[6] : base;
}

/** Bloque de una hora tal como está en disco (tag + tramos + en juego). */
function bloqueHoraDesdeRaw(raw, tagL) {
  let idx = -1;
  for (let i = 0; i < raw.length; i += 1) {
    const s = (raw[i] || '').trim();
    if (esHeaderHora(s) && s.toLowerCase() === tagL) {
      idx = i;
      break;
    }
  }
  if (idx < 0) return null;
  const bloque = [raw[idx].trim()];
  for (let i = idx + 1; i < raw.length; i += 1) {
    const s = (raw[i] || '').trim();
    if (!s) continue;
    if (esHeaderHora(s)) break;
    if (esTramoCerrado(s) || (esEnJuego(s) && !esInterrumpido(s))) {
      bloque.push(s);
    }
  }
  return bloque.length >= 2 ? bloque : null;
}

/** Python ya mergeó en disco — recargar ese bloque en memoria (no pisar con buffer viejo). */
function reemplazarHoraDesdeArchivo(tag) {
  if (!fs.existsSync(LINEAS_FILE)) return false;
  let raw;
  try {
    raw = fs.readFileSync(LINEAS_FILE, 'utf-8').split(/\r?\n/);
  } catch (_) {
    return false;
  }
  const tagL = String(tag).trim().toLowerCase();
  const bloque = bloqueHoraDesdeRaw(raw, tagL);
  if (!bloque) return false;

  let idx = -1;
  for (let i = 0; i < lineas.length; i += 1) {
    const s = (lineas[i] || '').trim();
    if (esHeaderHora(s) && s.toLowerCase() === tagL) {
      idx = i;
      break;
    }
  }

  const vivos = [];
  let fin = lineas.length;
  let pendienteEnBloque = false;
  if (idx >= 0) {
    fin = idx + 1;
    while (fin < lineas.length) {
      const s = (lineas[fin] || '').trim();
      if (!s) {
        fin += 1;
        continue;
      }
      if (esHeaderHora(s)) break;
      if (esEnJuego(s) && !esInterrumpido(s)) {
        vivos.push(s);
        if (pendiente && pendiente.idx === fin) pendienteEnBloque = true;
      }
      fin += 1;
    }
  }

  const cuerpo = bloque.slice(1).filter((s) => esTramoCerrado(s));
  const nuevoBloque = [bloque[0], ...cuerpo, ...vivos];

  const cabeza = idx >= 0 ? lineas.slice(0, idx) : lineas.slice();
  while (cabeza.length && !(cabeza[cabeza.length - 1] || '').trim()) cabeza.pop();
  const cola = idx >= 0 ? lineas.slice(fin) : [];
  while (cola.length && !(cola[0] || '').trim()) cola.shift();

  const next = [];
  if (cabeza.length) next.push(...cabeza, '');
  next.push(...nuevoBloque);
  if (cola.length) next.push('', ...cola);

  let nuevoPendiente = null;
  if (pendienteEnBloque && pendiente) {
    const startTxt = formatMS(pendiente.startDt);
    for (let i = 0; i < next.length; i += 1) {
      const s = (next[i] || '').trim();
      if (esEnJuego(s) && s.startsWith(startTxt)) {
        nuevoPendiente = { idx: i, startDt: pendiente.startDt };
        break;
      }
    }
  } else if (pendiente && !(idx >= 0 && pendiente.idx >= idx && pendiente.idx < fin)) {
    const oldLine = lineas[pendiente.idx];
    for (let i = 0; i < next.length; i += 1) {
      if (next[i] === oldLine) {
        nuevoPendiente = { idx: i, startDt: pendiente.startDt };
        break;
      }
    }
  }

  lineas.length = 0;
  lineas.push(...next);
  pendiente = nuevoPendiente;
  return true;
}

/** Cargar live desde el dashboard: mergea/sobrescribe tramos de una hora. */
function chequearInyectar() {
  if (!fs.existsSync(INYECTAR_FILE)) return;
  let payload = null;
  try {
    payload = JSON.parse(fs.readFileSync(INYECTAR_FILE, 'utf-8'));
  } catch (_) {
    payload = null;
  }
  try { fs.rmSync(INYECTAR_FILE, { force: true }); } catch (_) {}
  if (!payload || !payload.tag) return;

  const tag = String(payload.tag).trim();
  // FastAPI ya escribió el merge en disco — priorizar eso sobre el buffer en memoria.
  if (reemplazarHoraDesdeArchivo(tag)) {
    guardarLineas();
    log('Captura sincronizada desde disco: ' + tag + '.');
    return;
  }

  if (!Array.isArray(payload.tramos)) return;
  const tagL = tag.toLowerCase();
  const nuevos = {};
  for (const raw of payload.tramos) {
    const t = normTramo(raw);
    if (!t) continue;
    const k = inicioKey(t);
    if (k) nuevos[k] = t;
  }
  if (!Object.keys(nuevos).length) return;

  let idx = -1;
  for (let i = 0; i < lineas.length; i += 1) {
    const s = (lineas[i] || '').trim();
    if (esHeaderHora(s) && s.toLowerCase() === tagL) {
      idx = i;
      break;
    }
  }

  const vivos = [];
  let fin = lineas.length;
  let pendienteEnBloque = false;
  if (idx >= 0) {
    fin = idx + 1;
    while (fin < lineas.length) {
      const s = (lineas[fin] || '').trim();
      if (!s) {
        fin += 1;
        continue;
      }
      if (esHeaderHora(s)) break;
      if (esEnJuego(s) && !esInterrumpido(s)) {
        vivos.push(s);
        if (pendiente && pendiente.idx === fin) pendienteEnBloque = true;
      }
      fin += 1;
    }
  }

  const cuerpo = Object.keys(nuevos)
    .sort()
    .map((k) => nuevos[k]);
  const bloque = [tag, ...cuerpo, ...vivos];

  const cabeza = idx >= 0 ? lineas.slice(0, idx) : lineas.slice();
  while (cabeza.length && !(cabeza[cabeza.length - 1] || '').trim()) cabeza.pop();
  const cola = idx >= 0 ? lineas.slice(fin) : [];
  while (cola.length && !(cola[0] || '').trim()) cola.shift();

  const next = [];
  if (cabeza.length) {
    next.push(...cabeza, '');
  }
  next.push(...bloque);
  if (cola.length) {
    next.push('', ...cola);
  }

  // Reindexar pendiente si el "en juego" de esta hora se conservó.
  let nuevoPendiente = null;
  if (pendienteEnBloque && pendiente) {
    const startTxt = formatMS(pendiente.startDt);
    for (let i = 0; i < next.length; i += 1) {
      const s = (next[i] || '').trim();
      if (esEnJuego(s) && s.startsWith(startTxt)) {
        nuevoPendiente = { idx: i, startDt: pendiente.startDt };
        break;
      }
    }
  } else if (pendiente && !(idx >= 0 && pendiente.idx >= idx && pendiente.idx < fin)) {
    // Pendiente de otra hora / fuera del bloque tocado: recalcular idx por texto.
    const oldLine = lineas[pendiente.idx];
    for (let i = 0; i < next.length; i += 1) {
      if (next[i] === oldLine) {
        nuevoPendiente = { idx: i, startDt: pendiente.startDt };
        break;
      }
    }
  }

  lineas.length = 0;
  lineas.push(...next);
  pendiente = nuevoPendiente;
  if (idx < 0) {
    const hk = horaKeyDesdeHeader(tag);
    if (hk) horaActualKey = hk;
  }
  guardarLineas();
  log(
    'Cargar live inyectado: ' +
      tag +
      ' · ' +
      Object.keys(nuevos).length +
      ' tramo(s) mergeados.'
  );
}

function tramoTexto(startDt, endDt, label, valor) {
  const base = formatMS(startDt) + '-' + formatMS(endDt) + ' ' + label;
  return valor === null || valor === undefined ? base : base + ' ' + valor;
}

async function registrarRonda(wheelResult, bonusResult) {
  if (pausadoManual) {
    log('Ronda recibida durante pausa manual; omitida.');
    return;
  }
  const cierre = new Date();
  const wr = String(wheelResult ?? '').toLowerCase();
  const esG = Object.prototype.hasOwnProperty.call(SPECIAL_TO_GROUP, wr);
  const label = esG ? SPECIAL_TO_GROUP[wr] : 'R';
  const valor = esG ? sumBonusResult(bonusResult) : null;

  // Este resultado es el de la ronda que se estaba jugando (la que quedó
  // pendiente al abrirse), no el de la que arranca ahora.
  if (pendiente) {
    const finDt = new Date(cierre.getTime() - 1000);
    const inicioK = inicioKeyFromDt(pendiente.startDt);
    const dupIdx = findTramoCerradoPorInicio(inicioK, pendiente.idx);
    if (dupIdx >= 0) {
      // Cargar live ya tiene ese inicio → no duplicar; quitamos "en juego".
      lineas.splice(pendiente.idx, 1);
      pendiente = null;
      log(
        'Inicio ' +
          inicioK +
          ' ya en cinta (live gana); ronda de extracción descartada.'
      );
    } else {
      lineas[pendiente.idx] = tramoTexto(pendiente.startDt, finDt, label, valor);
      pendiente = null;
    }
  } else {
    // Si no había pendiente previo (arranque, reconexión o reanudación tras pausa),
    // registramos la ronda con inicio estimado (~45s antes) para no perder este resultado.
    const startDt = new Date(cierre.getTime() - 45000);
    const finDt = new Date(cierre.getTime() - 1000);
    const inicioK = inicioKeyFromDt(startDt);
    if (findTramoCerradoPorInicio(inicioK, -1) < 0) {
      lineas.push(tramoTexto(startDt, finDt, label, valor));
      log(
        'Ronda sin pendiente previo registrada (inicio est. ' +
          formatMS(startDt) +
          '): ' +
          label +
          (valor !== null ? ' ' + valor : '')
      );
    }
  }

  // Único hueco real sin ronda en curso: si el chequeo periódico dejó pedido
  // un refresh, se hace justo acá, así nunca interrumpe una ronda en juego.
  if (refrescoPendiente && !refrescando && f5KeepAliveExtraccionActivo()) {
    refrescoPendiente = false;
    await refrescarKeepAlive('periódico, en hueco entre rondas');
  }


  const ahora = new Date();
  const horaKey = ahora.getFullYear() + '-' + ahora.getMonth() + '-' + ahora.getDate() + '-' + ahora.getHours();
  if (horaKey !== horaActualKey) {
    if (lineas.length) lineas.push('');
    lineas.push(headerDe(ahora));
    horaActualKey = horaKey;
  }

  // Abre el tramo de la ronda que arranca ahora; se completa cuando llegue su resultado.
  const inicioNuevo = inicioKeyFromDt(ahora);
  if (findTramoCerradoPorInicio(inicioNuevo, -1) >= 0) {
    pendiente = null;
    log(
      'Inicio ' +
        inicioNuevo +
        ' ya cubierto en cinta (live); no abro en juego duplicado.'
    );
  } else {
    lineas.push(formatMS(ahora) + ' en juego...');
    pendiente = { idx: lineas.length - 1, startDt: ahora };
  }

  guardarLineas();
  const valorTxt = valor === null ? '' : ' ' + valor;
  log('RONDA ' + wr + ' -> ' + label + valorTxt);
}

// ── Parser Socket.IO ──────────────────────────────────────────────────────────
// 42["event", data]  |  42/namespace,["event", data]  |  varios paquetes con \x1e
function extraerPaquetesSocketIO(raw) {
  const texto = String(raw || '');
  const partes = texto.split('\x1e');
  const out = [];
  for (const parte of partes) {
    const p = parte.trim();
    if (!p.startsWith('42')) continue;
    const m = p.match(/^42(?:\/[^,[\]]+)?,?(?:\d+)?(\[.*\])\s*$/s);
    if (m) {
      try {
        const arr = JSON.parse(m[1]);
        if (Array.isArray(arr)) out.push(arr);
      } catch (_) {}
      continue;
    }
    try {
      const arr = JSON.parse(p.slice(2));
      if (Array.isArray(arr)) out.push(arr);
    } catch (_) {}
  }
  return out;
}

function buscarPayloadRonda(obj, depth) {
  if (!obj || typeof obj !== 'object' || depth > 6) return null;
  const wr = obj.wheelResult ?? obj.wheel_result;
  if (wr != null && String(wr) !== '') return obj;
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const found = buscarPayloadRonda(item, depth + 1);
      if (found) return found;
    }
    return null;
  }
  for (const v of Object.values(obj)) {
    if (v && typeof v === 'object') {
      const found = buscarPayloadRonda(v, depth + 1);
      if (found) return found;
    }
  }
  return null;
}

function parsearSocketIO(raw) {
  const paquetes = extraerPaquetesSocketIO(raw);
  if (!paquetes.length) {
    if (String(raw).startsWith('42') && eventosWsLog < 20) {
      eventosWsLog += 1;
      log('WS 42 no parseable · ' + String(raw).slice(0, 140));
    }
    return;
  }
  for (const arr of paquetes) {
    if (!Array.isArray(arr) || !arr.length) continue;
    const evento = String(arr[0] || '');
    const payload = arr[1];
    const evNorm = evento.replace(/[_\s]/g, '').toLowerCase();
    if (evNorm === 'play' && payload?.result?.request === 'history') {
      if (eventosWsLog < 20) {
        eventosWsLog += 1;
        log('WS history ignorado');
      }
      continue;
    }
    const esRonda =
      evNorm.includes('roundend') ||
      evNorm.includes('roundresult') ||
      evNorm.includes('spinresult') ||
      evNorm.includes('gameend');
    if (!esRonda) {
      if (eventosWsLog < 20) {
        eventosWsLog += 1;
        let preview = '';
        try { preview = JSON.stringify(payload); } catch (_) { preview = String(payload); }
        log('WS evento ' + evento + ' · ' + String(preview).slice(0, 120));
      }
      continue;
    }
    const p =
      buscarPayloadRonda(payload, 0) ||
      payload?.result?.payload ||
      payload?.payload ||
      payload?.result ||
      payload;
    const wr = p && (p.wheelResult ?? p.wheel_result);
    if (wr == null || wr === '') {
      if (eventosWsLog < 20) {
        eventosWsLog += 1;
        log('WS ronda sin wheelResult · evento=' + evento + ' · ' + String(raw).slice(0, 140));
      }
      continue;
    }
    ultimaRonda = Date.now();
    colaEventos = colaEventos
      .then(() => registrarRonda(wr, p.bonusResult ?? p.bonus_result))
      .catch(e => log('Error registrando ronda (continuando): ' + e.message.slice(0, 80)));
  }
}

function adjuntarAPage(page, onSignal, onConectado, cuentaId) {
  if (cuentaId) pageCuentaMap.set(page, cuentaId);
  page.on('websocket', ws => {
    const wsUrl = ws.url();
    if (!esWsJuego(wsUrl)) return;
    let pageUrl = '';
    try { pageUrl = page.url(); } catch (_) {}
    const basura = esPaginaBasura(pageUrl);
    paginaWsJuego = page;
    recordarUrlMesa(pageUrl);
    wsConectadoDesde = wsConectadoDesde || Date.now();
    if (basura) {
      log('WS Skywind en anuncio/tracker (escucho rondas): ' + pageUrl.slice(0, 90));
    } else {
      log('WS juego conectado · ' + pageUrl.slice(0, 90));
      wsJuegoAbiertos += 1;
      fallosF5Seguidos = 0;
      guardarEstado('conectado', 'Conexión exitosa a Jokers, comienza la extracción.');
      if (onConectado) onConectado(page);
    }

    ws.on('framereceived', frame => {
      const cid = pageCuentaMap.get(page);
      if (contextsMulti && activeCuentaId && cid && cid !== activeCuentaId) return;
      framesWs += 1;
      const raw = typeof frame.payload === 'string'
        ? frame.payload
        : Buffer.from(frame.payload).toString('utf-8');
      if (!basura) {
        onSignal();
        lastFrameAt = Date.now();
      }
      if (!raw.startsWith('42')) {
        if (eventosWsLog < 8 && raw && !/^[\d]+$/.test(raw) && raw !== '2' && raw !== '3') {
          eventosWsLog += 1;
          log('WS frame no-42 · ' + String(raw).slice(0, 80));
        }
        return;
      }
      parsearSocketIO(raw);
    });
    ws.on('close', () => {
      if (basura) return;
      log('WS juego cerrado');
      wsJuegoAbiertos = Math.max(0, wsJuegoAbiertos - 1);
    });
  });
}

function wireContextPages(context, cuentaId) {
  const pagesAdjuntas = new WeakSet();
  const registrarSenal = () => { ultimaSenal = Date.now(); };
  function adjuntar(p) {
    if (!p || pagesAdjuntas.has(p)) return;
    pagesAdjuntas.add(p);
    adjuntarAPage(p, registrarSenal, pagina => {
      paginaJuego = pagina;
      ultimaSenal = Date.now();
      recordarUrlMesa((() => { try { return pagina.url(); } catch (_) { return ''; } })());
      actualizarEstadoCuentas();
    }, cuentaId);
    p.on('close', () => { if (p === paginaJuego) paginaJuego = null; });
    try {
      if (!paginaJuego && !esPaginaBasura(p.url())) paginaJuego = p;
    } catch (_) {}
  }
  for (const p of context.pages()) adjuntar(p);
  context.on('page', p => adjuntar(p));
}

function arrancarTimers() {
  const chequeoTimer = setInterval(() => {
    if (pausadoManual) {
      ultimoRefresh = Date.now();
      ultimaSenal = Date.now();
      ultimaRonda = Date.now();
      return;
    }
    if (
      contextsMulti &&
      framesWs > 0 &&
      lastFrameAt &&
      Date.now() - lastFrameAt > FAILOVER_WS_MS
    ) {
      elegirFailover();
    }
    sincronizarEstadoCuentasPorPulso(lastBotEstadoExtra);
    if (Date.now() - ultimoDiag >= 60000) {
      ultimoDiag = Date.now();
      log(
        'diag ' + EXTRACTOR_REV +
        ' · frames=' + framesWs +
        ' · wsAbiertos=' + wsJuegoAbiertos +
        ' · fuente=' + (activeCuentaId || '-') +
        ' · urlMesa=' + (ultimaUrlMesa || '-').slice(0, 70) +
        ' · pestañas=' + urlsAbiertas()
      );
    }
    if (!paginaJuego) {
      const alt = paginaParaF5();
      if (alt) paginaJuego = alt;
    }
    soltarPendienteColgado();
    if (f5KeepAliveExtraccionActivo()) {
      const sinRefresh = Date.now() - ultimoRefresh;
      const sinDatos = Date.now() - ultimaSenal;
      const esperaPrimera = !ultimaRonda;
      const anclaRonda = esperaPrimera
        ? Math.max(wsConectadoDesde || ultimoRefresh, ultimoRefresh)
        : ultimaRonda;
      const limiteRonda = esperaPrimera ? PRIMERA_RONDA_MS : F5_INTERVAL;
      const sinRonda = Date.now() - anclaRonda;
      const wsVivo = wsJuegoAbiertos > 0;
      if (anclaRonda && sinRonda >= limiteRonda) {
        refrescoPendiente = false;
        colaEventos = colaEventos
          .then(() => refrescarKeepAlive(
            esperaPrimera ? 'watchdog: 90s sin primera ronda' : 'watchdog: sin rondas > 8 min'
          ))
          .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
        if (esperaPrimera) wsConectadoDesde = Date.now();
        return;
      }
      if (sinDatos >= SILENCIO_MAX && !wsVivo) {
        refrescoPendiente = false;
        ultimaSenal = Date.now();
        colaEventos = colaEventos
          .then(() => refrescarKeepAlive('watchdog: WS cerrado > 3 min'))
          .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
      } else if (sinRefresh >= F5_MAX && !wsVivo) {
        refrescoPendiente = false;
        colaEventos = colaEventos
          .then(() => refrescarKeepAlive('watchdog: limite duro, WS cerrado'))
          .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
      } else if (sinRefresh >= F5_INTERVAL) {
        refrescoPendiente = true;
      }
    }
  }, 15000);

  const limpiarTimer = setInterval(chequearLimpiar, 1000);
  const inyectarTimer = setInterval(chequearInyectar, 1000);
  const pausaTimer = setInterval(chequearPausa, 1000);

  return { chequeoTimer, limpiarTimer, inyectarTimer, pausaTimer };
}

async function mainJokerbets() {
  const cuentas = leerJokerbetsCuentas();
  if (!cuentas || cuentas.length < 3) {
    guardarEstado('error', 'Faltan las 3 URLs en Cuentas → URLs (jokerbets/config.json).');
    process.exit(1);
  }
  const sinUrl = cuentas.filter(c => !c.url);
  if (sinUrl.length) {
    guardarEstado('error', 'Cada cuenta (rojo/azul/verde) necesita URL en config.');
    process.exit(1);
  }

  cargarBufferExistente();
  asegurarHoraReloj();
  log('jokerbets multi ' + EXTRACTOR_REV + ' · 3 perfiles Chrome');
  try {
    fs.writeFileSync(PID_FILE, String(process.pid), 'utf-8');
  } catch (_) {}

  const chromePath = buscarChrome();
  if (!chromePath) {
    guardarEstado('error', 'No se encontro Chrome instalado en este equipo.');
    process.exit(1);
  }

  guardarEstado(
    'esperando',
    'Abriendo 3 Chrome (rojo/azul/verde). Iniciá sesión en cada uno si hace falta.'
  );

  const primaria = cuentas.find(c => c.wsPrimaria) || cuentas[1] || cuentas[0];
  activeCuentaId = primaria.id;
  cuentasFailoverOrden = [
    primaria.id,
    ...cuentas.filter(c => c.id !== primaria.id).map(c => c.id),
  ];
  lastFrameAt = Date.now();
  let cerrando = false;

  contextsMulti = [];
  for (const c of cuentas) {
    const perfil = path.join(DIR, 'perfiles', c.id);
    try { fs.mkdirSync(perfil, { recursive: true }); } catch (_) {}
    limpiarLocksHuerfanos(perfil);
    const chromeArgs = [
      '--start-maximized',
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
    ];
    const ctx = await chromium.launchPersistentContext(perfil, {
      headless: false,
      executablePath: chromePath,
      args: chromeArgs,
      ignoreDefaultArgs: ['--enable-automation'],
      viewport: null,
    });
    await ctx.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      window.chrome = { runtime: {} };
    });
    contextsMulti.push({ cuenta: c, context: ctx });
    wireContextPages(ctx, c.id);
    let page = ctx.pages()[0];
    if (!page) page = await ctx.newPage();
    if (c.url) {
      try {
        log('Goto ' + c.color + ' · ' + c.url.slice(0, 100));
        await page.goto(c.url, { waitUntil: 'commit', timeout: 90000 });
      } catch (e) {
        log('Goto ' + c.color + ' falló: ' + String(e.message || e).slice(0, 100));
      }
    }
    ctx.on('close', () => {
      const vivos = contextsMulti.filter(x => {
        try {
          return x.context.pages().some(p => !p.isClosed());
        } catch (_) {
          return false;
        }
      });
      if (!vivos.length && !cerrando) {
        log('Los 3 Chrome se cerraron.');
        borrarPid();
        guardarEstado('detenido', 'Chrome cerrado. Volvé a iniciar extracción.');
        process.exit(0);
      }
    });
  }

  const slotPrim = contextsMulti.find(x => x.cuenta.id === activeCuentaId);
  contextRef = slotPrim ? slotPrim.context : contextsMulti[0].context;
  actualizarEstadoCuentas();
  try {
    require('./jokerbets-log.js').bumpUiPulse('extraccion_arranque', {});
  } catch (_) {}

  function borrarPid() {
    try { fs.unlinkSync(PID_FILE); } catch (_) {}
    try { fs.unlinkSync(PAUSA_FILE); } catch (_) {}
    try { fs.unlinkSync(CUENTAS_ESTADO_FILE); } catch (_) {}
  }
  async function apagar() {
    if (cerrando) return;
    cerrando = true;
    if (botInterval) clearInterval(botInterval);
    if (senalSyncTimer) clearInterval(senalSyncTimer);
    if (f5RotacionTimer) clearInterval(f5RotacionTimer);
    borrarPid();
    guardarEstado('detenido', 'Extracción detenida.');
    for (const { context } of contextsMulti || []) {
      try { await context.close(); } catch (_) {}
    }
    contextsMulti = null;
    process.exit(0);
  }

  const { chequeoTimer, limpiarTimer, inyectarTimer, pausaTimer } = arrancarTimers();

  try {
    const { startBotLoop, botArmado } = require('./jokerbets-bot.js');
    try {
      const senalSync = require('./jokerbets-senal-sync.js');
      senalSync.syncDesdeExtraccion({
        pendienteStart: pendiente?.startDt || null,
        lineasMemoria: lineas,
      });
      senalSyncTimer = setInterval(() => {
        try {
          senalSync.syncDesdeExtraccion({
            pendienteStart: pendiente?.startDt || null,
            lineasMemoria: lineas,
          });
        } catch (_) {}
      }, 2000);
    } catch (_) {}

    botInterval = startBotLoop(contextsMulti, (estadoBot, senal, apuestaOk, manual) => {
      for (const [id, st] of estadoBot.porCuenta.entries()) {
        botRuntimeByCuenta[id] = st;
      }
      let manualEst = manual;
      try {
        if (!manualEst) manualEst = require('./jokerbets-manual.js').leerManual();
      } catch (_) {}
      lastBotEstadoExtra = {
        botArmado: botArmado(),
        apuestaOk,
        manual: manualEst,
        senal: {
          interruptor: senal.interruptor,
          enZona: senal.enZona,
          puertaA: senal.puertaA,
          permitirClics: senal.permitirClics,
          tip: senal.tip,
          enCurso: senal.enCurso,
        },
      };
    });
  } catch (e) {
    log('Bot C no cargó: ' + String(e.message || e).slice(0, 80));
  }

  iniciarF5Rotacion();

  process.on('SIGINT', () => {
    clearInterval(chequeoTimer);
    clearInterval(limpiarTimer);
    clearInterval(inyectarTimer);
    clearInterval(pausaTimer);
    if (botInterval) clearInterval(botInterval);
    if (senalSyncTimer) clearInterval(senalSyncTimer);
    if (f5RotacionTimer) clearInterval(f5RotacionTimer);
    apagar();
  });
  process.on('SIGTERM', apagar);
  process.on('SIGBREAK', apagar);
  process.on('uncaughtException', e => log('ERROR (continuando): ' + e.message));
  process.on('unhandledRejection', r => log('Promise rechazada (continuando): ' + String(r).slice(0, 80)));

  await new Promise(() => {});
}

// ── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  cargarBufferExistente();
  asegurarHoraReloj();
  log('extractor ' + EXTRACTOR_REV + ' · si no ves esta linea, este PC tiene un .js viejo');
  try {
    fs.writeFileSync(PID_FILE, String(process.pid), 'utf-8');
  } catch (_) {}
  guardarEstado('esperando', 'Esperando (' + EXTRACTOR_REV + '): abrí el Jokers Wheel en esta ventana de Chrome.');

  const chromePath = buscarChrome();
  const primeraVez = !fs.existsSync(PERFIL_DIR);

  if (!chromePath) {
    guardarEstado('error', 'No se encontro Chrome instalado en este equipo.');
    process.exit(1);
  }
  if (primeraVez) {
    guardarEstado('esperando', 'Primera vez: se abrió Chrome. Entrá al casino que quieras, iniciá sesión y abrí el Jokers Wheel.');
  } else {
    limpiarLocksHuerfanos();
  }

  const context = await chromium.launchPersistentContext(PERFIL_DIR, {
    headless: false,
    executablePath: chromePath,
    args: ['--start-maximized', '--disable-blink-features=AutomationControlled', '--no-first-run', '--no-default-browser-check'],
    ignoreDefaultArgs: ['--enable-automation'],
    viewport: null,
  });
  contextRef = context;

  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
  });

  const registrarSenal = () => { ultimaSenal = Date.now(); };

  // Se pega a cualquier pestaña (presente o futura) y espera a que alguna
  // hable con el WS de Skywind; no navega a ningún casino en particular.
  const pagesAdjuntas = new WeakSet();
  function adjuntar(p) {
    if (!p || pagesAdjuntas.has(p)) return;
    pagesAdjuntas.add(p);
    adjuntarAPage(p, registrarSenal, pagina => {
      paginaJuego = pagina;
      ultimaSenal = Date.now();
      recordarUrlMesa((() => { try { return pagina.url(); } catch (_) { return ''; } })());
    });
    p.on('close', () => { if (p === paginaJuego) paginaJuego = null; });
    try {
      if (!paginaJuego && !esPaginaBasura(p.url())) paginaJuego = p;
    } catch (_) {}
  }
  if (context.pages().length === 0) await context.newPage();
  for (const p of context.pages()) adjuntar(p);
  context.on('page', p => adjuntar(p));

  // Si el usuario cierra esta ventana de Chrome a mano, el proceso Node debe
  // terminar (no seguir vivo escuchando nada): así el backend detecta que ya
  // no está "corriendo" y el botón puede volver a abrirla.
  context.on('close', () => {
    if (cerrando) return;
    log('La ventana de Chrome se cerró.');
    borrarPid();
    guardarEstado('detenido', 'Se cerró la ventana de Chrome. Apretá "Comenzar extracción" para abrirla de nuevo.');
    process.exit(0);
  });

  // Chequeo cada 15s: el F5 periódico (F5_INTERVAL) espera el hueco entre
  // rondas vía registrarRonda(). F5 forzado solo si el WS del juego ya se cerró.
  const chequeoTimer = setInterval(() => {
    if (pausadoManual) {
      ultimoRefresh = Date.now();
      ultimaSenal = Date.now();
      ultimaRonda = Date.now();
      return;
    }
    try {
      for (const p of context.pages()) adjuntar(p);
    } catch (_) {}
    if (Date.now() - ultimoDiag >= 60000) {
      ultimoDiag = Date.now();
      log(
        'diag ' + EXTRACTOR_REV +
        ' · frames=' + framesWs +
        ' · wsAbiertos=' + wsJuegoAbiertos +
        ' · urlMesa=' + (ultimaUrlMesa || '-').slice(0, 70) +
        ' · pestañas=' + urlsAbiertas()
      );
    }
    if (!paginaJuego) {
      const alt = paginaParaF5();
      if (alt) paginaJuego = alt;
    }
    soltarPendienteColgado();
    const sinRefresh = Date.now() - ultimoRefresh;
    const sinDatos   = Date.now() - ultimaSenal;
    const esperaPrimera = !ultimaRonda;
    const anclaRonda = esperaPrimera
      ? Math.max(wsConectadoDesde || ultimoRefresh, ultimoRefresh)
      : ultimaRonda;
    const limiteRonda = esperaPrimera ? PRIMERA_RONDA_MS : F5_INTERVAL;
    const sinRonda = Date.now() - anclaRonda;
    const wsVivo = wsJuegoAbiertos > 0;
    if (anclaRonda && sinRonda >= limiteRonda) {
      refrescoPendiente = false;
      colaEventos = colaEventos
        .then(() => refrescarKeepAlive(
          esperaPrimera ? 'watchdog: 90s sin primera ronda' : 'watchdog: sin rondas > 8 min'
        ))
        .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
      if (esperaPrimera) wsConectadoDesde = Date.now();
      return;
    }
    if (sinDatos >= SILENCIO_MAX && !wsVivo) {
      refrescoPendiente = false;
      ultimaSenal = Date.now();
      colaEventos = colaEventos
        .then(() => refrescarKeepAlive('watchdog: WS cerrado > 3 min'))
        .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
    } else if (sinRefresh >= F5_MAX && !wsVivo) {
      refrescoPendiente = false;
      colaEventos = colaEventos
        .then(() => refrescarKeepAlive('watchdog: limite duro, WS cerrado'))
        .catch(e => log('Error en refresh forzado (continuando): ' + e.message.slice(0, 80)));
    } else if (sinRefresh >= F5_INTERVAL) {
      refrescoPendiente = true;
    }
  }, 15000);

  const limpiarTimer = setInterval(chequearLimpiar, 1000);
  const inyectarTimer = setInterval(chequearInyectar, 1000);
  const pausaTimer = setInterval(chequearPausa, 1000);

  let cerrando = false;
  function borrarPid() {
    try { fs.unlinkSync(PID_FILE); } catch (_) {}
    try { fs.unlinkSync(PAUSA_FILE); } catch (_) {}
  }
  async function apagar() {
    if (cerrando) return;
    cerrando = true;
    clearInterval(chequeoTimer);
    clearInterval(limpiarTimer);
    clearInterval(inyectarTimer);
    clearInterval(pausaTimer);
    borrarPid();
    guardarEstado('detenido', 'Extracción detenida.');
    try { await context.close(); } catch (_) {}
    process.exit(0);
  }
  process.on('SIGINT', apagar);
  process.on('SIGTERM', apagar);
  process.on('SIGBREAK', apagar);
  process.on('uncaughtException', e => log('ERROR (continuando): ' + e.message));
  process.on('unhandledRejection', r => log('Promise rechazada (continuando): ' + String(r).slice(0, 80)));

  await new Promise(() => {});
}

function arrancar() {
  if (process.env.JOKERBETS_MULTI === '1') return mainJokerbets();
  return main();
}

arrancar().catch(e => {
  try { fs.unlinkSync(PID_FILE); } catch (_) {}
  guardarEstado('error', String(e.message || e));
  console.error('Fatal:', e.message);
  process.exit(1);
});
