/**
 * Ola post-SN — cola G>500 en 40–59 tras supernova ya confirmada en la hora.
 * INFO · no boleto · icono aparte (barra pools, junto a Next).
 */
import { buildBrilloLectura } from "./brilloInfo.js";
import {
  minutoConfirmacionSn,
  ultimaOlaPostSn,
} from "./supernovaInfo.js";

export const OLA_COLA_MIN = 500;
export const OLA_SHOW_MIN = 40;
export const OLA_ALERT_MAX = 57;

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function statsHora(tiros = [], T = 0) {
  let acum = 0;
  let nG = 0;
  let sumG = 0;
  let maxG = 0;
  for (const t of tiros || []) {
    if (!t || t.m0 > T) continue;
    const lm = lumenOf(t);
    if (lm == null) continue;
    acum += lm;
    if (String(t.color || "").toUpperCase().startsWith("G")) {
      nG += 1;
      sumG += lm;
      if (lm > maxG) maxG = lm;
    }
  }
  return {
    acum,
    nG,
    meanG: nG > 0 ? sumG / nG : null,
    maxG,
  };
}

function maxGEnRango(tiros = [], lo, hi, T) {
  let max = 0;
  for (const t of tiros || []) {
    if (!t || t.m0 < lo || t.m0 > hi || t.m0 > T) continue;
    if (!String(t.color || "").toUpperCase().startsWith("G")) continue;
    const lm = lumenOf(t);
    if (lm != null && lm > max) max = lm;
  }
  return max;
}

function evalOlorPostSn({ tiros, T, minSn, st, brillo }) {
  const margenProy =
    brillo?.predHi != null ? brillo.predHi - st.acum : null;
  const pico2039 = maxGEnRango(tiros, 20, 39, Math.min(T, 39));
  return (
    st.maxG >= OLA_COLA_MIN ||
    pico2039 >= 400 ||
    (st.meanG != null && st.meanG >= 55 && st.nG >= 4) ||
    (margenProy != null && margenProy >= 200)
  );
}

/**
 * @returns {null | { ok, parpadea, fase, titulo, lineas, minSn, ola, T, fingerprint }}
 */
export function buildOlaPostSnLectura({
  tiros = [],
  minuto = 0,
  tag = "",
  horaCerrada = false,
  brillo = null,
} = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const minSn = minutoConfirmacionSn(tiros, T);
  if (minSn == null || T < OLA_SHOW_MIN) return null;

  const ola = ultimaOlaPostSn(tiros, T, minSn);
  const st = statsHora(tiros, T);
  const brilloLectura =
    brillo || buildBrilloLectura({ tiros, minuto: T, tag, cintaLineas: [] });
  const olorActivo =
    !ola && !horaCerrada && T <= OLA_ALERT_MAX && evalOlorPostSn({ tiros, T, minSn, st, brillo: brilloLectura });

  if (!ola && !olorActivo) return null;

  const parpadea = Boolean(olorActivo && !horaCerrada);
  const fase = ola ? "confirmada" : "alerta";
  const lineas = [];

  if (ola) {
    lineas.push(
      `Ola post-SN: G de ${ola.lumen} lm al min ${ola.m0} (después del min ${minSn}).`
    );
    lineas.push("No es otra supernova — cola sobre la SN ya confirmada.");
  } else {
    lineas.push(
      `SN confirmada al min ${minSn} · bloque 40–59 abierto — olor de otra G>${OLA_COLA_MIN} lm.`
    );
    lineas.push(
      `Van ${Math.round(st.acum)} lm · max G ${st.maxG} · proyección ${brilloLectura.predLo ?? "—"}–${brilloLectura.predHi ?? "—"}.`
    );
    lineas.push("Alerta de cola — no implica que caiga; mirá cada tiro G.");
  }

  const titulo = ola ? "Ola post-SN" : "Olor cola post-SN";

  return {
    ok: true,
    tag,
    T,
    minSn,
    ola,
    parpadea,
    fase,
    titulo,
    lineas,
    fingerprint: [
      tag,
      fase,
      minSn,
      ola?.m0 ?? "-",
      ola?.lumen ?? "-",
      parpadea ? 1 : 0,
      Math.round(st.acum / 100) * 100,
    ].join("|"),
  };
}

export function olaPostSnTooltip(lectura) {
  if (!lectura?.ok) return "";
  const head = lectura.ola
    ? `Ola post-SN · G ${lectura.ola.lumen} lm @${lectura.ola.m0}`
    : `Olor cola post-SN · SN min ${lectura.minSn}`;
  return [head, ...(lectura.lineas || [])].join("\n");
}
