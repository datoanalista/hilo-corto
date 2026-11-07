/**
 * Brillo INFO — escalas + lectura humana (lab-prohibido).
 * Eje lumen (luz), no cupo nG. Actualiza con live.
 */
import { parseTag } from "./live.js";
import {
  buildOpacidadTips,
  flacaTooltipExtra,
} from "./opacidadInfo.js";
import { buildCosturaLectura, buildCosturasLectura } from "./costuraInfo.js";
import { buildIntraHoraTips } from "./intraHoraInfo.js";
import { buildColaGTips, colaGTooltipExtra } from "./colaGInfo.js";

/** Luz total de la hora (suma al cerrar). */
export const ESCALA_TOTAL = [
  { id: "muy_apagado", label: "muy apagado", min: 0, max: 449 },
  { id: "opaco", label: "opaco", min: 450, max: 599 },
  { id: "normal", label: "normal", min: 600, max: 849 },
  { id: "fuerte", label: "fuerte", min: 850, max: 1099 },
  { id: "muy_fuerte", label: "muy fuerte", min: 1100, max: 1599 },
  { id: "supernova", label: "supernova", min: 1600, max: 99999 },
];

/** Luz por cada G (promedio). */
export const ESCALA_MEAN = [
  { id: "muy_apagado", label: "muy apagado", min: 0, max: 41.99 },
  { id: "opaco", label: "opaco", min: 42, max: 49.99 },
  { id: "normal", label: "normal", min: 50, max: 67.99 },
  { id: "fuerte", label: "fuerte", min: 68, max: 84.99 },
  { id: "muy_fuerte", label: "muy fuerte", min: 85, max: 109.99 },
  { id: "supernova", label: "supernova", min: 110, max: 99999 },
];

export const MEAN_Q25 = 48.0;
export const MEAN_Q75 = 74.0; // p75 train · alineado catálogo / PROMETE

