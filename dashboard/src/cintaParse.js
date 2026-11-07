/**
 * Parseo de cinta extracción — una pasada O(n) + caché por fingerprint.
 */
import { parseTag, parseTiro } from "./live.js";
import { meanGDeTiros } from "./ecoInfo.js";
import {
  GEN_SUM_UMBRAL,
  GEN_SUM_OPACO,
} from "./generosidadInfo.js";

let _cacheFp = "";
let _cacheHoras = null;

function dayKeyFromTag(tag) {
  const t = parseTag(tag);
  return t ? `${t.dia}-${t.mes}-${t.anio}` : null;
}

/** Fingerprint barato para evitar re-parsear la misma cinta. */
export function fingerprintLineas(lineas = []) {
  const n = lineas.length;
  if (!n) return "0";
  let h = n;
  const step = Math.max(1, Math.floor(n / 24));
  for (let i = 0; i < n; i += step) {
    const s = lineas[i] || "";
    h = (Math.imul(31, h) + s.length + s.charCodeAt(0)) | 0;
  }
  return `${n}:${h}:${lineas[n - 1]}:${lineas[0]}`;
}

/** Horas cerradas en cinta con suma G — una sola pasada. */
export function horasDeLineas(lineas = []) {
  const out = [];
  let i = 0;
  while (i < lineas.length) {
    const s = (lineas[i] || "").trim();
    if (!/^h\d{1,2}-\d{6}$/i.test(s)) {
      i += 1;
      continue;
    }
    const tag = s.toLowerCase();
    const meta = parseTag(tag);
    i += 1;
    const tiros = [];
    while (i < lineas.length) {
      const row = (lineas[i] || "").trim();
      if (!row) {
        i += 1;
        continue;
      }
      if (/^h\d{1,2}-\d{6}$/i.test(row)) break;
      const tiro = parseTiro(row);
      if (tiro) tiros.push(tiro);
      i += 1;
    }
    if (!meta) continue;
    const { acumG, nG, meanG } = meanGDeTiros(tiros);
    if (nG < 1) continue;
    let maxG = 0;
    let cola500 = false;
    let cola400 = false;
    for (const t of tiros) {
      if (t.color !== "G" || t.lumen == null) continue;
      const lm = Number(t.lumen);
      if (lm > maxG) maxG = lm;
      if (lm > 500) cola500 = true;
      if (lm > 400) cola400 = true;
    }
    out.push({
      tag,
      hod: meta.hora,
      dayKey: dayKeyFromTag(tag),
      sumG: Math.round(acumG),
      nG,
      meanG,
      maxG,
      cola500,
      cola400,
      generosa: acumG >= GEN_SUM_UMBRAL,
      opaca: acumG < GEN_SUM_OPACO,
    });
  }
  return out;
}

export function horasDeLineasCached(lineas = []) {
  const fp = fingerprintLineas(lineas);
  if (fp === _cacheFp && _cacheHoras) return _cacheHoras;
  _cacheFp = fp;
  _cacheHoras = horasDeLineas(lineas);
  return _cacheHoras;
}

export function lineasSinCambio(prevFp, lineas = []) {
  return prevFp === fingerprintLineas(lineas);
}

/** Últimas N horas de cinta — tips/contexto sin parsear 120 h enteras. */
export function tailLineasHoras(lineas = [], maxHoras = 32) {
  if (maxHoras <= 0 || !lineas?.length) return lineas || [];
  const headers = [];
  for (let i = 0; i < lineas.length; i += 1) {
    const s = (lineas[i] || "").trim();
    if (/^h\d{1,2}-\d{6}$/i.test(s)) headers.push(i);
  }
  if (headers.length <= maxHoras) return lineas;
  return lineas.slice(headers[headers.length - maxHoras]);
}
