const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const LOG_FILE = path.join(DIR, 'jokerbets-apuestas.jsonl');
const UI_PULSE_FILE = path.join(DIR, 'jokerbets-ui-pulse.json');
const MAX_LINEAS_LEER = 200;
const JOKERBETS_CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const PUSH_URL =
  (process.env.JOKERBETS_SERVIR || 'http://127.0.0.1:8765') +
  '/api/jokerbets/push-event';

const COLORES_RONDA = ['rojo', 'azul', 'verde'];
const RONDA_ESPERA_MS = 18_000;

let ntfyCache = { at: 0, enabled: null };
/** @type {Map<string, { colors: object, firstAt: number, sent: boolean, horaTag: string }>} */
const bolsasRonda = new Map();
let lastRondaPushKey = '';
let lastRondaPushAt = 0;

function ntfyHabilitado() {
  const now = Date.now();
  if (ntfyCache.enabled != null && now - ntfyCache.at < 60_000) {
    return ntfyCache.enabled;
  }
  let on = false;
  try {
    if (fs.existsSync(JOKERBETS_CONFIG_FILE)) {
      const cfg = JSON.parse(fs.readFileSync(JOKERBETS_CONFIG_FILE, 'utf-8'));
      const n = cfg?.ntfy;
      on = Boolean(n && n.enabled !== false && String(n.topic || '').trim());
    }
  } catch (_) {}
  ntfyCache = { at: now, enabled: on };
  return on;
}

/**
 * Solo cobro real de bono: hubo apuesta en barra y premio de cobro.
 * Descarta PREMIO acumulado / fantasmas con apuesta 0.
 */
function esCobroGanancia(row) {
  if (String(row.tipo || '').toLowerCase() !== 'premio') return false;
  const p = parseMonto(row.premio);
  if (p == null || p <= 0) return false;
  const a = parseMonto(row.montoApuesta);
  if (a == null || a <= 0) return false;
  if (p >= a) return true;
  const mult = row.multiplicador != null ? Number(row.multiplicador) : null;
  // Mult≥2 del sector + premio al menos 1 bono mínimo ($50).
  if (mult != null && !Number.isNaN(mult) && mult >= 2 && p >= 50) return true;
  return false;
}

function claveBolsaRonda(row) {
  const tag = String(row.horaTag || 'sin-hora').toLowerCase();
  const t = Date.parse(row.ts || '');
  const bucket = Number.isNaN(t) ? 0 : Math.floor(t / 45_000);
  return `${tag}|b${bucket}`;
}

function filaResumen(color, row) {
  if (!row) {
    return { color, premio: null, montoApuesta: null, multiplicador: null, saldo: null, ganancia: false };
  }
  return {
    color,
    premio: row.premio ?? null,
    montoApuesta: row.montoApuesta ?? null,
    multiplicador: row.multiplicador ?? null,
    saldo: row.saldo ?? null,
    ganancia: esCobroGanancia(row),
  };
}

function intentarPushRonda(bolsaKey, bolsa) {
  if (bolsa.sent) return;
  const algunaGana = COLORES_RONDA.some(c => bolsa.colors[c] && esCobroGanancia(bolsa.colors[c]));
  if (!algunaGana) {
    if (Date.now() - bolsa.firstAt > RONDA_ESPERA_MS) bolsasRonda.delete(bolsaKey);
    return;
  }
  const todas = COLORES_RONDA.every(c => bolsa.colors[c]);
  const timeout = Date.now() - bolsa.firstAt >= RONDA_ESPERA_MS;
  if (!todas && !timeout) return;

  const colores = COLORES_RONDA.map(c => filaResumen(c, bolsa.colors[c]));
  const aciertos = colores.filter(c => c.ganancia);
  if (!aciertos.length) {
    if (Date.now() - bolsa.firstAt > RONDA_ESPERA_MS) bolsasRonda.delete(bolsaKey);
    return;
  }
  const dedupe = [
    bolsaKey,
    ...aciertos.map(c => `${c.color}:${c.premio}:${c.montoApuesta}`),
  ].join('|');
  const now = Date.now();
  if (dedupe === lastRondaPushKey && now - lastRondaPushAt < 30_000) {
    bolsa.sent = true;
    bolsasRonda.delete(bolsaKey);
    return;
  }

  bolsa.sent = true;
  lastRondaPushKey = dedupe;
  lastRondaPushAt = now;
  bolsasRonda.delete(bolsaKey);

  if (!ntfyHabilitado() || typeof fetch !== 'function') return;

  fetch(PUSH_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tipo: 'ronda_acertada',
      horaTag: bolsa.horaTag || null,
      colores,
      ts: new Date().toISOString(),
    }),
  }).catch(() => {});
}

function registrarPremioParaNtfy(row) {
  if (String(row.tipo || '').toLowerCase() !== 'premio') return;
  const color = String(row.color || '').toLowerCase();
  if (!COLORES_RONDA.includes(color)) return;

  const bolsaKey = claveBolsaRonda(row);
  let bolsa = bolsasRonda.get(bolsaKey);
  if (!bolsa) {
    bolsa = {
      colors: {},
      firstAt: Date.now(),
      sent: false,
      horaTag: row.horaTag || '',
    };
    bolsasRonda.set(bolsaKey, bolsa);
  }
  bolsa.colors[color] = row;
  if (row.horaTag) bolsa.horaTag = row.horaTag;
  intentarPushRonda(bolsaKey, bolsa);
}

