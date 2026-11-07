/**
 * Señal al bot desde extracción (no depende del POST del dashboard).
 * El dashboard puede seguir escribiendo brilloFp; esto mantiene tip/enCurso/reloj vivos.
 */
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const LINEAS_FILE = path.join(DIR, 'extraccion-en-vivo.txt');
const SENAL_FILE = path.join(DIR, 'jokerbets-senal.json');
const SIM_POOL7_FILE = path.join(DIR, 'jokerbets-simul-pool7.json');

function pad2(n) {
  return String(n).padStart(2, '0');
}

function leerJson(file, fallback) {
  try {
    if (!fs.existsSync(file)) return fallback;
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  } catch (_) {
    return fallback;
  }
}

function horaDesdeTag(tag) {
  const m = /^h(\d{1,2})-/i.exec(String(tag || '').trim());
  return m ? Number(m[1]) : null;
}

function minutoDesdeEnCurso(enCurso) {
  const s = String(enCurso || '').trim();
  let m = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(s);
  if (m) return Number(m[2]) + Number(m[3]) / 60;
  m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (m) return Number(m[1]) + Number(m[2]) / 60;
  return null;
}

function enZonaPool7(enCurso, tip) {
  if (!enCurso || tip == null || Number.isNaN(Number(tip))) return false;
  const m = minutoDesdeEnCurso(enCurso);
  if (m == null) return false;
  const minTiro = Math.floor(m);
  const d = Math.abs((minTiro % 60) - (Number(tip) % 60));
  return Math.min(d, 60 - d) <= 1;
}

function enVentanaPool7Reloj(relojMinuto, tip) {
  if (tip == null || Number.isNaN(Number(tip))) return false;
  if (relojMinuto == null || Number.isNaN(Number(relojMinuto))) return false;
  const m = Math.floor(Number(relojMinuto));
  const d = Math.abs((m % 60) - (Number(tip) % 60));
  return Math.min(d, 60 - d) <= 1;
}

function enZonaApuestaLive({ enCurso, tip, relojMinuto }) {
  if (enVentanaPool7Reloj(relojMinuto, tip)) return true;
  return enZonaPool7(enCurso, tip);
}

function percentile(xs, p, fallback = 5) {
  if (!xs.length) return fallback;
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(sorted.length * p)));
  return sorted[idx];
}

function tipLc01(luces) {
  const sorted = [...new Set(luces || [])].sort((a, b) => a - b);
  if (!sorted.length) return { tip: null, estado: 'calculando' };
  const gaps = [];
  for (let i = 1; i < sorted.length; i += 1) gaps.push(sorted[i] - sorted[i - 1]);
  const gap = percentile(gaps, 0.3, 5);
  const T = sorted[sorted.length - 1];
  const tip = Math.min(59, Math.max(T + 1, T + gap));
  return { tip, estado: 'listo' };
}

function parseUltimaHora(texto) {
  const lines = String(texto || '')
    .split(/\r?\n/)
    .map(l => l.trim())
    .filter(Boolean);
  let tag = '';
  let body = [];
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    if (/^h\d{1,2}-\d{6}$/i.test(lines[i])) {
      tag = lines[i].toLowerCase();
      body = lines.slice(i + 1);
      break;
    }
  }
  if (!tag) return null;
  const luces = [];
  let nTiros = 0;
  let enJuego = null;
  for (const ln of body) {
    if (/ en juego/i.test(ln)) {
      const j = /(\d{2}):(\d{2})\s+en juego/i.exec(ln);
      if (j) enJuego = { min: Number(j[1]), sec: Number(j[2]) };
      continue;
    }
    const tr = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})\s+(R|G\d)/i.exec(ln);
    if (tr) {
      nTiros += 1;
      if (tr[5].toUpperCase().startsWith('G')) {
        luces.push(Number(tr[1]));
      }
    }
  }
  return { tag, luces, nTiros, enJuego };
}

function gapDesdeUltimaG(luces, nTiros) {
  if (!luces.length) return nTiros;
  return Math.max(0, nTiros - luces.length);
}

/** Bandas Pool 7 ON: fuerte / muy fuerte / supernova (media≥68 o pill pura). */
const POOL7_BRILLO_ON = new Set(['fuerte', 'muy fuerte', 'supernova']);

/**
 * brilloFp = tag|fase|pill|nG|acum|meanG (desde dashboard buildBrilloLectura).
 * El sync no recalcula Brillo; sí puede leer el pill/mean del fp.
 */
function pool7BrilloOkDesdeFp(brilloFp) {
  const parts = String(brilloFp || '').split('|');
  if (parts.length < 3) return false;
  const pill = String(parts[2] || '')
    .toLowerCase()
    .replace(/_/g, ' ')
    .trim();
  if (POOL7_BRILLO_ON.has(pill)) return true;
  const mean = Number(parts[5]);
  if (Number.isFinite(mean) && mean >= 68) return true;
  const acum = Number(parts[4]);
  if (Number.isFinite(acum) && acum >= 850) return true;
  return false;
}

function buildEnCurso(horaTag, pendienteStart, enJuego, now) {
  if (pendienteStart instanceof Date && !Number.isNaN(pendienteStart.getTime())) {
    const h = horaTag != null ? horaTag : pendienteStart.getHours();
    return `${h}:${pad2(pendienteStart.getMinutes())}:${pad2(pendienteStart.getSeconds())}`;
  }
  if (enJuego && horaTag != null) {
    const sec = now.getSeconds();
    return `${horaTag}:${pad2(enJuego.min)}:${pad2(enJuego.sec != null ? enJuego.sec : sec)}`;
  }
  return '';
}

