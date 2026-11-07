import { pad } from "./mesa.js";

/** MM:SS o HH:MM:SS del tiro en curso → minuto 0–59.999 */
export function minutoDesdeEnCurso(enCurso) {
  const s = String(enCurso || "").trim();
  let m = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(s);
  if (m) return Number(m[2]) + Number(m[3]) / 60;
  m = /^(\d{1,2}):(\d{2})$/.exec(s);
  if (m) return Number(m[1]) + Number(m[2]) / 60;
  return null;
}

/** Zona Pool 7: tiro en curso dentro de tip ±1 (ignora reloj PC). */
export function enZonaPool7(enCurso, tip) {
  if (!enCurso || tip == null || Number.isNaN(Number(tip))) return false;
  const m = minutoDesdeEnCurso(enCurso);
  if (m == null) return false;
  const minTiro = Math.floor(m);
  const d = Math.abs((minTiro % 60) - (Number(tip) % 60));
  return Math.min(d, 60 - d) <= 1;
}

/** Minuto continuo alineado al playhead (reloj + en curso + último cierre). */
export function minutoLivePlayhead({ reloj, tiroEnCurso, ultimoCierre = null } = {}) {
  let m =
    reloj && reloj.minuto != null
      ? reloj.minuto + (reloj.segundo || 0) / 60
      : 0;
  const desdeCurso = minutoDesdeEnCurso(tiroEnCurso);
  if (desdeCurso != null) m = Math.max(m, desdeCurso);
  if (ultimoCierre != null && !Number.isNaN(ultimoCierre)) {
    m = Math.max(m, Number(ultimoCierre));
  }
  return Math.min(59.999, m);
}

/** Primera ficha estrictamente después de T (misma hora). */
export function nextChip(chips, T) {
  const fut = (chips || []).filter((m) => m > T);
  return fut.length ? Math.min(...fut) : null;
}

function mediana(xs, fallback = 5) {
  if (!xs.length) return fallback;
  if (xs.length === 1) return xs[0];
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function percentile(xs, p, fallback = 5) {
  if (!xs.length) return fallback;
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(sorted.length * p)));
  return sorted[idx];
}

function harmonic(xs, fallback = 5) {
  if (!xs.length) return fallback;
  const s = xs.reduce((acc, x) => acc + 1 / Math.max(1, x), 0);
  return Math.round(xs.length / s);
}

/** gapMode: p30 (default LC-01) | p25 | harmonic | median */
function huecoTipico(gaps, mode = "p30", fallback = 5) {
  switch (mode) {
    case "p25":
      return percentile(gaps, 0.25, fallback);
    case "p30":
      return percentile(gaps, 0.30, fallback);
    case "median":
      return mediana(gaps, fallback);
    case "harmonic":
    default:
      return harmonic(gaps, fallback);
  }
}

function pickClosest(pool, target) {
  if (!pool.length) return null;
  let tip = pool[0];
  let best = Math.abs(tip - target);
  for (const c of pool) {
    const d = Math.abs(c - target);
    if (d < best || (d === best && c < tip)) {
      best = d;
      tip = c;
    }
  }
  return tip;
}

/**
 * Tip LC-01 reloj-solo (livecero F3 · lightgreen 288h).
 * tip = clip(T + p30(gaps)) · SIN menú de chips.
 * Walk: banda 44.8% · hold 47.4% (+2.5pp vs LG-43).
 * LG-43 ventana+closest = ARCHIVO (mode: "ventana").
 *
 * modo:
 *   "reloj"   (default LC-01) — tip = target del hueco
 *   "ventana" (ARCH LG-43)    — closest en pool chips
 *
 * minutoAhora (modo reloj): solo estado UI — si reloj pasó el tip → "pasado".
 * El número tip NO cambia (LC-01 = última G + hueco). Pool 7 usa null.
 */
export function tipSiguienteG({
  mesasChips = [],
  luces = [],
  medGapFallback = 5,
  ventanaDelta = 2,
  gapMode = "p30",
  modo = "reloj",
  minutoAhora = null,
} = {}) {
  const sorted = [...new Set(luces || [])].sort((a, b) => a - b);
  const gaps = [];
  for (let i = 1; i < sorted.length; i += 1) {
    gaps.push(sorted[i] - sorted[i - 1]);
  }
  const gap = huecoTipico(gaps, gapMode, medGapFallback);

  const T = sorted.length ? sorted[sorted.length - 1] : -1;
  const target = Math.min(59, Math.max(T + 1, T + gap));
  const hi = Math.min(59, T + gap + ventanaDelta);

  const nexts = [];
  for (const chips of mesasChips) {
    const n = nextChip(chips, T);
    if (n != null) nexts.push(n);
  }
  const cands = [...new Set(nexts)].sort((a, b) => a - b);

  // ── LC-01 reloj-solo ──
  if (modo === "reloj") {
    if (T < 0) {
      return {
        tip: null,
        label: "calculando…",
        estado: "calculando",
        target,
        medGap: gap,
        T,
        hi,
        cands,
        why: "sin luces aún · esperando primera G",
        algo: "LC-01",
      };
    }
    const tip = target;
    const pasado =
      minutoAhora != null &&
      tip != null &&
      Math.floor(minutoAhora) > tip;
    const relojTxt =
      minutoAhora != null
        ? `${pad(Math.floor(minutoAhora))}:${pad(Math.round((minutoAhora % 1) * 60))}`
        : "—";
    return {
      tip,
      label: pad(tip),
      estado: pasado ? "pasado" : "listo",
      target,
      medGap: gap,
      T,
      hi,
      cands,
      why: pasado
        ? `LC-01 tip ${pad(tip)} pasó · reloj ${relojTxt} · esperando G`
        : `LC-01 reloj · ${gapMode}~${gap} · tip ${pad(tip)} · sin chips`,
      algo: "LC-01",
    };
  }

  // ── ARCH: LG-43 ventana + closest ──
  const pool = [];
  for (const chips of mesasChips) {
    for (const m of chips || []) {
      if (m > T && m <= hi) pool.push(m);
    }
  }
  const vivos =
    minutoAhora == null ? pool : pool.filter((m) => m >= minutoAhora);

  if (!vivos.length) {
    return {
      tip: null,
      label: "calculando…",
      estado: "calculando",
      target,
      medGap: gap,
      T,
      hi,
      cands,
      why:
        minutoAhora != null
          ? `sin tip futuro ≥${pad(minutoAhora)} · ventana agotada`
          : "sin fichas en ventana",
      algo: "LG-43",
    };
  }

  const tip = pickClosest(vivos, Math.max(target, minutoAhora ?? target));

  return {
    tip,
    label: pad(tip),
    estado: "listo",
    target,
    medGap: gap,
    T,
    hi,
    cands,
    why: `LG-43 ventana δ=${ventanaDelta} · ${gapMode}~${gap} · target ${pad(target)} · pool ${[
      ...new Set(vivos),
    ]
      .sort((a, b) => a - b)
      .map(pad)
      .join(",")}`,
    algo: "LG-43",
  };
}
