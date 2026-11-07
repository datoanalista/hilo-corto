/**
 * Log estructurado para análisis de performance (agente / backtest vivo).
 * Una línea JSON por evento → jokerbets-performance.jsonl
 */
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const PERF_FILE = path.join(DIR, 'jokerbets-performance.jsonl');
const CONFIG_FILE = path.join(DIR, '..', '..', 'jokerbets', 'config.json');
const MAX_LINES_READ = 50_000;

const MIN_MS_SNAPSHOT = 120_000;

function leerArranqueUsd() {
  try {
    if (!fs.existsSync(CONFIG_FILE)) return 20_000;
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    const n = Number(cfg.arranqueUsd);
    return Number.isFinite(n) && n > 0 ? n : 20_000;
  } catch (_) {
    return 20_000;
  }
}

function leerApuestaModo() {
  try {
    if (!fs.existsSync(CONFIG_FILE)) return '50';
    const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    const m = String(cfg.apuestaModo || '50').trim();
    if (m === '150' || m === '200') return m;
    return '50';
  } catch (_) {
    return '50';
  }
}

/** Parsea SALDO $12.345, $6K, $1.2M */
function parseSaldo(raw) {
  if (raw == null || raw === '') return null;
  let s = String(raw).trim().replace(/\s/g, '');
  const up = s.toUpperCase();
  let mul = 1;
  if (/K$/i.test(s)) {
    mul = 1_000;
    s = s.replace(/K$/i, '');
  } else if (/M$/i.test(up)) {
    mul = 1_000_000;
    s = s.replace(/M$/i, '');
  }
  s = s.replace(/[^\d.]/g, '');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n * mul : null;
}

function appendPerf(row) {
  const entry = {
    ts: new Date().toISOString(),
    arranqueUsd: leerArranqueUsd(),
    apuestaModo: leerApuestaModo(),
    ...row,
  };
  try {
    fs.appendFileSync(PERF_FILE, JSON.stringify(entry) + '\n', 'utf-8');
  } catch (_) {}
  return entry;
}

function senalMini(senal) {
  if (!senal) return null;
  return {
    tag: senal.tag || null,
    interruptor: senal.interruptor || null,
    puertaA: !!senal.puertaA,
    puertaAFase: senal.puertaAFase || null,
    tip: senal.tip ?? null,
    enZonaApuesta: !!senal.enZonaApuesta,
    simulPool7: !!senal.simulPool7,
  };
}

/**
 * Actualiza pico/drawdown por cuenta y escribe snapshot si cambió el saldo o pasó tiempo.
 */
function registrarSaldo({ cuenta, saldoRaw, st, senal, motivo = 'tick' }) {
  if (!cuenta || !st) return null;
  const saldo = parseSaldo(saldoRaw);
  if (saldo == null) return null;

  const prev = st._analisisLastSaldo;
  const now = Date.now();
  if (st.saldoPeak == null || saldo > st.saldoPeak) st.saldoPeak = saldo;
  const drawdown = Math.max(0, (st.saldoPeak || saldo) - saldo);
  const arranque = st.arranqueUsd != null ? st.arranqueUsd : leerArranqueUsd();
  if (st.arranqueUsd == null) st.arranqueUsd = arranque;

  const cambio = prev == null || Math.abs(saldo - prev) >= 50;
  const tiempo = !st._analisisLastAt || now - st._analisisLastAt >= MIN_MS_SNAPSHOT;
  if (!cambio && !tiempo) {
    st._analisisLastSaldo = saldo;
    return { saldo, drawdown, logged: false };
  }

  st._analisisLastSaldo = saldo;
  st._analisisLastAt = now;
  appendPerf({
    event: 'saldo_snapshot',
    motivo,
    cuentaId: cuenta.id,
    color: cuenta.color,
    saldo,
    saldoPeak: st.saldoPeak,
    drawdown,
    pnlDesdeArranque: saldo - arranque,
    frenoEmergencia: !!st.frenoEmergencia,
    senal: senalMini(senal),
  });
  return { saldo, drawdown, logged: true };
}

function registrarApuestaBot({ cuenta, senal, st, montoApuesta, objetivo, bono, clics, poolTip, minSlot, key }) {
  const saldo = parseSaldo(st.ultimoSaldo);
  appendPerf({
    event: 'apuesta_bot',
    cuentaId: cuenta.id,
    color: cuenta.color,
    montoApuesta: montoApuesta != null ? String(montoApuesta) : null,
    objetivoUsd: objetivo,
    bonoUsd: bono,
    clicsCentro: clics,
    poolTip,
    minSlot,
    apuestaKey: key,
    saldo,
    saldoPeak: st.saldoPeak ?? saldo,
    drawdown:
      st.saldoPeak != null && saldo != null ? Math.max(0, st.saldoPeak - saldo) : null,
    frenoEmergencia: !!st.frenoEmergencia,
    senal: senalMini(senal),
  });
}

function registrarPremio({ cuenta, senal, st, montoApuesta, premio, multiplicador }) {
  const a = parseSaldo(montoApuesta);
  const p = parseSaldo(premio);
  const saldo = parseSaldo(st.ultimoSaldo);
  appendPerf({
    event: 'premio',
    cuentaId: cuenta.id,
    color: cuenta.color,
    montoApuesta: montoApuesta != null ? String(montoApuesta) : null,
    premio: premio != null ? String(premio) : null,
    netoEstimado: a != null && p != null ? p - a : null,
    multiplicador: multiplicador ?? null,
    saldo,
    saldoPeak: st.saldoPeak ?? saldo,
    senal: senalMini(senal),
  });
}

function registrarFrenoEmergencia({ cuenta, senal, st, saldo, activo, notas }) {
  appendPerf({
    event: activo ? 'freno_emergencia_on' : 'freno_emergencia_off',
    cuentaId: cuenta.id,
    color: cuenta.color,
    saldo,
    saldoPeak: st.saldoPeak ?? saldo,
    umbralUsd: 6000,
    notas: notas || '',
    senal: senalMini(senal),
  });
}

function readPerf({ limit = 500, cuentaId = null, event = null } = {}) {
  if (!fs.existsSync(PERF_FILE)) return [];
  let lines;
  try {
    lines = fs.readFileSync(PERF_FILE, 'utf-8').split(/\r?\n/).filter(Boolean);
  } catch (_) {
    return [];
  }
  if (lines.length > MAX_LINES_READ) lines = lines.slice(-MAX_LINES_READ);
  const out = [];
  for (let i = lines.length - 1; i >= 0 && out.length < limit; i -= 1) {
    try {
      const ev = JSON.parse(lines[i]);
      if (cuentaId && ev.cuentaId !== cuentaId) continue;
      if (event && ev.event !== event) continue;
      out.push(ev);
    } catch (_) {}
  }
  return out;
}

module.exports = {
  PERF_FILE,
  parseSaldo,
  appendPerf,
  registrarSaldo,
  registrarApuestaBot,
  registrarPremio,
  registrarFrenoEmergencia,
  readPerf,
};