/**
 * Calcula señal Pool 7 desde cinta (sin escribir disco).
 * @param {{ pendienteStart?: Date|null, lineasMemoria?: string[] }} ctx
 */
function buildSenalPool7(ctx = {}) {
  let parsed = null;
  if (Array.isArray(ctx.lineasMemoria) && ctx.lineasMemoria.length) {
    const tagLine = ctx.lineasMemoria.find(l => /^h\d{1,2}-\d{6}$/i.test(l.trim()));
    const tag = tagLine ? tagLine.trim().toLowerCase() : '';
    const idx = ctx.lineasMemoria.indexOf(tagLine);
    const body = idx >= 0 ? ctx.lineasMemoria.slice(idx + 1) : ctx.lineasMemoria;
    const fake = [tag, ...body].join('\n');
    parsed = parseUltimaHora(fake);
  }
  if (!parsed) {
    try {
      if (!fs.existsSync(LINEAS_FILE)) return null;
      parsed = parseUltimaHora(fs.readFileSync(LINEAS_FILE, 'utf-8'));
    } catch (_) {
      return null;
    }
  }
  if (!parsed?.tag) return null;

  const now = new Date();
  const horaTag = horaDesdeTag(parsed.tag);
  const prev = leerJson(SENAL_FILE, {});
  const simF = leerJson(SIM_POOL7_FILE, { activo: false });
  /** Solo el toggle (jokerbets-simul-pool7.json). No pegarse de prev.simulPool7. */
  const simulPool7 = Boolean(simF.activo);

  const tipInfo = tipLc01(parsed.luces);
  const tip = tipInfo.tip;
  const enCurso = buildEnCurso(horaTag, ctx.pendienteStart, parsed.enJuego, now);

  let relojMinuto = null;
  let relojSegundo = null;
  if (horaTag != null && now.getHours() === horaTag) {
    relojMinuto = now.getMinutes();
    relojSegundo = now.getSeconds();
  } else if (enCurso) {
    const m = minutoDesdeEnCurso(enCurso);
    if (m != null) {
      relojMinuto = Math.floor(m);
      relojSegundo = Math.round((m % 1) * 60);
    }
  }

  const enZonaApuesta = enZonaApuestaLive({ enCurso, tip, relojMinuto });
  const enZona = enZonaApuesta;
  const gapTiro = gapDesdeUltimaG(parsed.luces, parsed.nTiros);
  const ventanaCaliente = simulPool7 ? true : gapTiro == null || gapTiro <= 3;
  const brilloFp = prev.brilloFp || '';
  const pool7BrilloOk = pool7BrilloOkDesdeFp(brilloFp);
  /** SIM: tip±1 + Brillo fuerte+. Prod: Pool7 + Puerta A. */
  const permitirClics = simulPool7
    ? tip != null && enVentanaPool7Reloj(relojMinuto, tip) && pool7BrilloOk
    : Boolean(prev.puertaA) &&
      (prev.interruptor || 'OFF') !== 'OFF' &&
      enZonaApuesta &&
      ventanaCaliente;

  const tipFinal = tip ?? (prev.tip != null ? prev.tip : null);
  const enZonaFinal = enZonaApuestaLive({ enCurso, tip: tipFinal, relojMinuto });
  const permitirFinal = simulPool7
    ? tipFinal != null &&
      enVentanaPool7Reloj(relojMinuto, tipFinal) &&
      pool7BrilloOk
    : permitirClics;

  return {
    ...prev,
    actualizado: now.toISOString().slice(0, 19),
    tag: parsed.tag,
    interruptor: simulPool7 ? 'ON' : prev.interruptor || 'OFF',
    puertaA: simulPool7 ? true : Boolean(prev.puertaA),
    enZona: enZonaFinal,
    enZonaApuesta: enZonaFinal,
    enCurso,
    nTiros: parsed.nTiros,
    brilloFp,
    relojMinuto,
    relojSegundo,
    tip: tipFinal,
    tipEstado: tipFinal != null ? tipInfo.estado : 'calculando',
    permitirClics: permitirFinal,
    gapTiro,
    ventanaCaliente,
    simulPool7,
    pool7BrilloOk,
    puertaGoBrillo: Boolean(prev.puertaGoBrillo),
    viaApuesta: prev.puertaGoBrillo
      ? prev.viaApuesta || 'puertaA'
      : simulPool7
        ? 'sim'
        : prev.viaApuesta === 'sim'
          ? null
          : prev.viaApuesta || null,
    _senalFuente: 'extraccion-sync',
  };
}

function syncDesdeExtraccion(ctx = {}) {
  const payload = buildSenalPool7(ctx);
  if (!payload) return null;
  try {
    fs.writeFileSync(SENAL_FILE, JSON.stringify(payload, null, 2) + '\n', 'utf-8');
  } catch (_) {
    return null;
  }
  return payload;
}

function senalEstaVieja(s, maxSec = 8) {
  if (!s?.actualizado) return true;
  const t = Date.parse(String(s.actualizado).replace(' ', 'T'));
  if (Number.isNaN(t)) return true;
  return Date.now() - t > maxSec * 1000;
}

function refrescarSiHaceFalta(ctx) {
  const s = leerJson(SENAL_FILE, {});
  const needs =
    senalEstaVieja(s, 8) ||
    s.tip == null ||
    s.relojMinuto == null ||
    s._senalFuente !== 'extraccion-sync';
  if (!needs) return s;
  return syncDesdeExtraccion(ctx) || s;
}

module.exports = {
  buildSenalPool7,
  syncDesdeExtraccion,
  refrescarSiHaceFalta,
  senalEstaVieja,
  enVentanaPool7Reloj,
  pool7BrilloOkDesdeFp,
};
