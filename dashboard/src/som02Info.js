/**
 * SOM02 — chip sombra (mediana huecos H-1 + fermión/cupo).
 * Espejo de src/motor.py · Tips INFO.
 */
import { dist, pad } from "./mesa.js";

function pasoSombra(islas) {
  const xs = [...new Set((islas || []).map((x) => ((x % 60) + 60) % 60))].sort(
    (a, b) => a - b
  );
  if (xs.length < 2) return 4;
  const gaps = [];
  for (let i = 0; i < xs.length - 1; i++) gaps.push((xs[i + 1] - xs[i] + 60) % 60);
  gaps.push((xs[0] + 60 - xs[xs.length - 1]) % 60);
  const buenos = gaps.filter((g) => g >= 1 && g <= 20);
  if (!buenos.length) return 4;
  const s = [...buenos].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
}

function minDistCand(cand, chips) {
  const bs = chips || [];
  if (!bs.length) return 99;
  return Math.min(...bs.map((c) => dist(cand, c)));
}

/**
 * @returns {{ ok: boolean, cand: number|null, paso: number, motivo: string, chips: number[] }}
 */
export function proponerSom02Chip({
  chips = [],
  h1 = [],
  nGClima = 10,
} = {}) {
  const base = [...new Set((chips || []).map((x) => ((x % 60) + 60) % 60))];
  const foto = [...new Set((h1 || []).map((x) => ((x % 60) + 60) % 60))];
  const clima = Math.max(7, Math.min(13, Number(nGClima) || 10));

  if (!foto.length) {
    return { ok: false, cand: null, paso: 4, motivo: "sin_foto_H-1", chips: base.sort((a, b) => a - b) };
  }
  if (base.length >= clima) {
    return {
      ok: false,
      cand: null,
      paso: pasoSombra(foto),
      motivo: "cupo_lleno",
      chips: base.sort((a, b) => a - b),
    };
  }

  const paso = pasoSombra(foto);
  const ultima = Math.max(...foto);
  const cand = (ultima + paso) % 60;

  if (cand === 1) {
    return { ok: false, cand, paso, motivo: "veto_minuto_01", chips: base.sort((a, b) => a - b) };
  }
  if (base.includes(cand)) {
    return { ok: false, cand, paso, motivo: "ya_en_boleto", chips: base.sort((a, b) => a - b) };
  }
  if (minDistCand(cand, base) < 2) {
    return { ok: false, cand, paso, motivo: "fermion_d_lt_2", chips: base.sort((a, b) => a - b) };
  }

  return {
    ok: true,
    cand,
    paso,
    motivo: "ok",
    chips: [...base, cand].sort((a, b) => a - b),
    ultima,
  };
}

/** Tips cuando SOM02 está cableado en el boleto prod. */
export function som02ProdTip(tiro, meta = {}) {
  if (!tiro || tiro.rol !== "sombra") return null;
  const m = tiro.minuto;
  const a = (m + 59) % 60;
  const d = (m + 1) % 60;
  const paso = meta?.paso ?? "?";
  return {
    id: "som02-prod",
    minuto: m,
    resumen:
      `SOM02 prod: ficha min ${pad(m)} (paso ~${paso} desde H-1). ` +
      "Cableada al motor — monitoreo online.",
    detalle: [
      `Chip sombra: ${pad(m)} cubre ${pad(a)} · ${pad(m)} · ${pad(d)} (TIBIO, rol sombra).`,
      "Misma zona que el tip de reloj; ahora sí está en el boleto.",
    ],
  };
}

/** Fallback si prod no incluyó sombra pero el lab la propondría (no debería pasar). */
export function som02ChipTip(proposal) {
  if (!proposal?.ok || proposal.cand == null) return null;
  const m = proposal.cand;
  const a = (m + 59) % 60;
  const d = (m + 1) % 60;
  return {
    id: "som02-chip",
    minuto: m,
    resumen:
      `SOM02 pendiente: min ${pad(m)} no entró al boleto (${proposal.motivo || "?"}).`,
    detalle: [
      `Propuesta lab: ${pad(m)} cubre ${pad(a)} · ${pad(m)} · ${pad(d)}.`,
      `Origen: max(H-1) ${pad(proposal.ultima ?? "?")} + paso ~${proposal.paso}.`,
    ],
  };
}