/** Tabla hod train · cinta larga 35d (depurar-all-4G-detail, sin 1h rota). */
export const HOD_TABLA = {
  0: { P_O: 0.2, P_B: 0.2, P_N: 0.6, moda: "N", med_rem20: 390, p25_rem20: 250, p75_rem20: 508 },
  1: { P_O: 0.36, P_B: 0.2, P_N: 0.44, moda: "N", med_rem20: 318, p25_rem20: 241, p75_rem20: 385 },
  2: { P_O: 0.2, P_B: 0.36, P_N: 0.44, moda: "N", med_rem20: 369, p25_rem20: 285, p75_rem20: 491 },
  3: { P_O: 0.12, P_B: 0.24, P_N: 0.64, moda: "N", med_rem20: 480, p25_rem20: 338, p75_rem20: 591 },
  4: { P_O: 0.16, P_B: 0.24, P_N: 0.6, moda: "N", med_rem20: 415, p25_rem20: 350, p75_rem20: 508 },
  5: { P_O: 0.16, P_B: 0.16, P_N: 0.68, moda: "N", med_rem20: 333, p25_rem20: 289, p75_rem20: 444 },
  6: { P_O: 0.16, P_B: 0.36, P_N: 0.48, moda: "N", med_rem20: 414, p25_rem20: 270, p75_rem20: 560 },
  7: { P_O: 0.28, P_B: 0.28, P_N: 0.44, moda: "N", med_rem20: 428, p25_rem20: 266, p75_rem20: 626 },
  8: { P_O: 0.08, P_B: 0.36, P_N: 0.56, moda: "N", med_rem20: 416, p25_rem20: 298, p75_rem20: 578 },
  9: { P_O: 0.231, P_B: 0.231, P_N: 0.538, moda: "N", med_rem20: 408, p25_rem20: 239, p75_rem20: 554 },
  10: { P_O: 0.269, P_B: 0.269, P_N: 0.462, moda: "N", med_rem20: 395, p25_rem20: 272, p75_rem20: 513 },
  11: { P_O: 0.346, P_B: 0.192, P_N: 0.462, moda: "N", med_rem20: 325, p25_rem20: 213, p75_rem20: 480 },
  12: { P_O: 0.231, P_B: 0.231, P_N: 0.538, moda: "N", med_rem20: 392, p25_rem20: 275, p75_rem20: 497 },
  13: { P_O: 0.192, P_B: 0.231, P_N: 0.577, moda: "N", med_rem20: 336, p25_rem20: 210, p75_rem20: 551 },
  14: { P_O: 0.423, P_B: 0.231, P_N: 0.346, moda: "O", med_rem20: 326, p25_rem20: 228, p75_rem20: 487 },
  15: { P_O: 0.192, P_B: 0.385, P_N: 0.423, moda: "N", med_rem20: 446, p25_rem20: 347, p75_rem20: 547 },
  16: { P_O: 0.192, P_B: 0.154, P_N: 0.654, moda: "N", med_rem20: 374, p25_rem20: 284, p75_rem20: 446 },
  17: { P_O: 0.423, P_B: 0.269, P_N: 0.308, moda: "O", med_rem20: 361, p25_rem20: 212, p75_rem20: 566 },
  18: { P_O: 0.346, P_B: 0.231, P_N: 0.423, moda: "N", med_rem20: 351, p25_rem20: 233, p75_rem20: 501 },
  19: { P_O: 0.269, P_B: 0.269, P_N: 0.462, moda: "N", med_rem20: 368, p25_rem20: 249, p75_rem20: 557 },
  20: { P_O: 0.308, P_B: 0.346, P_N: 0.346, moda: "N", med_rem20: 388, p25_rem20: 298, p75_rem20: 601 },
  21: { P_O: 0.308, P_B: 0.154, P_N: 0.538, moda: "N", med_rem20: 403, p25_rem20: 269, p75_rem20: 508 },
  22: { P_O: 0.346, P_B: 0.308, P_N: 0.346, moda: "O", med_rem20: 378, p25_rem20: 263, p75_rem20: 662 },
  23: { P_O: 0.231, P_B: 0.154, P_N: 0.615, moda: "N", med_rem20: 331, p25_rem20: 282, p75_rem20: 446 },
};

function bandOf(value, escala) {
  for (const b of escala) {
    if (value >= b.min && value <= b.max) return b;
  }
  return escala[escala.length - 1];
}

function round50(n) {
  return Math.round(n / 50) * 50;
}

function pctHuman(p) {
  if (p >= 0.65) return "en 7 de cada 10 veces";
  if (p >= 0.55) return "en más de la mitad de las veces";
  if (p >= 0.4) return "en 4 de cada 10 veces";
  if (p >= 0.3) return "en 3 de cada 10 veces";
  return "a veces";
}

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  // live corto: el número tras G/R suele ser lumen
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

/**
 * @param {object} opts
 * @param {Array} opts.tiros — tiros parseados (color, lumen/vecino, m0)
 * @param {number} opts.minuto — minuto actual de la hora
 * @param {string} opts.tag — hN-DDMMYY
 */
