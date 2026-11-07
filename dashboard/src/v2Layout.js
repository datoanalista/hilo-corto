/** Geometría del tablero V2 (bloques 00–19 / 20–39 / 40–59). */

export const BLOQUES = [
  { id: 0, lo: 0, hi: 19, label: "00–19" },
  { id: 1, lo: 20, hi: 39, label: "20–39" },
  { id: 2, lo: 40, hi: 59, label: "40–59" },
];

export const SLOTS_BLOQUE = 20;
/** Bloque en juego vs laterales de la hora: 60-20-20. */
export const PESO_EXP = 0.6;
export const PESO_SHR = 0.2;
export const GAP_EXP = 2.2;
export const GAP_SHR = 2.4;

export function bloqueDeMinuto(m) {
  if (m <= 19) return 0;
  if (m <= 39) return 1;
  return 2;
}

export function pesosBloques(expandido) {
  return [0, 1, 2].map((i) => (i === expandido ? PESO_EXP : PESO_SHR));
}

export function rangoBloque(b, pesos) {
  let start = 0;
  for (let i = 0; i < b; i += 1) start += pesos[i] * 100;
  const width = pesos[b] * 100;
  const pad = Math.min(width * 0.05, 1.7);
  const usable = Math.max(width - 2 * pad, 0);
  return { start: start + pad, end: start + pad + usable, width, pad, usable };
}

export function minutoAPct(m, pesos) {
  const mm = Math.max(0, Math.min(59, Math.floor(Number(m) || 0)));
  const b = bloqueDeMinuto(mm);
  const { start, usable } = rangoBloque(b, pesos);
  const lo = BLOQUES[b].lo;
  const slot = mm - lo;
  const frac = (slot + 0.5) / SLOTS_BLOQUE;
  return start + frac * usable;
}

export function tiempoAPct(tMin, pesos) {
  const mm = Math.max(0, Math.min(59.999, Number(tMin) || 0));
  const b = bloqueDeMinuto(Math.floor(mm));
  const { start, usable } = rangoBloque(b, pesos);
  const lo = BLOQUES[b].lo;
  const slot = mm - lo;
  const frac = Math.max(0, Math.min(1, slot / SLOTS_BLOQUE));
  return start + frac * usable;
}

/** MM:SS o HH:MM:SS del tiro "en curso" → minuto continuo 0–59.999 */
export function minutoDesdeEnCurso(enCurso) {
  const s = String(enCurso || "").trim();
  let m = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(s);
  if (m) return Number(m[2]) + Number(m[3]) / 60;
  m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (m) return Number(m[1]) + Number(m[2]) / 60;
  return null;
}

export function computeTPlay({
  enCursoKey = "",
  sosteniendoHora = false,
  ultimoMinuto = null,
  enHora = false,
  reloj = null,
} = {}) {
  const enCursoStart = minutoDesdeEnCurso(enCursoKey);
  if (sosteniendoHora) {
    return ultimoMinuto != null ? Number(ultimoMinuto) : 59;
  }
  let m = null;
  if (enHora && reloj && reloj.minuto != null) {
    m = reloj.minuto + (reloj.segundo || 0) / 60;
  }
  if (enCursoStart != null) {
    m = m == null ? enCursoStart : Math.max(m, enCursoStart);
  }
  if (ultimoMinuto != null && !Number.isNaN(Number(ultimoMinuto))) {
    m = m == null ? Number(ultimoMinuto) : Math.max(m, Number(ultimoMinuto));
  }
  if (m == null) return 0;
  return Math.min(59.999, m);
}

export function cortesBloques(pesos) {
  const out = [0];
  let acc = 0;
  for (let i = 0; i < 2; i += 1) {
    acc += pesos[i] * 100;
    out.push(acc);
  }
  return out;
}

function antiSolape(natural, lo, hi, minGap) {
  const n = natural.length;
  if (n === 0) return [];
  if (n === 1) {
    return [Math.max(lo, Math.min(hi, natural[0]))];
  }
  let pos = natural.map((p) => Math.max(lo, Math.min(hi, p)));
  const span = hi - lo;
  const need = (n - 1) * minGap;
  if (need > span) {
    for (let i = 0; i < n; i += 1) {
      pos[i] = lo + (i / (n - 1)) * span;
    }
    return pos;
  }
  for (let pass = 0; pass < 10; pass += 1) {
    for (let i = 1; i < n; i += 1) {
      if (pos[i] - pos[i - 1] < minGap) {
        const mid = (pos[i] + pos[i - 1]) / 2;
        pos[i - 1] = mid - minGap / 2;
        pos[i] = mid + minGap / 2;
      }
    }
    if (pos[0] < lo) {
      const sh = lo - pos[0];
      pos = pos.map((p) => p + sh);
    }
    if (pos[n - 1] > hi) {
      const sh = pos[n - 1] - hi;
      if (pos[0] - sh >= lo) {
        pos = pos.map((p) => p - sh);
      } else {
        for (let i = 0; i < n; i += 1) {
          pos[i] = lo + (i / (n - 1)) * span;
        }
        break;
      }
    }
  }
  return pos;
}

export function posicionesMarksFila(chips, pesos, bloqueExpandido) {
  const pos = new Map();
  const porBloque = [[], [], []];
  for (const m of new Set(chips || [])) {
    porBloque[bloqueDeMinuto(m)].push(m);
  }
  for (let b = 0; b < 3; b += 1) {
    const list = [...porBloque[b]].sort((a, c) => a - c);
    if (!list.length) continue;
    const { start, end } = rangoBloque(b, pesos);
    const expanded = b === bloqueExpandido;
    const natural = list.map((m) => minutoAPct(m, pesos));
    const gap = expanded ? GAP_EXP : GAP_SHR;
    const placed = antiSolape(natural, start, end, gap);
    list.forEach((m, i) => pos.set(m, placed[i]));
  }
  return pos;
}

export function gradientBloques(pesos, bloqueExpandido) {
  const tonos = [
    "rgba(42, 58, 82, 0.28)",
    "rgba(68, 58, 42, 0.22)",
    "rgba(58, 46, 78, 0.26)",
  ];
  const tonosOn = [
    "rgba(52, 78, 108, 0.38)",
    "rgba(88, 72, 48, 0.32)",
    "rgba(78, 58, 98, 0.36)",
  ];
  const stops = [];
  let acc = 0;
  for (let i = 0; i < 3; i += 1) {
    const c = i === bloqueExpandido ? tonosOn[i] : tonos[i];
    stops.push(`${c} ${acc}%`);
    acc += pesos[i] * 100;
    stops.push(`${c} ${acc}%`);
  }
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

/** ¿Vale la pena un tick ligero solo para avisoCerca de este chip? */
export function chipNearCercaWindow(m, T) {
  if (T == null || m == null) return false;
  const diff = m - T;
  return diff >= -2 && diff <= 5;
}
