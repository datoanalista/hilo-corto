/**
 * Opacidad INFO — tips lab cinta (castigo ~1h, día+1, hora flaca).
 * INFO · no boleto.
 */
import { anteriorTag, parseTag } from "./live.js";
import {
  GEN_SUM_OPACO,
  horasDeLineasCached,
} from "./generosidadInfo.js";

const MEAN_OPACO = 48;

/** Lab hora flaca · 883h */
const FLACA_EARLY_MAX = 19;
const FLACA_EARLY_NG = 1;
const FLACA_CIERRE_T = 40;
const FLACA_CIERRE_NG = 3;
const FLACA_CIERRE_ACUM = 250;
const FLACA_PREV_NG = 3;

/** Hora opaca: sum<450 o mean<42 (al cerrar). */
export function esHoraOpaca(sumG, meanG = null) {
  if (sumG != null && sumG < GEN_SUM_OPACO) return true;
  if (meanG != null && meanG < MEAN_OPACO) return true;
  return false;
}

function statsHoraEn(horas, tag) {
  if (!tag) return null;
  return horas.find((h) => h.tag === tag.toLowerCase()) || null;
}

function statsDiaAnteriorEn(horas, tag) {
  const t = parseTag(tag);
  if (!t) return null;
  const prev = new Date(t.anio, t.mes - 1, t.dia);
  prev.setDate(prev.getDate() - 1);
  const dayKey = `${prev.getDate()}-${prev.getMonth() + 1}-${prev.getFullYear()}`;
  const hs = horas.filter((h) => h.dayKey === dayKey);
  if (hs.length < 8) return null;
  const nOp = hs.filter((h) => h.opaca).length;
  return {
    n: hs.length,
    pOp: nOp / hs.length,
    tot: hs.reduce((a, x) => a + x.sumG, 0),
  };
}

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function nGEnBloque(tiros = [], T = 59, hi = FLACA_EARLY_MAX) {
  let n = 0;
  for (const t of tiros || []) {
    if (t.m0 > T || t.m0 > hi) continue;
    if (!String(t.color || "").toUpperCase().startsWith("G")) continue;
    if (lumenOf(t) == null) continue;
    n += 1;
  }
  return n;
}

function pushTip(tips, seen, tip) {
  if (!tip || seen.has(tip.id)) return;
  seen.add(tip.id);
  tips.push(tip);
}

/**
 * Tips opacidad para modal Brillo.
 */
export function buildOpacidadTips({
  tag = "",
  lineas = [],
  tone = "",
  meanG = null,
  acum = 0,
  T = 0,
  tiros = [],
  nG = null,
} = {}) {
  const tips = [];
  const seen = new Set();
  const horaOpacaAhora =
    tone === "opaco" ||
    (meanG != null && meanG <= MEAN_OPACO) ||
    (acum > 0 && acum < GEN_SUM_OPACO && T >= 40);

  if (horaOpacaAhora && T >= 15) {
    pushTip(tips, seen, {
      id: "castigo-1h",
      texto:
        "Hora opaca: el castigo de lumen suele durar ~1 h (racha mediana 1 · p90 2). La hora siguiente tiende a rebote, no a prolongarse.",
    });
  }

  const horas = lineas.length ? horasDeLineasCached(lineas) : [];
  const prevTag = anteriorTag(tag);
  const prevH = prevTag ? statsHoraEn(horas, prevTag) : null;

  if (prevH?.opaca && !horaOpacaAhora && T >= 10) {
    pushTip(tips, seen, {
      id: "post-opaca",
      texto:
        "La hora anterior cerró opaca — olor de normalización en suma/mean; no asumir que el día entero sigue apagado.",
    });
  }
  if (prevH?.opaca && horaOpacaAhora) {
    pushTip(tips, seen, {
      id: "racha-opaca",
      texto:
        "Dos horas seguidas opacas: raro (lift H→H+1 ~1,04). Si pasa, suele cortar en 1–2 h, no en rachas largas.",
    });
  }

  // H+1 tras hora muy flaca (lab-g-cola · hora flaca)
  if (
    prevH &&
    prevH.nG != null &&
    prevH.nG <= FLACA_PREV_NG &&
    !horaOpacaAhora &&
    T >= 5 &&
    T <= 45
  ) {
    pushTip(tips, seen, {
      id: "post-flaca-rebote",
      texto: `Hora anterior muy flaca (${prevH.nG} G · ${prevH.sumG} lumen) — olor rebote en suma y más G en lo que sigue (lab flaca · H+1). No es seguro.`,
      tono: "olor",
    });
  }

  // Perfil flaca de cierre en curso
  const nGNow = nG != null ? nG : nGEnBloque(tiros, T, T);
  if (
    T >= FLACA_CIERRE_T &&
    nGNow <= FLACA_CIERRE_NG &&
    acum > 0 &&
    acum < FLACA_CIERRE_ACUM &&
    !horaOpacaAhora
  ) {
    pushTip(tips, seen, {
      id: "flaca-cierre-perfil",
      texto:
        "Perfil flaca de cierre (pocas G, acum bajo) — olor opaca fuerte; en cinta nG≤5 cierra opaca ~85%. Poco margen para generosa.",
      tono: "olor",
      alerta: true,
    });
  }

  const diaPrev = statsDiaAnteriorEn(horas, tag);
  if (diaPrev && diaPrev.pOp >= 0.4) {
    pushTip(tips, seen, {
      id: "dia-prev-opaco",
      texto: `Ayer ~${Math.round(diaPrev.pOp * 100)}% horas opacas — el día siguiente no hereda oscuridad (r≈0 en cinta). Mirá hod/franja, no el calendario.`,
    });
  }

  return tips;
}

/** Tips flaca activos (opacidad + intra). */
export function tipsFlacaActivos(tipsOpacidad = [], tipsIntraHora = []) {
  const ids = new Set([
    "flaca-cierre-perfil",
    "flaca-olor-20",
    "post-flaca-rebote",
  ]);
  return [...tipsOpacidad, ...tipsIntraHora].filter((t) => ids.has(t.id));
}

/** Tag compacto live — olor opaca. */
export function flacaTagLive(tipsOpacidad = [], tipsIntraHora = []) {
  const flaca = tipsFlacaActivos(tipsOpacidad, tipsIntraHora);
  if (!flaca.length) return null;
  if (flaca.some((t) => t.id === "flaca-cierre-perfil")) return "Opaca · olor cierre";
  if (flaca.some((t) => t.tono === "olor")) return "Opaca · olor";
  return null;
}

/** Línea corta para tooltip Brillo. */
export function flacaTooltipExtra(tipsOpacidad = [], tipsIntraHora = []) {
  const flaca = tipsFlacaActivos(tipsOpacidad, tipsIntraHora);
  const t = flaca.find((x) => x.alerta) || flaca[0];
  if (!t) return null;
  const txt = t.texto.length > 72 ? `${t.texto.slice(0, 69)}…` : t.texto;
  return `Flaca: ${txt}`;
}