export function buildBrilloLectura({ tiros = [], minuto = 0, tag = "", cintaLineas = [] } = {}) {
  const meta = parseTag(tag);
  const hod = meta?.hora ?? 0;
  const hodRow = HOD_TABLA[hod] || HOD_TABLA[0];
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));

  const cerrados = (tiros || []).filter((t) => t && t.m0 <= T);
  let acum = 0;
  let sumG = 0;
  let nG = 0;
  let maxG = 0;
  let sinLumen = 0;
  for (const t of cerrados) {
    const lm = lumenOf(t);
    if (lm == null) {
      sinLumen += 1;
      continue;
    }
    acum += lm;
    if (t.color === "G") {
      sumG += lm;
      nG += 1;
      if (lm > maxG) maxG = lm;
    }
  }
  const meanG = nG > 0 ? sumG / nG : null;
  const tieneDatos = acum > 0 || nG > 0;

  // rem20 = luz que suele quedar DESPUÉS del min 20 (train).
  // Escalar por minutos restantes para no doble-contar @40+.
  const remScale =
    T <= 20 ? 1 : Math.max(0, Math.min(1, (60 - T) / 40));
  const remLo = (hodRow.p25_rem20 || 200) * remScale;
  const remHi = (hodRow.p75_rem20 || 600) * remScale;
  // Apertura (poca acum): ancla a banda hod total si hay p25/p75 sum — si no, rem.
  let predLo;
  let predHi;
  if (T < 15 && acum < 50) {
    // sin parcial útil: no inventar cierre fino
    predLo = null;
    predHi = null;
  } else {
    predLo = round50(Math.max(200, acum + remLo));
    predHi = round50(Math.max((predLo || 0) + 50, acum + remHi));
  }
  const bandaTotal =
    predLo != null
      ? bandOf((predLo + predHi) / 2, ESCALA_TOTAL)
      : { label: "—" };
  const bandaMean = meanG != null ? bandOf(meanG, ESCALA_MEAN) : null;

  let fase = "apertura";
  let pill = "histórico";
  let tone = "mute";
  const lineas = [];

  const modaLabel =
    hodRow.moda === "O" ? "opaca" : hodRow.moda === "B" ? "fuerte" : "normal";

  if (T < 15 || nG < 2) {
    fase = T < 15 ? "apertura" : "esperando";
    if (T >= 15 && nG < 2) {
      pill = "esperando";
      tone = "mute";
      lineas.push(
        `Brillo: todavía no se puede leer el brillo por G.`
      );
      lineas.push(
        `Hace falta una segunda G para ver si cada tiro trae luz alta o baja.`
      );
      if (nG === 1 && meanG != null) {
        lineas.push(
          `Por ahora: 1 G con ~${Math.round(meanG)} lumen.`
        );
      }
    } else {
      const po = hodRow.P_O || 0;
      const pb = hodRow.P_B || 0;
      if (po >= 0.35) {
        pill = "sesgo opaco";
        tone = "opaco";
        lineas.push(
          `Brillo: la hora h${String(hod).padStart(2, "0")} suele cerrar con poca luz total.`
        );
        lineas.push(
          `${pctHuman(po).replace(/^./, (c) => c.toUpperCase())} termina opaca o muy apagada (menos de ~650 lumen en toda la hora).`
        );
        lineas.push(
          `Esto no dice cuántas G van a caer — solo cuánta luz acostumbra sumar esta hora.`
        );
      } else if (pb >= 0.35) {
        pill = "sesgo fuerte";
        tone = "brill";
        lineas.push(
          `Brillo: la hora h${String(hod).padStart(2, "0")} suele cerrar luminosa.`
        );
        lineas.push(
          `${pctHuman(pb).replace(/^./, (c) => c.toUpperCase())} supera ~900 lumen (zona fuerte o más).`
        );
        lineas.push(
          `Aún no hay lectura de lo que va en curso — es el histórico de esta hora civil.`
        );
      } else {
        pill = "sesgo normal";
        tone = "mute";
        lineas.push(
          `Brillo: la hora h${String(hod).padStart(2, "0")} no trae sesgo claro en la cinta.`
        );
        lineas.push(
          `Suele cerrar en la banda normal (600–850 lumen).`
        );
      }
      if (!tieneDatos && pb < 0.35 && po < 0.35) {
        lineas.push(`Esperá la lectura cuando caigan al menos 2 G.`);
      }
    }
  } else if (T < 40) {
    fase = "tendencia";
    const predTxt =
      predLo != null
        ? `~${predLo}–${predHi} lumen (${bandaTotal.label})`
        : "aún sin proyección fina";
    if (meanG <= MEAN_Q25) {
      pill = "tendencia opaca";
      tone = "opaco";
      lineas.push(`Brillo: tendencia opaca al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen sumados en lo que va de la hora.`
      );
      lineas.push(
        `Cada G trae ~${Math.round(meanG)} lumen de promedio (${bandaMean?.label || "opaco"}).`
      );
      lineas.push(`Si sigue parecido, la hora podría cerrar ${predTxt}.`);
    } else if (meanG >= MEAN_Q75) {
      pill = "tendencia fuerte";
      tone = "brill";
      lineas.push(`Brillo: tendencia fuerte al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen · cada G ~${Math.round(meanG)} lumen (${bandaMean?.label || "fuerte"}).`
      );
      lineas.push(`Proyección al cierre: ${predTxt}.`);
    } else {
      pill = "normal";
      tone = "mute";
      lineas.push(`Brillo: en banda al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen · cada G ~${Math.round(meanG)} lumen (${bandaMean?.label || "normal"}).`
      );
      lineas.push(`Proyección: ${predTxt} si no cambia el ritmo.`);
    }
  } else {
    fase = "confirmado";
    const predTxt =
      predLo != null
        ? `${predLo}–${predHi} lumen (${bandaTotal.label})`
        : "—";
    if (meanG <= MEAN_Q25) {
      pill = bandaMean?.label || "opaco";
      tone = "opaco";
      lineas.push(`Brillo: hora ${pill} — confirmado al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen · cada G ~${Math.round(meanG)} lumen.`
      );
      lineas.push(`Cierre estimado: ${predTxt}.`);
    } else if (meanG >= MEAN_Q75) {
      const label =
        meanG >= 110 || (predHi != null && predHi >= 1600)
          ? "supernova"
          : meanG >= 85 || (predHi != null && predHi >= 1100)
            ? "muy fuerte"
            : bandaMean?.label || "fuerte";
      pill = label;
      tone = "brill";
      lineas.push(`Brillo: ráfaga luminosa al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen · cada G ~${Math.round(meanG)} lumen.`
      );
      lineas.push(`La hora va hacia ${label} (${predTxt}).`);
    } else {
      pill = bandaMean?.label || bandaTotal.label;
      tone = "mute";
      lineas.push(`Brillo: lectura estable al minuto ${T}.`);
      lineas.push(
        `Van ${Math.round(acum)} lumen · cada G ~${Math.round(meanG)} lumen (${bandaMean?.label}).`
      );
      lineas.push(`Cierre probable: ${predTxt}.`);
    }
  }

  const fingerprint = [
    tag,
    fase,
    pill,
    nG,
    Math.round(acum / 25) * 25,
    meanG == null ? "-" : Math.round(meanG / 5) * 5,
  ].join("|");

  const tipsOpacidad = buildOpacidadTips({
    tag,
    lineas: cintaLineas,
    tone,
    meanG,
    acum,
    T,
    tiros,
    nG,
  });

  const tipsIntraHora = buildIntraHoraTips({ tiros, minuto: T, nG });

  const tipsColaG = buildColaGTips({
    tag,
    tiros,
    minuto: T,
    lineas: cintaLineas,
    acum,
    meanG,
    nG,
    maxG,
  });

  const costuras = buildCosturasLectura({
    tag,
    hod,
    lineas: cintaLineas,
    acum,
    meanG,
    nG,
    T,
  });
  const costura = costuras.find((c) => c.alerta) || costuras[0] || null;

  return {
    ok: true,
    tag,
    hod,
    T,
    fase,
    pill,
    tone,
    lineas,
    acum: Math.round(acum),
    nG,
    maxG: maxG > 0 ? maxG : null,
    meanG: meanG == null ? null : Math.round(meanG * 10) / 10,
    predLo,
    predHi,
    bandaTotal: bandaTotal.label,
    bandaMean: bandaMean?.label || null,
    modaHod: modaLabel,
    sinLumen,
    fingerprint,
    tipsOpacidad,
    tipsIntraHora,
    tipsColaG,
    costura,
    costuras,
    escalas: { total: ESCALA_TOTAL, mean: ESCALA_MEAN },
  };
}