function bumpUiPulse(reason, extra) {
  const payload = {
    seq: Date.now(),
    at: new Date().toISOString(),
    reason: String(reason || 'evento'),
    ...(extra && typeof extra === 'object' ? extra : {}),
  };
  try {
    fs.writeFileSync(UI_PULSE_FILE, JSON.stringify(payload), 'utf-8');
  } catch (_) {}
  return payload;
}

function readUiPulse() {
  try {
    if (!fs.existsSync(UI_PULSE_FILE)) return null;
    return JSON.parse(fs.readFileSync(UI_PULSE_FILE, 'utf-8'));
  } catch (_) {
    return null;
  }
}

function appendLog(entry) {
  const row = {
    ts: new Date().toISOString(),
    ...entry,
  };
  try {
    fs.appendFileSync(LOG_FILE, JSON.stringify(row) + '\n', 'utf-8');
  } catch (_) {}
  registrarPremioParaNtfy(row);
  const tipo = String(row.tipo || '').toLowerCase();
  if (tipo === 'bono_color') {
    bumpUiPulse('bono_fin', { color: row.color, cuentaId: row.cuentaId });
  } else if (tipo === 'premio' && esCobroGanancia(row)) {
    bumpUiPulse('premio_ganado', { color: row.color, cuentaId: row.cuentaId });
  }
  return row;
}

function readLog({ color = null, cuentaId = null, limit = 80 } = {}) {
  if (!fs.existsSync(LOG_FILE)) return [];
  let lines;
  try {
    lines = fs.readFileSync(LOG_FILE, 'utf-8').split(/\r?\n/).filter(Boolean);
  } catch (_) {
    return [];
  }
  if (lines.length > MAX_LINEAS_LEER) {
    lines = lines.slice(-MAX_LINEAS_LEER);
  }
  const out = [];
  for (let i = lines.length - 1; i >= 0 && out.length < limit; i -= 1) {
    try {
      const ev = JSON.parse(lines[i]);
      if (color && ev.color !== color) continue;
      if (cuentaId && ev.cuentaId !== cuentaId) continue;
      out.push(ev);
    } catch (_) {}
  }
  return out;
}

/** Parsea montos de barra: 200, 1.05K, 1,693, $6K. */
function parseMonto(raw) {
  if (raw == null || raw === '') return null;
  let s = String(raw).trim().replace(/\s/g, '').replace(/\$/g, '');
  if (!s) return null;
  let mul = 1;
  if (/k$/i.test(s)) {
    mul = 1_000;
    s = s.replace(/k$/i, '');
  } else if (/m$/i.test(s)) {
    mul = 1_000_000;
    s = s.replace(/m$/i, '');
  }
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) {
    s = s.replace(/,/g, '');
  } else if (s.includes(',') && !s.includes('.')) {
    s = s.replace(',', '.');
  } else {
    s = s.replace(/,/g, '');
  }
  s = s.replace(/[^\d.]/g, '');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n * mul : null;
}

/** Formato miles con punto: $12.600 · $124.900 */
function formatMonto(raw) {
  const n = parseMonto(raw);
  if (n == null) return raw != null && raw !== '' ? String(raw) : '—';
  const entero = Math.round(n);
  const neg = entero < 0;
  const digits = String(Math.abs(entero));
  const conMiles = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${neg ? '-' : ''}$${conMiles}`;
}

function parseMultiplicador(texto, apuesta, premio) {
  if (texto) {
    const m = /(\d{1,4})\s*[x×]/i.exec(String(texto));
    if (m) return Number(m[1]);
  }
  const a = parseMonto(apuesta);
  const p = parseMonto(premio);
  if (a > 0 && p > 0) {
    // Apuesta barra = 4 bonos; el × del sector suele ser premio / (apuesta/4).
    const porBono = a % 50 === 0 && a >= 50 ? a / 4 : a;
    if (porBono > 0) return Math.round(p / porBono);
  }
  return null;
}

/**
 * Detecta cambios DOM (apuesta / premio / saldo) y escribe log.
 */
function registrarCambiosDom({
  cuenta,
  bar,
  prev,
  botArmado,
  apuestaOk,
  bodySnippet = '',
  horaTag = null,
}) {
  if (!cuenta || !bar) return;
  const p = prev || {};
  const ap = bar.apuesta != null ? String(bar.apuesta) : null;
  const pr = bar.premio != null ? String(bar.premio) : null;
  const sal = bar.saldo != null ? String(bar.saldo) : null;

  const mult = parseMultiplicador(bodySnippet, ap, pr);

  if (ap && ap !== p.apuesta && parseMonto(ap) > 0) {
    appendLog({
      tipo: botArmado && apuestaOk ? 'apuesta_bot' : 'apuesta',
      cuentaId: cuenta.id,
      color: cuenta.color,
      horaTag,
      montoApuesta: ap,
      premio: pr,
      saldo: sal,
      multiplicador: mult,
      notas: botArmado && apuestaOk ? 'Señal ON+zona' : 'Cambio en barra APUESTA',
      fuente: 'dom',
    });
  }

  if (pr && pr !== p.premio && parseMonto(pr) > 0) {
    appendLog({
      tipo: 'premio',
      cuentaId: cuenta.id,
      color: cuenta.color,
      horaTag,
      montoApuesta: ap || p.apuesta,
      premio: pr,
      saldo: sal,
      multiplicador: mult,
      notas: mult ? `≈ ${mult}x` : 'Premio en barra',
      fuente: 'dom',
    });
  }
}

module.exports = {
  LOG_FILE,
  UI_PULSE_FILE,
  appendLog,
  readLog,
  readUiPulse,
  bumpUiPulse,
  registrarCambiosDom,
  parseMonto,
  formatMonto,
  parseMultiplicador,
  esCobroGanancia,
};
