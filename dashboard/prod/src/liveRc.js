/**
 * Pool 10 LIVE-RC — RC-04-MULTI93 (lab-live-recompute R2).
 * Recomputa chips intra-hora: reloj p30 · tips {c, c+1, c+2} por cada G vista.
 */

function percentile(xs, p, fallback = 5) {
  if (!xs.length) return fallback;
  const ys = [...xs].sort((a, b) => a - b);
  const idx = Math.min(ys.length - 1, Math.max(0, Math.floor(ys.length * p)));
  return ys[idx];
}

function tipReloj(T, gapsHist, p = 0.3) {
  if (T >= 59) return null;
  const gap = percentile(gapsHist, p);
  return Math.min(59, Math.max(T + 1, T + gap));
}

/** Acumula banda multi93 sobre prefix de luces (extracción en vivo). */
export function chipsLiveRc(luces) {
  const sorted = [...new Set(luces || [])].sort((a, b) => a - b);
  const tips = new Set();
  let gapsHist = [];

  const emit = (T, gh) => {
    const c = tipReloj(T, gh);
    if (c == null) return;
    for (const x of [c, c + 1, c + 2]) {
      if (T < x && x <= 59) tips.add(x);
    }
  };

  for (let i = 0; i <= sorted.length; i += 1) {
    const prefix = sorted.slice(0, i);
    const T = prefix.length ? prefix[prefix.length - 1] : -1;
    gapsHist = [];
    for (let k = 1; k < prefix.length; k += 1) {
      gapsHist.push(prefix[k] - prefix[k - 1]);
    }
    emit(T, gapsHist);
  }

  return [...tips].sort((a, b) => a - b);
}

/** Banda MULTI93 del paso actual (prefix luces → tips {c,c+1,c+2}). */
export function bandaLiveRcPaso(luces) {
  const sorted = [...new Set(luces || [])].sort((a, b) => a - b);
  const T = sorted.length ? sorted[sorted.length - 1] : -1;
  const gapsHist = [];
  for (let k = 1; k < sorted.length; k += 1) {
    gapsHist.push(sorted[k] - sorted[k - 1]);
  }
  const c = tipReloj(T, gapsHist);
  if (c == null) return [];
  const out = [];
  for (const x of [c, c + 1, c + 2]) {
    if (T < x && x <= 59) out.push(x);
  }
  return out;
}

export const LIVE_RC_META = {
  id: "live-rc",
  nombre: "Pool 10",
  motor: "LIVE-RC · MULTI93 reloj p30 {c,c+1,c+2}",
};
