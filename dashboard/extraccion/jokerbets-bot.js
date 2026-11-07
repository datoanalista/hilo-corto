const fs = require('fs');
const path = require('path');
const dom = require('./jokerbets-dom.js');
const jlog = require('./jokerbets-log.js');
const alog = require('./jokerbets-analisis-log.js');
const manualMod = require('./jokerbets-manual.js');

const DIR = __dirname;
const SENAL_FILE = path.join(DIR, 'jokerbets-senal.json');
const SIM_POOL7_FILE = path.join(DIR, 'jokerbets-simul-pool7.json');
const BOT_FILE = path.join(DIR, 'jokerbets-bot-armado.json');
const TRACE_FILE = path.join(DIR, 'jokerbets-bot.trace.jsonl');
const CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');

const MIN_MS_ENTRE_APUESTA = 2_500;
const MANUAL_POST_CLIC_MS = 80;
const MIN_MS_ENTRE_COLOR = 450;
/** Tras cambio de enCurso (timer tiro): ~6 s abre apuesta, ~10 s de margen. */
const EN_CURSO_DELAY_MS = 6_000;
const EN_CURSO_APUESTA_MS = 10_000;
/**
 * F5 solo alarma:
 * · Cada 6 min: si reloj oficial (Brillo) va ≥5 min por delante de enCurso (Go!) → F5×3.
 * · Disculpe/506/99501 en DOM → F5 inmediato; si persiste → cada 3 min (modo origen).
 * · Overlay Play en hora floja → clic play, no F5 (evita falsos positivos).
 */
const INTERVALO_DESFASE_MS = 6 * 60 * 1000;
const DESFASE_EN_CURSO_MIN = 5;
const F5_ORIGEN_DISULPE_MS = 3 * 60 * 1000;
const PLAY_HORA_FLOJA_MS = 10 * 60 * 1000;
const MIN_MS_ENTRE_F5_MANT = 45 * 1000;
const FRAME_CACHE_MS = 6 * 1000;
const MAX_INTENTOS_BONO = 4;
const APUESTA_OBJETIVO = { '50': 200, '150': 600, '200': 800 };
/** Freno de emergencia: standby apuestas hasta la hora siguiente (tag). */
const FREN0_EMERGENCIA_USD = 6000;

function normalizarApuestaModo(modo) {
  const m = String(modo || '50').replace(/\s/g, '');
  if (m === '150' || m === '200') return m;
  return '50';
}

function montoPorBonoModo(modoAp) {
  const m = normalizarApuestaModo(modoAp);
  if (m === '200') return 200;
  if (m === '150') return 150;
  return 50;
}
/** Manual = 1× centro → $50×4 bonos = $200. Auto SIM = modo 50 · Prod Puerta A = modo 200. */
const CLICS_CENTRO_MANUAL = 1;

function leerApuestaModoConfig() {
  try {
    if (!fs.existsSync(CONFIG_FILE)) return '50';
    const raw = fs.readFileSync(CONFIG_FILE, 'utf-8').replace(/^\uFEFF/, '');
    const cfg = JSON.parse(raw);
    return normalizarApuestaModo(cfg.apuestaModo);
  } catch (_) {
    return '50';
  }
}

/** Go Brillo + armado → $200. Si no, SIM Pool7 → $50. Else Puerta A → $200. */
function apuestaModoAuto(senal) {
  if (botArmado() && senal?.puertaGoBrillo) return '200';
  if (senal?.simulPool7) return '50';
  return '200';
}

function clicsCentroAuto(senal) {
  const m = apuestaModoAuto(senal);
  if (m === '200') return 4;
  if (m === '150') return 3;
  return 1;
}

function bonoColorCuenta(cuenta) {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      const id = cfg.activeNotebookId || cfg.notebooks?.[0]?.id;
      const nb = (cfg.notebooks || []).find(n => n.id === id) || cfg.notebooks?.[0];
      const row = (nb?.cuentas || []).find(c => c.id === cuenta.id);
      const bc = String(row?.bonoColor || row?.color || '').toLowerCase();
      if (bc === 'rojo' || bc === 'azul' || bc === 'verde') return bc;
    }
  } catch (_) {}
  const bc = String(cuenta.bonoColor || cuenta.color || '').toLowerCase();
  if (bc === 'rojo' || bc === 'azul' || bc === 'verde') return bc;
  return cuenta.color;
}

function traceBot(cuentaColor, evento, detalle) {
  const line =
    JSON.stringify({
      ts: new Date().toISOString(),
      color: cuentaColor || null,
      evento,
      detalle: detalle || '',
    }) + '\n';
  try {
    fs.appendFileSync(TRACE_FILE, line, 'utf-8');
  } catch (_) {}
}

