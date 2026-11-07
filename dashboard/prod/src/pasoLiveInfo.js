/**

 * INFO paso en vivo — costura h14→h15 · abreviaturas pool extracción.

 * No boleto · no filtra chips.

 */

import { parseTag } from "./live.js";

import { refuerzoAperturaCostura1415 } from "./intraHoraInfo.js";



function tagHod(tag, hod) {

  const t = parseTag(tag);

  if (!t) return null;

  const dd = String(t.dia).padStart(2, "0");

  const mm = String(t.mes).padStart(2, "0");

  const yy = String(t.anio).slice(-2);

  return `h${hod}-${dd}${mm}${yy}`;

}



/** OLOR costura h14 sin G 0–9 → h15 rebote (lab intra-hora). */

export function costuraH15Info(tag, lineas = []) {

  const t = parseTag(tag);

  if (!t || t.hora !== 15) return null;

  const h14 = tagHod(tag, 14);

  if (!h14) return null;

  const info = refuerzoAperturaCostura1415({

    lineas,

    tagOrigen: h14,

    enCurso: false,

  });

  if (!info) return null;

  return {

    pill: "alerta rebote",

    linea: info.linea,

    detalle: info.detalle,

  };

}



/** Abreviatura pool para extracción inline (solo número). */

export function poolHitShort(nombre, id) {

  const m = (nombre || "").match(/Pool\s*(\d+)/i);

  if (m) return m[1];

  if (id === "live-rc") return "10";

  if (id === "lc-01") return "7";

  if (id === "inter2") return "8";

  if (id === "oficial") return "0";

  return (id || "?").slice(0, 4);

}