function capLabel(s) {
  if (!s || s === "—") return "—";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Cuerpo del tag junto al reloj (sin prefijo Brillo). */
export function brilloTagBody(lectura) {
  if (!lectura) return null;
  const bandaRaw =
    lectura.predLo != null && lectura.bandaTotal && lectura.bandaTotal !== "—"
      ? lectura.bandaTotal
      : lectura.bandaMean || "—";
  const banda = capLabel(bandaRaw);
  const acum = lectura.acum ?? "—";
  const rango =
    lectura.predLo != null
      ? `${lectura.predLo}-${lectura.predHi}`
      : "—";
  return `${banda} ${acum}/${rango}`;
}

/** @deprecated usar brilloTagBody + icono */
export function brilloTagLive(lectura) {
  const body = brilloTagBody(lectura);
  return body ? `Brillo: ${body}` : null;
}

/** Bandas que encienden / mantienen Pool 7 auto ($50). */
const POOL7_BRILLO_ON = new Set(["fuerte", "muy fuerte", "supernova"]);
/** Bandas que apagan Pool 7 auto (no apostar). */
const POOL7_BRILLO_OFF = new Set([
  "normal",
  "opaco",
  "opaca",
  "muy apagado",
  "muy apagada",
  "esperando",
  "histórico",
  "historico",
]);

export function normalizarBandaBrillo(raw) {
  return String(raw || "")
    .toLowerCase()
    .replace(/_/g, " ")
    .trim();
}

/**
 * Pool 7 auto: se prende cuando la hora pasa a fuerte; se mantiene en
 * muy fuerte / supernova; no apuesta si vuelve a normal / opaca / muy apagada.
 * Solo etiquetas de banda puras (no "sesgo fuerte" ni "tendencia fuerte").
 */
export function pool7BrilloPermite(brillo) {
  if (!brillo) return false;
  for (const raw of [brillo.bandaMean, brillo.bandaTotal, brillo.pill]) {
    const b = normalizarBandaBrillo(raw);
    if (b && POOL7_BRILLO_ON.has(b)) return true;
  }
  return false;
}

export function pool7BrilloBandaLabel(brillo) {
  if (!brillo) return "—";
  for (const raw of [brillo.bandaMean, brillo.bandaTotal, brillo.pill]) {
    const b = normalizarBandaBrillo(raw);
    if (!b || b === "—") continue;
    if (POOL7_BRILLO_ON.has(b) || POOL7_BRILLO_OFF.has(b)) return b;
  }
  return (
    normalizarBandaBrillo(brillo.bandaMean) ||
    normalizarBandaBrillo(brillo.bandaTotal) ||
    normalizarBandaBrillo(brillo.pill) ||
    "—"
  );
}

/** Tooltip del icono Brillo (title nativo, multilínea). */
export function brilloTooltipTitle(lectura, { nuevo = false } = {}) {
  if (!lectura) return "Brillo de la hora";
  const base = nuevo
    ? `Brillo · ${lectura.pill} · hay novedad`
    : `Brillo · ${lectura.pill}`;
  const acum = `Acum: ${lectura.acum ?? "—"}`;
  const esperado =
    lectura.predLo != null
      ? `Esperado: ${lectura.predLo}–${lectura.predHi}`
      : "Esperado: —";
  const costura =
    lectura.costura?.ok && lectura.costura.expectativa?.titulo
      ? `${lectura.costura.alerta ? "AVISO · " : ""}${lectura.costura.expectativa.titulo}`
      : null;
  const cola = colaGTooltipExtra(lectura.tipsColaG);
  const flaca = flacaTooltipExtra(lectura.tipsOpacidad, lectura.tipsIntraHora);
  return [base, acum, esperado, costura, cola, flaca].filter(Boolean).join("\n");
}
