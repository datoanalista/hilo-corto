/**
 * Lámpara · INFO junto a Next.
 * Mismo tip LC-01. Callar si p30 sigue largo y la puerta dejaría jugar.
 * No mueve el minuto. No es ficha. No corta Pool 7.
 */

import { pad } from "./mesa.js";
import { diagnosticarGo } from "./sequiaGo.js";

export const LAMPARA_P30 = 9;

/**
 * @returns {null | {
 *   ok: true,
 *   pill: string,
 *   linea: string,
 *   tono: string,
 *   tooltip: string,
 *   fingerprint: string,
 *   p30: number,
 *   tip: number,
 * }}
 */
export function buildLamparaLectura({ tiros = [], tipProx = null } = {}) {
  const tip = tipProx?.tip;
  const p30 = Number(tipProx?.medGap);
  if (tip == null || !Number.isFinite(p30) || p30 < LAMPARA_P30) return null;
  if (tipProx?.estado === "calculando") return null;

  const go = diagnosticarGo(tiros);
  if (!go?.activo) return null;

  const tipTxt = pad(tip);
  const pill = "se pasa";
  const linea = `p30 ${p30} · tip ${tipTxt} se pasa · no me siento`;
  const tooltip = [
    "[Lámpara · no es tip]",
    `• Next ${tipTxt} no se mueve.`,
    `• p30 de huecos ya vistos = ${p30} (≥${LAMPARA_P30}, sigue largo).`,
    "• La puerta dejaría jugar este tiro.",
    "• Lectura: este tip se pasa · no me siento.",
    "• No es Pool 7 nuevo. No cambia LC-01.",
  ].join("\n");

  return {
    ok: true,
    pill,
    linea,
    tono: "on",
    tooltip,
    fingerprint: `${LAMPARA_P30}|${p30}|${tip}|${go.gap}|${go.tipo || "-"}`,
    p30,
    tip,
  };
}