function leerJson(file, fallback) {
  try {
    if (!fs.existsSync(file)) return fallback;
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (_) {
    return fallback;
  }
}

function botArmado() {
  const j = leerJson(BOT_FILE, { armado: false });
  return Boolean(j.armado);
}

function leerSenal() {
  const defaults = {
    permitirClics: false,
    puertaA: false,
    formaGApuesta: false,
    viaApuesta: null,
    enZona: false,
    enZonaApuesta: false,
    enCurso: '',
    interruptor: 'OFF',
    simulPool7: false,
    pool7BrilloOk: false,
    puertaGoBrillo: false,
    ventanaCaliente: false,
    gapTiro: null,
    confirmadoHasta: -1,
    nTiros: 0,
    brilloFp: '',
    relojMinuto: null,
    relojSegundo: null,
  };
  let s = leerJson(SENAL_FILE, defaults);
  const simF = leerJson(SIM_POOL7_FILE, { activo: false });
  const simulOn = Boolean(simF.activo);

  let live = null;
  try {
    live = require('./jokerbets-senal-sync.js').buildSenalPool7();
  } catch (_) {}

  if (live) {
    if (simulOn) {
      s = {
        ...s,
        ...live,
        simulPool7: true,
        brilloFp: s.brilloFp || live.brilloFp || '',
        confirmadoHasta:
          s.confirmadoHasta != null && s.confirmadoHasta >= 0
            ? s.confirmadoHasta
            : live.confirmadoHasta,
      };
    } else {
      s.relojMinuto = live.relojMinuto ?? s.relojMinuto;
      s.relojSegundo = live.relojSegundo ?? s.relojSegundo;
      s.tip = live.tip ?? s.tip;
      s.enCurso = live.enCurso || s.enCurso;
      s.tag = live.tag || s.tag;
      s.enZonaApuesta = live.enZonaApuesta ?? s.enZonaApuesta;
      s.simulPool7 = false;
      s.viaApuesta = s.viaApuesta === 'sim' ? null : s.viaApuesta;
    }
  }

  s.simulPool7 = simulOn;
  return s;
}

/** Minutos 0–59.999 del reloj oficial de la hora (Brillo / live.reloj). */
function minutosRelojOficial(senal) {
  const rm = Number(senal.relojMinuto);
  const rs = Number(senal.relojSegundo ?? 0);
  if (!Number.isFinite(rm)) return null;
  return rm + (Number.isFinite(rs) ? rs : 0) / 60;
}

/**
 * Cuántos minutos va atrasado enCurso (Go!) respecto al reloj oficial.
 * Positivo = la cinta no avanza el tiro abierto; null = no se puede medir.
 */
function desfaseEnCursoAtrasadoMin(senal) {
  const mEc = minutoDesdeEnCurso(senal.enCurso);
  const mRel = minutosRelojOficial(senal);
  if (mEc == null || mRel == null) return null;
  let lag = mRel - mEc;
  if (lag < -45) lag += 60;
  return lag;
}

/** Latido de extracción/dashboard — no confundir con enCurso (tiro abierto en cinta). */
function clavePulsoCinta(senal) {
  const tag = String(senal.tag || '').trim().toLowerCase();
  const conf = senal.confirmadoHasta ?? -1;
  const n = senal.nTiros ?? 0;
  const gap = senal.gapTiro ?? 'x';
  const fp = String(senal.brilloFp || '').slice(0, 48);
  return tag + '|c' + conf + '|n' + n + '|g' + gap + '|b' + fp;
}

async function gameFrameCached(estadoBot, page) {
  if (!page || page.isClosed()) return null;
  let url = '';
  try {
    url = page.url();
  } catch (_) {
    return null;
  }
  const c = estadoBot.frameCache;
  if (c && c.url === url && Date.now() - c.at < FRAME_CACHE_MS) {
    return c.frame;
  }
  const frame = await dom.findGameFrame(page);
  estadoBot.frameCache = { url, frame, at: Date.now() };
  return frame;
}

function invalidarFrameCache(estadoBot) {
  estadoBot.frameCache = null;
}

function minutoDesdeEnCurso(enCurso) {
  const s = String(enCurso || '').trim();
  let m = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(s);
  if (m) return Number(m[2]) + Number(m[3]) / 60;
  m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (m) return Number(m[1]) + Number(m[2]) / 60;
  return null;
}

/** Banda tip±1 (display / Puerta A). */
function enZonaPool7(enCurso, tip) {
  if (!enCurso || tip == null || Number.isNaN(Number(tip))) return false;
  const m = minutoDesdeEnCurso(enCurso);
  if (m == null) return false;
  const minTiro = Math.floor(m);
  const d = Math.abs((minTiro % 60) - (Number(tip) % 60));
  return Math.min(d, 60 - d) <= 1;
}

/** Disparo auto — sync tipProxima.enZonaApuestaPool7 (tip±1: 44–46 si tip=45). */
function enZonaApuestaPool7(enCurso, tip) {
  return enZonaPool7(enCurso, tip);
}

function senalEnZonaTip(senal, tip) {
  const t = tip != null ? Number(tip) : senal.tip;
  if (t == null || Number.isNaN(t)) return false;
  const curso = String(senal.enCurso || '').trim();
  if (!curso) return false;
  return enZonaApuestaPool7(curso, t);
}

function senalEnZona(senal) {
  return senalEnZonaTip(senal, senal.tip);
}

function parseApuestaNum(apuestaLeida) {
  if (apuestaLeida == null || apuestaLeida === '') return null;
  const s = String(apuestaLeida).replace(/[^\d.]/g, '');
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Apuesta confirmada en barra (capturas apuesta-scan: $200 = 4×$50 centro). */
function apuestaManualDesdeMonto(montoPorBono) {
  const m = manualMod.normalizarMontoPorBono(montoPorBono);
  return {
    montoBono: m,
    clics: m / 50,
    objetivo: m * 4,
  };
}

function apuestaObjetivoModo(modoAp) {
  const m = normalizarApuestaModo(modoAp);
  return APUESTA_OBJETIVO[m] || 200;
}

function apuestaBloqueadaFreno(st, tag) {
  if (!st.frenoEmergencia) return false;
  const t = String(tag || '').toLowerCase();
  return t === String(st.frenoDesdeTag || st.horaTag || '').toLowerCase();
}

function evaluarFrenoEmergencia(st, saldoNum, tag, cuenta, senal) {
  if (saldoNum == null) return;
  if (saldoNum <= FREN0_EMERGENCIA_USD && !st.frenoEmergencia) {
    st.frenoEmergencia = true;
    st.frenoDesdeTag = String(tag || '').toLowerCase();
    alog.registrarFrenoEmergencia({
      cuenta,
      senal,
      st,
      saldo: saldoNum,
      activo: true,
      notas: 'saldo<=' + FREN0_EMERGENCIA_USD + ' standby hasta otra hora',
    });
    traceBot(cuenta.color, 'freno-emergencia-on', 'saldo=' + saldoNum);
  }
}

function apuestaConfirmadaDom(apuestaAntes, apuestaDespues, objetivo = 200) {
  const desp = parseApuestaNum(apuestaDespues);
  if (desp == null || desp <= 0) return false;
  const ant = parseApuestaNum(apuestaAntes);
  /** Barra ya en objetivo (ronda anterior / lectura fantasma): no contar sin subida. */
  if (ant != null && ant >= objetivo && desp >= objetivo && desp <= ant) return false;
  if (desp >= objetivo) return true;
  if (ant == null || ant <= 0) return desp >= Math.min(50, objetivo);
  return desp > ant;
}

function enZonaApuestaDesdeSenal(senal) {
  if (typeof senal.enZonaApuesta === 'boolean') return senal.enZonaApuesta;
  return senalEnZona(senal);
}

function claveApuestaTagTip(tag, tip) {
  return String(tag || '') + '|tip' + String(tip ?? '?');
}

/** Una apuesta confirmada por minuto de piso en ventana Pool7 tip±1 (ej. m17 m18 m19). */
function claveApuestaTagMinuto(tag, minPiso) {
  return String(tag || '') + '|m' + String(minPiso ?? '?');
}

function resetHoraCuenta(st, tag, cuenta, senal) {
  const t = String(tag || '').toLowerCase();
  if (st.horaTag === t) return;
  if (st.frenoEmergencia && st.horaTag) {
    alog.registrarFrenoEmergencia({
      cuenta,
      senal,
      st,
      saldo: alog.parseSaldo(st.ultimoSaldo),
      activo: false,
      notas: 'nueva hora ' + t,
    });
    st.frenoEmergencia = false;
    st.frenoDesdeTag = '';
  }
  st.horaTag = t;
  st.tipsHechos = new Set();
  st.lastApuestaAtByKey = {};
  st.centroPulsadoKeys = new Set();
  st.apuestaBaselineByKey = {};
  st.centroClicadoEnRonda = false;
  st._enCursoVisto = '';
  st._enCursoVistoAt = 0;
  st._bonoEnPantalla = false;
  st._bonoEpisodio = 0;
  st._bonoColorOk = false;
  st._bonoIntentos = 0;
  st.lastDecisionKey = '';
  st._bonoTraceAt = 0;
}

/** Encola clic de color en TOMA TU DECISIÓN (episodio = cada entrada nueva a la pantalla). */
function encolarBonoSiCorresponde({ cuenta, page, frame, st, perm, senal, colaBono, ahora }) {
  if (!perm.color) return;
  const was = !!st._bonoEnPantalla;
  if (!was) {
    st._bonoEpisodio = (st._bonoEpisodio || 0) + 1;
    st._bonoColorOk = false;
    st._bonoIntentos = 0;
    st.lastDecisionKey = '';
    traceBot(
      cuenta.color,
      'bono-detect',
      'pantalla TOMA TU DECISIÓN · episodio=' + st._bonoEpisodio
    );
    st._bonoTraceAt = ahora;
  }
  st._bonoEnPantalla = true;

  const key = (senal.tag || '') + '|bono-e' + String(st._bonoEpisodio || 0);
  const intentosOk = (st._bonoIntentos || 0) < MAX_INTENTOS_BONO;
  const puedeReintentar = !st._bonoColorOk && intentosOk;
  const cooldownOk = ahora - (st.lastColorAt || 0) > MIN_MS_ENTRE_COLOR;

  if (puedeReintentar && cooldownOk) {
    colaBono.push({ cuenta, page, frame, st, perm, senal, key, ahora });
  } else if (puedeReintentar && !cooldownOk && !st._bonoCooldownTraceAt) {
    st._bonoCooldownTraceAt = ahora;
    traceBot(cuenta.color, 'bono-espera-cooldown', 'ms=' + (ahora - (st.lastColorAt || 0)));
  } else if (!intentosOk && !st._bonoTopeTraceAt) {
    st._bonoTopeTraceAt = ahora;
    traceBot(cuenta.color, 'bono-skip', 'tope intentos episodio=' + (st._bonoEpisodio || 0));
  }
}

/**
 * Fin de ronda: barra APUESTA vuelve a ~0 → se puede volver a apostar.
 * Mientras barra ≥ objetivo, no apilar clics (evita $200→$900 en la misma ronda).
 */
function sincronizarEstadoRondaApuesta(st, apuestaStr, objetivo) {
  const cur = parseApuestaNum(apuestaStr);
  const prev = parseApuestaNum(st.domPrev?.apuesta);
  if (cur != null && cur < 25) {
    st.centroClicadoEnRonda = false;
  }
  if (prev != null && prev >= 50 && cur != null && cur < 25) {
    if (st.apuestaBaselineByKey) {
      for (const k of Object.keys(st.apuestaBaselineByKey)) {
        if (!st.tipsHechos.has(k)) delete st.apuestaBaselineByKey[k];
      }
    }
  }
  if (cur != null && cur >= objetivo) {
    st.ultimaApuestaAltaEnBarra = cur;
  }
}

/**
 * ¿Omitir clic al centro? Solo si el minuto ya quedó confirmado en barra/bonos.
 * No bloquear por “clic Playwright enviado” (antes quemaba el minuto con APUESTA=0).
 */
async function omitirClicApuesta(st, autoKey, apuestaAntes, objetivo, frame, montoBono) {
  if (st.tipsHechos.has(autoKey)) {
    return { omitir: true, why: 'slot-ya-hecho', marcar: false };
  }
  if (apuestaAntes != null && apuestaAntes >= objetivo) {
    return { omitir: true, why: 'barra-ya-objetivo', marcar: true };
  }
  const bonos = await dom.verificarApuestaCentroBonos(frame, montoBono);
  if (bonos.ok) {
    return {
      omitir: true,
      why: 'bonos-4x' + montoBono + ' (' + bonos.detalle + ')',
      marcar: true,
    };
  }
  return { omitir: false, why: 'pulsar-centro' };
}

function marcarSlotApuestaHecho(st, autoKey, cuenta, detalle) {
  st.tipsHechos.add(autoKey);
  st.ultimoGesto = 'auto-apuesta-ya-colocada';
  traceBot(cuenta.color, 'apuesta-ya-colocada', 'key=' + autoKey + ' · ' + detalle);
}

function minutoTiroPiso(senal) {
  const m = minutoDesdeEnCurso(senal.enCurso);
  return m == null ? null : Math.floor(m);
}

function poolTipDesdeSenal(senal) {
  const t = senal.tip != null ? Number(senal.tip) : null;
  return t != null && !Number.isNaN(t) ? t : null;
}

/** Una apuesta por cambio del timer de tiro (caluga enCurso), no por minuto de pared. */
function claveApuestaEnCurso(tag, enCurso) {
  return String(tag || '') + '|curso|' + String(enCurso || '').trim();
}

function notarEnCurso(st, senal, ahora) {
  const curso = String(senal.enCurso || '').trim();
  if (!curso) return null;
  if (st._enCursoVisto !== curso) {
    st._enCursoVisto = curso;
    st._enCursoVistoAt = ahora;
  }
  return curso;
}

/**
 * Pool 7 tip±1 = minuto del timer enCurso (tip−1, tip, tip+1).
 * Ej. tip 37 → enCurso 9:36:xx / 9:37:xx / 9:38:xx.
 */
function ventanaPool7Abierta(senal) {
  const poolTip = poolTipDesdeSenal(senal);
  if (poolTip == null) return false;
  return senalEnZonaTip(senal, poolTip);
}

/**
 * Slot listo para auto: nuevo enCurso en tip±1, tras ~6 s, dentro de ~10 s de apuesta.
 * @returns {null|{ready?:boolean, defer?:boolean, exhaust?:boolean, why:string, key:string, minPiso:number|null}}
 */
function slotApuestaEnCurso(senal, st, ahora) {
  const poolTip = poolTipDesdeSenal(senal);
  if (poolTip == null) return null;
  const curso = notarEnCurso(st, senal, ahora);
  if (!curso) return null;
  if (!senalEnZonaTip(senal, poolTip)) return null;

  const key = claveApuestaEnCurso(senal.tag, curso);
  const minPiso = minutoTiroPiso(senal);
  if (st.tipsHechos.has(key)) {
    return { defer: true, why: 'ya-apostado-tiro', key, minPiso };
  }

  const seenAt = st._enCursoVistoAt || ahora;
  const age = ahora - seenAt;
  if (age < EN_CURSO_DELAY_MS) {
    return {
      defer: true,
      why: 'espera-apertura-' + Math.ceil((EN_CURSO_DELAY_MS - age) / 1000) + 's',
      key,
      minPiso,
    };
  }
  if (age > EN_CURSO_DELAY_MS + EN_CURSO_APUESTA_MS) {
    return { defer: true, exhaust: true, why: 'ventana-tiro-cerrada', key, minPiso };
  }
  return { ready: true, why: 'en-ventana-tiro', key, minPiso };
}

function pool7BrilloOkSenal(senal) {
  if (senal?.pool7BrilloOk) return true;
  try {
    const sync = require('./jokerbets-senal-sync.js');
    if (typeof sync.pool7BrilloOkDesdeFp === 'function') {
      return Boolean(sync.pool7BrilloOkDesdeFp(senal?.brilloFp));
    }
  } catch (_) {}
  return false;
}

/** Go Brillo + armado manda ($200). SIM Pool7 = tip±1 + Brillo fuerte+. Prod = Puerta A. */
function permitirApuesta(senal) {
  if (!ventanaPool7Abierta(senal)) return false;
  if (botArmado() && senal.puertaGoBrillo) return true;
  if (senal.simulPool7) return pool7BrilloOkSenal(senal);
  if (!botArmado()) return false;
  if (!senal.permitirClics) return false;
  if (senal.interruptor === 'OFF') return false;
  if (senal.puertaA) return true;
  return false;
}

/**
 * Color en TOMA TU DECISIÓN: siempre, si Chrome del bot está vivo.
 * No depende de Puerta A, Pool 7, zona tip, Brillo ni interruptor.
 */
function permitirBonoColor(_senal) {
  return true;
}

function claveApuestaAuto(senal, minPisoOverride) {
  const curso = String(senal.enCurso || '').trim();
  if (curso) return claveApuestaEnCurso(senal.tag, curso);
  const minPiso =
    minPisoOverride != null ? minPisoOverride : minutoTiroPiso(senal);
  return claveApuestaTagMinuto(senal.tag, minPiso);
}

function crearEstadoBot() {
  const t = Date.now();
  return {
    porCuenta: new Map(),
    frameCache: null,
    origenCaido: false,
    nextPlayFlojaAt: 0,
    nextDesfaseCheckAt: t + INTERVALO_DESFASE_MS,
    pulsoKey: '',
    relojSince: t,
    lastF5Mant: 0,
  };
}

/** Sin ventana de apuesta / Go caliente — solo ahí conviene play preventivo. */
function horaRegimenFlojo(senal) {
  if (senal.simulPool7) return false;
  if (senal.permitirClics || senal.puertaA) return false;
  if (senal.enZonaApuesta && senal.ventanaCaliente !== false) return false;
  if (senal.gapTiro != null && senal.gapTiro <= 4) return false;
  if (senal.interruptor === 'ON') return false;
  return true;
}

async function f5TodasLasMesas(contextsMulti, estadoBot, motivo) {
  invalidarFrameCache(estadoBot);
  for (const { cuenta, context } of contextsMulti) {
    const page = context.pages().find(p => !p.isClosed()) || null;
    if (!page) continue;
    const r = await dom.recargarMesaJuego(page, motivo);
    traceBot(cuenta.color, 'f5-mantenimiento', r.ok ? 'ok' : r.why || '?');
  }
}

/** Pantalla de mantenimiento Skywind — solo Disculpe (no Play: dispara F5 de más). */
async function mesaTieneDisculpe(contextsMulti, estadoBot) {
  const disc = await detectarDisculpeAlguna(contextsMulti, estadoBot);
  if (disc.ok) return { ok: true, why: 'disculpe', color: disc.color };
  return { ok: false };
}

async function detectarDisculpeAlguna(contextsMulti, estadoBot) {
  for (const { cuenta, context } of contextsMulti) {
    const page = context.pages().find(p => !p.isClosed()) || null;
    if (!page) continue;
    const frame = await gameFrameCached(estadoBot, page);
    if (!frame) continue;
    try {
      const d = await dom.detectDisculpeRapido(frame);
      if (d.ok) {
        return { ok: true, color: cuenta.color, det: d };
      }
    } catch (_) {}
  }
  return { ok: false };
}

async function playPreventivoHoraFloja(contextsMulti, estadoBot) {
  for (const { cuenta, context } of contextsMulti) {
    const page = context.pages().find(p => !p.isClosed()) || null;
    if (!page) continue;
    const frame = await gameFrameCached(estadoBot, page);
    if (!frame) continue;
    let enDecision = false;
    try {
      enDecision = await dom.pantallaDecision(frame);
    } catch (_) {}
    if (enDecision) continue;
    let play = { ok: false };
    try {
      play = await dom.detectPlayOverlayLigero(frame);
    } catch (_) {}
    if (!play.ok) continue;
    const clic = await dom.clickInactividadPlay(page, frame);
    traceBot(
      cuenta.color,
      'play-floja-10m',
      (clic.ok ? 'ok' : 'fallo') + ' · ' + (clic.detalle || play.detalle || clic.why || '')
    );
    if (clic.ok) {
      dom.logBot(cuenta.color + ' hora floja → play preventivo');
    }
  }
}

function cuentaStateDefaults() {
  return {
    lastApuestaAt: 0,
    lastColorAt: 0,
    lastDecisionKey: '',
    horaTag: '',
    tipsHechos: new Set(),
    lastApuestaAtByKey: {},
    centroPulsadoKeys: new Set(),
    apuestaBaselineByKey: {},
    centroClicadoEnRonda: false,
    ultimoSaldo: null,
    ultimoError: null,
    ultimoGesto: null,
    domPrev: { apuesta: null, premio: null, saldo: null },
    saldoPeak: null,
    frenoEmergencia: false,
    frenoDesdeTag: '',
    arranqueUsd: null,
  };
}

/** Mantenimiento puede crear entradas mínimas; rellenar campos faltantes (p. ej. lastColorAt). */
function cuentaState(map, id) {
  const defaults = cuentaStateDefaults();
  if (!map.has(id)) {
    map.set(id, { ...defaults });
    return map.get(id);
  }
  const st = map.get(id);
  for (const [k, v] of Object.entries(defaults)) {
    if (st[k] === undefined) {
      st[k] = v instanceof Set ? new Set() : v;
    }
  }
  return st;
}

function permitirCuenta(senal, manual) {
  const normal = permitirApuesta(senal);
  const manualTick = manualMod.permitirTick(manual);
  const manualPri = manualTick;
  return {
    apuesta: normal || manualTick,
    color: permitirBonoColor(senal),
    /** Manual pendiente gana: 1 clic centro aunque interruptor ON. */
    manual: manualPri,
  };
}

async function ejecutarApuestaJob(job, senal) {
  const { cuenta, page, frame, st, perm, tipApuesta, ahora, manual, autoKey: autoKeyJob } = job;
  const manualSnap = manualMod.leerManual();
  const manualParams = manual
    ? apuestaManualDesdeMonto(manualSnap.montoPorBono)
    : null;
  const clics = manual ? manualParams.clics : clicsCentroAuto(senal);
  const modoAp = manual ? String(manualParams.montoBono) : apuestaModoAuto(senal);
  const minSlot = manual ? minutoTiroPiso(senal) : tipApuesta;
  const autoKey =
    autoKeyJob ||
    (manual
      ? claveApuestaAuto(senal, minSlot)
      : claveApuestaEnCurso(senal.tag, senal.enCurso));
  const minTiro = minutoTiroPiso(senal);
  const poolTip = poolTipDesdeSenal(senal);
  const objetivo = manual ? manualParams.objetivo : apuestaObjetivoModo(modoAp);
  const montoBono = manual ? manualParams.montoBono : montoPorBonoModo(modoAp);

  let apuestaAntes = null;
  try {
    const bar0 = await dom.readBarraSaldo(frame);
    if (bar0.apuesta != null) apuestaAntes = parseApuestaNum(bar0.apuesta);
  } catch (_) {}
  if (apuestaAntes == null) apuestaAntes = parseApuestaNum(st.ultimoApuesta);

  /** Manual y auto: mismo clic (chip sin validar + centro force). Auto = timing enCurso. */
  if (manual) {
    const arm = manualSnap.armadoAt || '';
    if (arm && st._manualOlaCuenta === arm) return;
    st._manualOlaCuenta = arm;
  } else {
    if (!permitirApuesta(senal)) {
      st.ultimoGesto = 'auto-sin-zona';
      return;
    }
    if (!autoKey || st.tipsHechos.has(autoKey)) {
      st.ultimoGesto = 'auto-ya-apostado';
      return;
    }
    if (!ventanaPool7Abierta(senal)) {
      st.ultimoGesto = 'auto-fuera-zona-tip';
      return;
    }
    const lastAtKey = st.lastApuestaAtByKey[autoKey] || 0;
    if (ahora - lastAtKey < MIN_MS_ENTRE_APUESTA) return;

    const omit = await omitirClicApuesta(
      st,
      autoKey,
      apuestaAntes,
      objetivo,
      frame,
      montoBono
    );
    if (omit.omitir) {
      if (omit.marcar) {
        marcarSlotApuestaHecho(
          st,
          autoKey,
          cuenta,
          'APUESTA=' + (apuestaAntes ?? '?') + ' obj=' + objetivo + ' · ' + omit.why
        );
      } else {
        st.ultimoGesto = 'auto-ya-apostado';
      }
      return;
    }

    /** Solo dentro de la ventana del tiro; mesa abierta (Hagan juego / centro on). */
    if (await dom.esperaSiguienteRonda(frame)) {
      st.ultimoGesto = 'auto-espera-ronda';
      return;
    }
    const ventana = await dom.ventanaApuestaAbierta(frame);
    if (!ventana.ok) {
      st.ultimoGesto = 'auto-' + ventana.why;
      if (!st._lastMesaWhy || st._lastMesaWhy !== ventana.why) {
        st._lastMesaWhy = ventana.why;
        traceBot(cuenta.color, 'mesa-no-lista', ventana.why);
      }
      return;
    }
    st._lastMesaWhy = null;
  }

  const bloq = await dom.bloqueoApuestaManual(frame);
  if (bloq) {
    st.ultimoGesto = (manual ? 'manual-' : 'auto-') + bloq;
    return;
  }

  let gameFrame = frame;
  try {
    const fresh = await dom.findGameFrame(page);
    if (fresh) gameFrame = fresh;
  } catch (_) {}

  traceBot(
    cuenta.color,
    'apuesta-clics',
    'modo=' +
      modoAp +
      ' clics=' +
      clics +
      ' key=' +
      autoKey +
      ' poolTip=' +
      (poolTip ?? '?') +
      ' minSlot=' +
      (minSlot ?? '?') +
      ' minTiro=' +
      (minTiro ?? '?') +
      ' enCurso=' +
      (senal.enCurso || '?') +
      ' gapTiro=' +
      (senal.gapTiro ?? '?') +
      (senal.simulPool7 ? ' SIM=1' : '') +
      ' directo=1'
  );
  traceBot(
    cuenta.color,
    manual ? 'manual-directo' : 'auto-directo',
    'clics=' + clics + ' $' + montoBono + '/bono'
  );

  const n = await dom.clickCenterCircleManual(page, gameFrame, clics);
  const postMs = manual ? MANUAL_POST_CLIC_MS : 450;
  try {
    await gameFrame.waitForTimeout(postMs);
  } catch (_) {}

  let apuestaLeida = st.ultimoApuesta;
  try {
    const bar2 = await dom.readBarraSaldo(gameFrame);
    if (bar2.apuesta != null) apuestaLeida = bar2.apuesta;
  } catch (_) {}

  if (manual) {
    if (n >= 1) {
      st._manualOk = true;
      st.lastApuestaAt = Date.now();
      st.ultimoGesto = 'manual-circulo-x' + n;
      dom.logBot(
        cuenta.color +
          ' manual · directo · ' +
          n +
          ' clics centro · APUESTA DOM=' +
          (apuestaLeida ?? '?')
      );
      jlog.appendLog({
        tipo: 'apuesta_manual',
        cuentaId: cuenta.id,
        color: cuenta.color,
        horaTag: senal.tag || null,
        montoApuesta:
          apuestaLeida != null ? String(apuestaLeida) : '$' + String(objetivo) + '?',
        notas:
          `Manual directo $${montoBono}/bono · $${objetivo} total · ${n} clic(s) centro · sin validar chip`,
        fuente: 'bot',
      });
    } else {
      st.ultimoGesto = 'manual-fallo-centro';
      traceBot(cuenta.color, 'manual-fallo-centro', 'clics=0');
    }
    return;
  }

  /** Throttle reintento; no quemar el minuto hasta confirmar barra. */
  st.lastApuestaAtByKey[autoKey] = Date.now();

  const clicsOk = n >= clics;
  const barraOk = apuestaConfirmadaDom(apuestaAntes, apuestaLeida, objetivo);
  if (clicsOk && barraOk) {
    if (!st.centroPulsadoKeys) st.centroPulsadoKeys = new Set();
    st.centroPulsadoKeys.add(autoKey);
    st.centroClicadoEnRonda = true;
    st.tipsHechos.add(autoKey);
    st.lastApuestaAt = Date.now();
    st.ultimoGesto = 'auto-circulo-x' + n;
    dom.logBot(
      cuenta.color +
        ' auto · directo · ' +
        n +
        ' clics · $' +
        montoBono +
        '/bono · poolTip ' +
        (poolTip ?? '?') +
        ' min ' +
        (minSlot ?? '?') +
        ' · APUESTA DOM=' +
        (apuestaLeida ?? '?')
    );
    jlog.appendLog({
      tipo: 'apuesta_bot',
      cuentaId: cuenta.id,
      color: cuenta.color,
      horaTag: senal.tag || null,
      montoApuesta:
        apuestaLeida != null
          ? String(apuestaLeida)
          : '$' + String(apuestaObjetivoModo(modoAp)) + '?',
      notas:
        `Auto enCurso $${montoBono}/bono · Pool7 tip ${poolTip ?? '?'} · min ${minSlot ?? '?'} · key ${autoKey} · enCurso ${senal.enCurso || '?'} · gapTiro ${senal.gapTiro ?? '?'} · ${n} clic(s) centro · barra OK` +
        (senal.simulPool7 ? ' · SIM' : ' · PuertaA'),
      fuente: 'bot',
    });
    alog.registrarApuestaBot({
      cuenta,
      senal,
      st,
      montoApuesta: apuestaLeida,
      objetivo,
      bono: montoBono,
      clics: n,
      poolTip,
      minSlot,
      key: autoKey,
    });
    traceBot(
      cuenta.color,
      'apuesta-ok-directo',
      'key=' +
        autoKey +
        ' clics=' +
        n +
        '/' +
        clics +
        ' APUESTA=' +
        (apuestaLeida ?? '?')
    );
  } else if (clicsOk && !barraOk) {
    st.ultimoGesto = 'auto-clic-sin-barra';
    traceBot(
      cuenta.color,
      'apuesta-clic-sin-barra',
      'key=' +
        autoKey +
        ' clics=' +
        n +
        '/' +
        clics +
        ' APUESTA=' +
        (apuestaLeida ?? '0') +
        ' (reintenta)'
    );
  } else if (n >= 1) {
    st.ultimoGesto = 'auto-fallo-centro-parcial';
    traceBot(
      cuenta.color,
      'apuesta-sin-clic',
      'key=' + autoKey + ' minSlot=' + (minSlot ?? '?') + ' clics=' + n + '/' + clics
    );
  } else {
    st.ultimoGesto = 'auto-fallo-centro';
    traceBot(
      cuenta.color,
      'auto-fallo-centro',
      'key=' + autoKey + ' clics=0/' + clics
    );
  }
}

async function buildManualJobs(contextsMulti, estadoBot, manual) {
  if (!manualMod.permitirTick(manual)) return [];
  const senal = leerSenal();
  const jobs = [];
  for (const { cuenta, context } of contextsMulti) {
    const st = cuentaState(estadoBot.porCuenta, cuenta.id);
    if (manual.armadoAt && st._manualSession === manual.armadoAt && st._manualOk) {
      continue;
    }
    if (manual.armadoAt && st._manualSession !== manual.armadoAt) {
      st._manualSession = manual.armadoAt;
      st._manualOk = false;
      st._manualOlaCuenta = null;
    }
    let page;
    try {
      page = context.pages().find(p => !p.isClosed()) || null;
    } catch (_) {
      page = null;
    }
    if (!page) {
      st.ultimoGesto = 'manual-sin-pestaña';
      continue;
    }
    const frame = await dom.findGameFrame(page);
    if (!frame) {
      st.ultimoGesto = 'manual-sin-iframe';
      continue;
    }
    jobs.push({
      cuenta,
      page,
      frame,
      st,
      perm: { apuesta: true, manual: true },
      tipApuesta: senal.tip,
      ahora: Date.now(),
      manual: true,
    });
  }
  return jobs;
}

const ORDEN_COLOR_MANUAL = ['rojo', 'azul', 'verde'];

/** Una ola ×3 en secuencia rojo→azul→verde (bringToFront por si acaso; no depende del foco del usuario). */
async function ejecutarManualParalelo(contextsMulti, estadoBot, manual) {
  const jobs = await buildManualJobs(contextsMulti, estadoBot, manual);
  if (!jobs.length) {
    dom.logBot('Manual ×3 · 0 mesas listas (iframe/pestaña)');
    return 0;
  }
  dom.logBot(
    'Manual ×3 · mesas en ola: ' + jobs.map(j => j.cuenta.color).join(', ')
  );
  jobs.sort(
    (a, b) =>
      ORDEN_COLOR_MANUAL.indexOf(String(a.cuenta.color || '').toLowerCase()) -
      ORDEN_COLOR_MANUAL.indexOf(String(b.cuenta.color || '').toLowerCase())
  );
  const senalViva = leerSenal();
  for (const j of jobs) {
    try {
      if (j.page && !j.page.isClosed()) await j.page.bringToFront();
    } catch (_) {}
    await ejecutarApuestaJob(j, senalViva).catch(() => {});
  }
  return jobs.length;
}

/** Cierra la sesión manual tras una sola ola (1 clic botón = 1 pasada ×3, sin reintentos). */
function cerrarManualUnaOla(contextsMulti, estadoBot, manual) {
  if (!manualMod.permitirTick(manual)) return;
  const estados = contextsMulti.map(({ cuenta }) => estadoBot.porCuenta.get(cuenta.id));
  const nOk = estados.filter(st => st && st._manualOk).length;
  const gestos = estados.map(st => (st && st.ultimoGesto) || '?').join(' | ');
  if (nOk === 3) {
    manualMod.marcarDisparada('3 cuentas · manual OK');
    dom.logBot('Apuesta manual cerrada (3/3).');
  } else {
    manualMod.marcarDisparada(`${nOk}/3 · ${gestos}`.slice(0, 280));
    dom.logBot('Apuesta manual · una ola · OK: ' + nOk + '/3 · gestos: ' + gestos);
  }
}

async function ejecutarBonoJob(job) {
  const { cuenta, page, st, senal, key, ahora } = job;
  let frame = job.frame;
  if (!permitirBonoColor(senal)) {
    st.ultimoGesto = 'color-espera';
    traceBot(cuenta.color, 'bono-skip', 'sin permiso color');
    return;
  }
  if ((st._bonoIntentos || 0) >= MAX_INTENTOS_BONO) {
    st.ultimoGesto = 'bono-tope-intentos';
    traceBot(cuenta.color, 'bono-skip', 'tope intentos');
    return;
  }
  try {
    const fresh = await dom.findGameFrame(page);
    if (fresh) frame = fresh;
  } catch (_) {}
  if (!frame) {
    st.ultimoGesto = 'bono-sin-iframe';
    traceBot(cuenta.color, 'bono-skip', 'sin iframe juego');
    return;
  }
  const bono = bonoColorCuenta(cuenta);
  const res = await dom.clickColorCuenta(frame, bono, page);
  const vOk = res.verify?.ok;
  st._bonoIntentos = (st._bonoIntentos || 0) + 1;
  st.ultimoGesto = res.ok ? 'bono-' + bono + (vOk ? '+verif' : '?verif') : 'bono-fallo';
  traceBot(cuenta.color, 'bono-color', res.detalle || bono);
  dom.logBot(
    cuenta.color +
      ' decisión bono → ' +
      bono +
      ' · ' +
      st.ultimoGesto +
      ' · ' +
      (res.detalle || '')
  );
  if (res.ok) {
    st.lastColorAt = ahora;
    if (vOk) {
      st.lastDecisionKey = key;
      st._bonoColorOk = true;
      st._bonoIntentos = 0;
      st._bonoCooldownTraceAt = 0;
      st._bonoTopeTraceAt = 0;
      st._bonoSinColaTraceAt = 0;
    }
    jlog.appendLog({
      tipo: 'bono_color',
      cuentaId: cuenta.id,
      color: cuenta.color,
      horaTag: senal.tag || null,
      montoApuesta: null,
      notas:
        'bono=' +
        bono +
        ' · ' +
        (res.detalle || 'Bono color') +
        (vOk ? ' · UI confirma selección' : ' · UI sin marca (revisar)'),
      fuente: 'bot',
    });
  }
}

function etiquetaDisculpe(det) {
  if (!det) return 'disculpe';
  if (det.error506) return '506';
  if (det.error99501) return '99501';
  return det.codigoError || 'disculpe';
}

/** F5×3 y marca modo origen si tras recargar sigue Disculpe. */
async function f5GoNogoYEvaluarOrigen(contextsMulti, estadoBot, pulsoKey, evento) {
  const ahora = Date.now();
  estadoBot.lastF5Mant = ahora;
  estadoBot.relojSince = ahora;
  estadoBot.pulsoKey = pulsoKey;
  traceBot(null, evento, pulsoKey);
  dom.logBot('Go!/NoGo! → F5 las 3 mesas · ' + pulsoKey);
  await f5TodasLasMesas(contextsMulti, estadoBot, evento);
  const post = await detectarDisculpeAlguna(contextsMulti, estadoBot);
  if (post.ok) {
    estadoBot.origenCaido = true;
    traceBot(null, 'origen-disculpe-persiste', post.color + '|' + etiquetaDisculpe(post.det));
    dom.logBot(
      'Tras F5 sigue Disculpe (' +
        post.color +
        ') · falla origen · F5 cada 3 min hasta que enCurso avance'
    );
  } else {
    estadoBot.origenCaido = false;
  }
}

async function aplicarMantenimientoMesa(contextsMulti, estadoBot, senal) {
  const tag = String(senal.tag || '').trim();
  const ahora = Date.now();
  const pulsoKey = clavePulsoCinta(senal);

  if (tag) {
    if (estadoBot.pulsoKey !== pulsoKey) {
      if (estadoBot.origenCaido) {
        traceBot(null, 'origen-recuperado-pulso', pulsoKey);
        dom.logBot('Cinta avanzó · origen OK · ' + pulsoKey);
      }
      estadoBot.pulsoKey = pulsoKey;
      estadoBot.relojSince = ahora;
      estadoBot.origenCaido = false;
    }

    if (
      ahora - (estadoBot.lastF5Mant || 0) >= MIN_MS_ENTRE_F5_MANT
    ) {
      const disc = await mesaTieneDisculpe(contextsMulti, estadoBot);
      if (disc.ok) {
        await f5GoNogoYEvaluarOrigen(
          contextsMulti,
          estadoBot,
          pulsoKey,
          'disculpe-f5'
        );
        return;
      }
    }

    if (
      estadoBot.origenCaido &&
      ahora - (estadoBot.lastF5Mant || 0) >= F5_ORIGEN_DISULPE_MS &&
      ahora - (estadoBot.lastF5Mant || 0) >= MIN_MS_ENTRE_F5_MANT
    ) {
      await f5GoNogoYEvaluarOrigen(
        contextsMulti,
        estadoBot,
        pulsoKey,
        'origen-f5-3min'
      );
      return;
    }

    if (
      !estadoBot.origenCaido &&
      ahora >= (estadoBot.nextDesfaseCheckAt || 0) &&
      ahora - (estadoBot.lastF5Mant || 0) >= MIN_MS_ENTRE_F5_MANT
    ) {
      estadoBot.nextDesfaseCheckAt = ahora + INTERVALO_DESFASE_MS;
      const lag = desfaseEnCursoAtrasadoMin(senal);
      const detalle =
        'enCurso=' +
        (senal.enCurso || '?') +
        ' · reloj=' +
        (senal.relojMinuto != null ? String(senal.relojMinuto) : '?') +
        ':' +
        (senal.relojSegundo != null ? String(senal.relojSegundo) : '?') +
        ' · lagMin=' +
        (lag != null ? lag.toFixed(1) : '?');
      if (ventanaPool7Abierta(senal)) {
        traceBot(null, 'desfase-skip-ventana-p7', detalle);
        return;
      }
      if (lag != null && lag >= DESFASE_EN_CURSO_MIN) {
        traceBot(null, 'desfase-enCurso-f5', detalle);
        dom.logBot('Go! atrasado ≥' + DESFASE_EN_CURSO_MIN + ' min · F5 · ' + detalle);
        await f5GoNogoYEvaluarOrigen(
          contextsMulti,
          estadoBot,
          pulsoKey,
          'desfase-enCurso-5min'
        );
        return;
      }
      traceBot(null, 'desfase-ok', detalle);
    }
  }

  if (
    !estadoBot.origenCaido &&
    horaRegimenFlojo(senal) &&
    ahora >= (estadoBot.nextPlayFlojaAt || 0)
  ) {
    estadoBot.nextPlayFlojaAt = ahora + PLAY_HORA_FLOJA_MS;
    await playPreventivoHoraFloja(contextsMulti, estadoBot);
  }
}

async function tickBot(contextsMulti, estadoBot, onEstado) {
  if (!contextsMulti?.length) return;
  const senal = leerSenal();
  let manual = manualMod.leerManual();
  if (manualMod.permitirTick(manual)) {
    const arm = manual.armadoAt || '';
    if (estadoBot._manualOlaArmado !== arm) {
      estadoBot._manualOlaArmado = arm;
      dom.logBot(
        'Manual ×3 · una ola · rojo→azul→verde · bringToFront · $' +
          (manual.montoPorBono ?? 50) +
          '/bono · armadoAt=' +
          (arm || '?')
      );
      await ejecutarManualParalelo(contextsMulti, estadoBot, manual);
      cerrarManualUnaOla(contextsMulti, estadoBot, manual);
    }
    manual = manualMod.leerManual();
    if (onEstado) onEstado(estadoBot, senal, permitirApuesta(senal), manual);
    return;
  }
  estadoBot._manualOlaArmado = null;
  const apuestaOk = permitirApuesta(senal);
  const colaApuestaAuto = [];
  const colaBono = [];
  for (const { cuenta, context } of contextsMulti) {
    const st = cuentaState(estadoBot.porCuenta, cuenta.id);
    resetHoraCuenta(st, senal.tag, cuenta, senal);
    let perm = permitirCuenta(senal, manual);
    let page;
    try {
      page = context.pages().find(p => !p.isClosed()) || null;
    } catch (_) {
      page = null;
    }
    if (!page) {
      if (perm.manual) {
        st.ultimoGesto = 'manual-sin-pestaña';
      }
      continue;
    }

    let frame = await dom.findGameFrame(page);
    if (!frame) {
      if (perm.manual) {
        st.ultimoGesto = 'manual-sin-iframe';
      }
      continue;
    }

    const ahora = Date.now();
    let enDecision = false;
    try {
      enDecision = await dom.pantallaDecision(frame);
      if (!enDecision) {
        const frame2 = await dom.findGameFrame(page);
        if (frame2 && frame2 !== frame) {
          frame = frame2;
          enDecision = await dom.pantallaDecision(frame);
        }
      }
    } catch (_) {}
    if (enDecision) {
      encolarBonoSiCorresponde({
        cuenta,
        page,
        frame,
        st,
        perm,
        senal,
        colaBono,
        ahora,
      });
      st.ultimoGesto = st._bonoColorOk ? 'bono-hecho' : 'bono-decision';
      continue;
    }
    if (st._bonoEnPantalla) {
      st._bonoEnPantalla = false;
      st._bonoCooldownTraceAt = 0;
      st._bonoTopeTraceAt = 0;
    }
    st._bonoTraceAt = 0;

    if (perm.apuesta && !st._frameUrlLogged) {
      st._frameUrlLogged = true;
      try {
        traceBot(cuenta.color, 'frame', (frame.url() || '').slice(0, 120));
      } catch (_) {}
    }

    try {
      const bar = await dom.readBarraSaldoFromPage(page);
      const premioAntes = st.domPrev?.premio;
      if (bar.saldo) st.ultimoSaldo = bar.saldo;
      if (bar.apuesta != null) st.ultimoApuesta = bar.apuesta;
      if (bar.premio != null) st.ultimoPremio = bar.premio;
      const saldoNum = alog.parseSaldo(bar.saldo || st.ultimoSaldo);
      alog.registrarSaldo({ cuenta, saldoRaw: bar.saldo, st, senal, motivo: 'tick' });
      evaluarFrenoEmergencia(st, saldoNum, senal.tag, cuenta, senal);
      if (apuestaBloqueadaFreno(st, senal.tag)) {
        perm = { ...perm, apuesta: false };
        st.ultimoGesto = 'freno-emergencia-standby';
      }
      try {
        const barGame = await dom.readBarraSaldo(frame);
        if (barGame.apuesta != null) st.ultimoApuesta = barGame.apuesta;
        sincronizarEstadoRondaApuesta(
          st,
          barGame.apuesta,
          apuestaObjetivoModo(apuestaModoAuto(senal))
        );
      } catch (_) {}
      const premioSubio =
        bar.premio &&
        bar.premio !== premioAntes &&
        (jlog.parseMonto(bar.premio) || 0) > 0;
      if (premioSubio || ahora - (st._domLogAt || 0) > 12_000) {
        st._domLogAt = ahora;
        let snippet = '';
        if (premioSubio) {
          try {
            snippet = await frame.evaluate(() =>
              String(document.body?.innerText || '').slice(0, 5000)
            );
          } catch (_) {}
        }
        jlog.registrarCambiosDom({
          cuenta,
          bar,
          prev: st.domPrev,
          botArmado: botArmado(),
          apuestaOk: perm.apuesta,
          bodySnippet: snippet,
          horaTag: senal.tag || null,
        });
        if (premioSubio) {
          const mult = jlog.parseMultiplicador(snippet, bar.apuesta, bar.premio);
          const montoApuesta = bar.apuesta || st.domPrev.apuesta;
          alog.registrarPremio({
            cuenta,
            senal,
            st,
            montoApuesta,
            premio: bar.premio,
            multiplicador: mult,
          });
          if (
            jlog.esCobroGanancia({
              tipo: 'premio',
              premio: bar.premio,
              montoApuesta,
              multiplicador: mult,
            })
          ) {
            jlog.bumpUiPulse('premio_ganado', {
              color: cuenta.color,
              cuentaId: cuenta.id,
            });
          }
        }
      }
      st.domPrev = {
        apuesta: bar.apuesta != null ? String(bar.apuesta) : st.domPrev.apuesta,
        premio: bar.premio != null ? String(bar.premio) : st.domPrev.premio,
        saldo: bar.saldo != null ? String(bar.saldo) : st.domPrev.saldo,
      };
      if (!bar.saldo && !st._saldoLogAt) {
        st._saldoLogAt = Date.now();
        dom.logBot(cuenta.color + ' SALDO no leído aún (iframe)');
      } else if (bar.saldo) {
        st._saldoLogAt = 0;
      }
    } catch (e) {
      st.ultimoError = String(e.message || e).slice(0, 120);
    }

    try {
      if (!perm.apuesta) {
        st.ultimoGesto = manual.pendiente ? 'manual-pendiente' : 'idle';
        const mp = minutoTiroPiso(senal);
        const bloqueKey =
          String(senal.tag || '') + '|bloqueo|' + (mp != null ? mp : '?');
        if (senalEnZonaTip(senal, senal.tip) && st._lastBloqueoSenalKey !== bloqueKey) {
          st._lastBloqueoSenalKey = bloqueKey;
          traceBot(
            cuenta.color,
            'apuesta-bloqueada-senal',
            'iv=' +
              (senal.interruptor || '?') +
              ' puertaA=' +
              (senal.puertaA ? '1' : '0') +
              ' formaG=' +
              (senal.formaGApuesta ? '1' : '0') +
              ' via=' +
              (senal.viaApuesta || '-') +
              ' clics=' +
              (senal.permitirClics ? '1' : '0') +
              ' enZonaAp=' +
              (senal.enZonaApuesta ? '1' : '0') +
              ' sim=' +
              (senal.simulPool7 ? '1' : '0') +
              ' tip=' +
              (senal.tip ?? '?') +
              ' rel=' +
              (senal.relojMinuto ?? '?') +
              ':' +
              (senal.relojSegundo ?? '?') +
              ' src=' +
              (senal._senalFuente || 'dash')
          );
        }
        continue;
      }
      st._lastBloqueoSenalKey = '';

      if (perm.manual && manual.armadoAt && st._manualSession !== manual.armadoAt) {
        st._manualSession = manual.armadoAt;
        st._manualTickDone = false;
        st._manualOk = false;
      }

      if (perm.manual) {
        if (manual.armadoAt && st._manualSession === manual.armadoAt && st._manualOk) {
          continue;
        }
        colaApuestaAuto.push({
          cuenta,
          page,
          frame,
          st,
          perm,
          tipApuesta: senal.tip,
          ahora,
          manual: true,
        });
        continue;
      }

      const slot = slotApuestaEnCurso(senal, st, ahora);
      if (!slot || !slot.ready) {
        if (slot?.exhaust && slot.key && !st.tipsHechos.has(slot.key)) {
          st.tipsHechos.add(slot.key);
          st.ultimoGesto = 'auto-ventana-tiro-cerrada';
          traceBot(
            cuenta.color,
            'auto-ventana-tiro-cerrada',
            'key=' + slot.key + ' · sin barra en ~10s'
          );
        } else if (permitirApuesta(senal) && slot) {
          st.ultimoGesto =
            slot.why === 'ya-apostado-tiro'
              ? 'auto-ya-apostado-tiro'
              : 'auto-' + (slot.why || 'espera-tiro');
        } else if (permitirApuesta(senal)) {
          st.ultimoGesto = 'auto-espera-enCurso';
        } else if (senal.enCurso && poolTipDesdeSenal(senal) != null) {
          st.ultimoGesto = 'auto-fuera-zona-tip';
        }
        continue;
      }

      colaApuestaAuto.push({
        cuenta,
        page,
        frame,
        st,
        perm,
        tipApuesta: slot.minPiso,
        autoKey: slot.key,
        ahora,
        manual: false,
      });
    } catch (e) {
      st.ultimoError = String(e.message || e).slice(0, 120);
    }
  }

  if (colaBono.length) {
    await Promise.all(
      colaBono.map(j =>
        ejecutarBonoJob(j).catch(e => {
          traceBot(
            j.cuenta.color,
            'bono-job-error',
            String(e.message || e).slice(0, 120)
          );
        })
      )
    );
  }

  if (colaApuestaAuto.length) {
    const senalViva = leerSenal();
    const autoJobs = colaApuestaAuto.filter(j => !j.manual);
    const manualJobs = colaApuestaAuto.filter(j => j.manual);
    if (autoJobs.length && permitirApuesta(senalViva)) {
      await Promise.all(
        autoJobs.map(j => ejecutarApuestaJob(j, senalViva).catch(() => {}))
      );
    }
    if (manualJobs.length) {
      await Promise.all(
        manualJobs.map(j => ejecutarApuestaJob(j, senalViva).catch(() => {}))
      );
    }
  }

  if (onEstado) onEstado(estadoBot, senal, apuestaOk, manualMod.leerManual());
}

function startBotLoop(contextsMulti, onEstado) {
  const estadoBot = crearEstadoBot();
  let tickBusy = false;
  dom.logBot('Loop bot C iniciado (armado=' + botArmado() + ')');
  return setInterval(() => {
    if (tickBusy) return;
    tickBusy = true;
    tickBot(contextsMulti, estadoBot, onEstado)
      .catch(e => dom.logBot('tick error: ' + String(e.message || e).slice(0, 80)))
      .finally(() => {
        tickBusy = false;
      });
  }, 650);
}

module.exports = {
  startBotLoop,
  leerSenal,
  botArmado,
  SENAL_FILE,
  BOT_FILE,
};
