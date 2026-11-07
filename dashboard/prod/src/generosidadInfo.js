/**
 * Generosidad — olas de día (lab cinta 868h) + lectura live con fecha.
 * INFO · no boleto. Día generoso = ≥25% horas con sum≥850.
 */
import { parseTag } from "./live.js";
import { pad } from "./mesa.js";
import { horasDeLineasCached } from "./cintaParse.js";

export { horasDeLineas, horasDeLineasCached } from "./cintaParse.js";

export const GEN_SUM_UMBRAL = 850;
export const GEN_DIA_PCT = 0.25;
export const GEN_MEDIAN_GAP_D = 3;
export const GEN_HOD_OLOR = [14, 15, 19];
export const GEN_SUM_OPACO = 450;

/** Train cinta · P_gen/día histórico por DOW (getDay 0=dom). */
export const GEN_DOW_PGEN = {
  0: 17,
  1: 16,
  2: 19,
  3: 22,
  4: 22,
  5: 16,
  6: 19,
};

/** P(día generoso) histórico por DOW — muestra chica, olor. */
export const GEN_DOW_PDIA = {
  0: 40,
  1: 20,
  2: 20,
  3: 60,
  4: 50,
  5: 0,
  6: 20,
};

/** P(hora generosa) por hod — anclas mediodía-tarde. */
export const GEN_HOD_PGEN = {
  14: 22,
  15: 30,
  19: 22,
};

const DOW_ES = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const MIN_HORAS_DIA_HIST = 12;

function dateFromParts(dia, mes, anio) {
  return new Date(anio, mes - 1, dia);
}

function dateFromTag(tag) {
  const t = parseTag(tag);
  if (!t) return null;
  return dateFromParts(t.dia, t.mes, t.anio);
}

function diaMasDate(date, delta) {
  const d = new Date(date.getTime());
  d.setDate(d.getDate() + delta);
  return d;
}

function fmtFechaCorta(d) {
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
}

function fmtFechaLarga(d) {
  return `${DOW_ES[d.getDay()]} ${fmtFechaCorta(d)}`;
}

function dayKeyFromTag(tag) {
  const t = parseTag(tag);
  return t ? `${t.dia}-${t.mes}-${t.anio}` : null;
}

function agruparPorDia(horas, tagLive = "", acumLive = null) {
  const byDay = new Map();
  for (const h of horas) {
    if (!byDay.has(h.dayKey)) {
      byDay.set(h.dayKey, []);
    }
    byDay.get(h.dayKey).push(h);
  }

  if (tagLive && acumLive != null) {
    const dk = dayKeyFromTag(tagLive);
    const meta = parseTag(tagLive);
    if (dk && meta) {
      const list = byDay.get(dk) || [];
      const idx = list.findIndex((x) => x.tag === tagLive.toLowerCase());
      const row = {
        tag: tagLive.toLowerCase(),
        hod: meta.hora,
        dayKey: dk,
        sumG: Math.round(acumLive),
        generosa: acumLive >= GEN_SUM_UMBRAL,
        opaca: acumLive < GEN_SUM_OPACO,
        enCurso: true,
      };
      if (idx >= 0) list[idx] = row;
      else list.push(row);
      byDay.set(dk, list);
    }
  }

  const dias = [];
  for (const [dayKey, hs] of byDay.entries()) {
    hs.sort((a, b) => a.hod - b.hod);
    const n = hs.length;
    const nGen = hs.filter((x) => x.generosa).length;
    const nOp = hs.filter((x) => x.opaca).length;
    const sums = hs.map((x) => x.sumG).sort((a, b) => a - b);
    const medH =
      sums.length > 0
        ? sums.length % 2
          ? sums[(sums.length - 1) / 2]
          : (sums[sums.length / 2 - 1] + sums[sums.length / 2]) / 2
        : 0;
    const t = parseTag(hs[0].tag);
    const dt = dateFromParts(t.dia, t.mes, t.anio);
    dias.push({
      dayKey,
      dt,
      fecha: fmtFechaCorta(dt),
      dow: DOW_ES[dt.getDay()],
      n,
      nGen,
      nOp,
      pGen: nGen / n,
      pOp: nOp / n,
      tot: hs.reduce((a, x) => a + x.sumG, 0),
      medH,
      genDia: n >= MIN_HORAS_DIA_HIST && nGen / n >= GEN_DIA_PCT,
      falsoGen:
        n >= MIN_HORAS_DIA_HIST &&
        nGen / n >= GEN_DIA_PCT &&
        nOp / n >= 0.35 &&
        medH < 600,
      horas: hs,
    });
  }
  dias.sort((a, b) => a.dt - b.dt);
  return dias;
}

function perfilDow(dow) {
  const p = GEN_DOW_PGEN[dow] ?? 17;
  if (p >= 21) return "alto";
  if (p <= 16) return "bajo";
  return "medio";
}

function etiquetaHoy(hoyRow) {
  if (!hoyRow) return null;
  if (hoyRow.n < 8) {
    return { id: "temprano", label: "Muy temprano", hint: "Menos de 8 h en el día." };
  }
  if (hoyRow.falsoGen) {
    return {
      id: "falso",
      label: "Día partido",
      hint: "≥25% fuertes pero mediana <600 y muchas opacas — picos, no día limpio.",
    };
  }
  if (hoyRow.genDia) {
    return { id: "generoso", label: "Generoso", hint: "≥25% horas fuertes, pocas opacas." };
  }
  if (hoyRow.pOp >= 0.35) {
    return { id: "opaco", label: "Día opaco", hint: "Muchas horas opacas; no perfil generoso." };
  }
  return { id: "normal", label: "En curso", hint: "Día sin perfil generoso claro aún." };
}

function confianzaOla({
  diasDesdeUltimo,
  diasHastaOlor,
  hoyDate,
  olorDesde,
  olorHasta,
  ultimoGen,
}) {
  if (!ultimoGen || !hoyDate) {
    return { nivel: "baja", label: "Sin ola reciente", nota: "Mediana entre días generosos: 3 d." };
  }
  const enRango =
    olorDesde &&
    olorHasta &&
    hoyDate.getTime() >= olorDesde.getTime() &&
    hoyDate.getTime() <= olorHasta.getTime();
  if (diasHastaOlor === 0) {
    return { nivel: "alta", label: "Hoy centro olor", nota: "Ventana ±1d desde última ola." };
  }
  if (diasHastaOlor === 1) {
    return { nivel: "alta", label: "Mañana centro olor", nota: "Ventana ±1d." };
  }
  if (enRango) {
    return { nivel: "media", label: "Dentro ventana ±1d", nota: "Olor día generoso, no regla." };
  }
  if (diasDesdeUltimo != null && diasDesdeUltimo >= 2 && diasDesdeUltimo <= 4) {
    return {
      nivel: "media",
      label: "Cerca mediana 3d",
      nota: `Hace ${diasDesdeUltimo} d desde ${ultimoGen.dow} ${ultimoGen.fecha}.`,
    };
  }
  return {
    nivel: "baja",
    label: "Olor lejano",
    nota: "Día+1 no hereda generosidad (r≈0).",
  };
}

function confianzaDowLabel(pDiaGenHist, pGenHist) {
  if (pDiaGenHist === 0) return "DOW hist bajo";
  if (pDiaGenHist >= 40) return "DOW hist alto";
  if (pGenHist <= 16) return "DOW apagado";
  return null;
}

/**
 * Lectura calendario generosidad para modal Proyección.
 */
export function buildGenerosidadLectura({
  tag = "",
  lineas = [],
  hod = 0,
  acumHora = null,
} = {}) {
  const hoyMeta = parseTag(tag);
  const hoyDate = hoyMeta ? dateFromParts(hoyMeta.dia, hoyMeta.mes, hoyMeta.anio) : null;

  const horas = horasDeLineasCached(lineas);
  const dias = agruparPorDia(horas, tag, acumHora);

  const diasCompletos = dias.filter((d) => d.n >= MIN_HORAS_DIA_HIST);
  const genHist = diasCompletos.filter((d) => d.genDia);

  let ultimoGen = null;
  for (let i = genHist.length - 1; i >= 0; i -= 1) {
    const d = genHist[i];
    if (hoyDate && d.dt.getTime() === hoyDate.getTime()) continue;
    ultimoGen = d;
    break;
  }
  if (!ultimoGen && genHist.length) {
    const last = genHist[genHist.length - 1];
    if (!hoyDate || last.dt.getTime() !== hoyDate.getTime()) ultimoGen = last;
  }

  const hoyRow =
    hoyDate != null
      ? dias.find((d) => d.dt.getTime() === hoyDate.getTime())
      : null;

  let diasDesdeUltimo = null;
  let olorCentro = null;
  let olorDesde = null;
  let olorHasta = null;

  if (ultimoGen && hoyDate) {
    diasDesdeUltimo = Math.round(
      (hoyDate.getTime() - ultimoGen.dt.getTime()) / 86400000
    );
    olorCentro = diaMasDate(ultimoGen.dt, GEN_MEDIAN_GAP_D);
    olorDesde = diaMasDate(ultimoGen.dt, GEN_MEDIAN_GAP_D - 1);
    olorHasta = diaMasDate(ultimoGen.dt, GEN_MEDIAN_GAP_D + 1);
  } else if (hoyDate && !ultimoGen) {
    olorCentro = diaMasDate(hoyDate, GEN_MEDIAN_GAP_D);
    olorDesde = diaMasDate(hoyDate, GEN_MEDIAN_GAP_D - 1);
    olorHasta = diaMasDate(hoyDate, GEN_MEDIAN_GAP_D + 1);
  }

  const diasHastaOlor =
    olorCentro && hoyDate
      ? Math.round((olorCentro.getTime() - hoyDate.getTime()) / 86400000)
      : null;

  const ventana = [];
  if (hoyDate) {
    for (let k = 0; k <= 4; k += 1) {
      const d = diaMasDate(hoyDate, k);
      const dow = d.getDay();
      const esOlor =
        olorCentro && d.getTime() === olorCentro.getTime();
      const enRango =
        olorDesde &&
        olorHasta &&
        d.getTime() >= olorDesde.getTime() &&
        d.getTime() <= olorHasta.getTime();
      ventana.push({
        offset: k,
        fecha: fmtFechaCorta(d),
        dow: DOW_ES[dow],
        label: fmtFechaLarga(d),
        pGenHist: GEN_DOW_PGEN[dow] ?? 17,
        pDiaGenHist: GEN_DOW_PDIA[dow] ?? 20,
        perfil: perfilDow(dow),
        confianzaDow: confianzaDowLabel(GEN_DOW_PDIA[dow] ?? 20, GEN_DOW_PGEN[dow] ?? 17),
        esHoy: k === 0,
        esOlorCentro: esOlor,
        enRangoOla: enRango,
      });
    }
  }

  const hodEnOlor = GEN_HOD_OLOR.includes(hod);
  const hodPG = GEN_HOD_PGEN[hod];

  const confianza = confianzaOla({
    diasDesdeUltimo,
    diasHastaOlor,
    hoyDate,
    olorDesde,
    olorHasta,
    ultimoGen: ultimoGen
      ? {
          dow: ultimoGen.dow,
          fecha: fmtFechaCorta(ultimoGen.dt),
        }
      : null,
  });

  const hoyEtiqueta = hoyRow ? etiquetaHoy(hoyRow) : null;
  const franja =
    hod >= 12 && hod <= 17
      ? "mediodía"
      : hod >= 18
        ? "noche"
        : hod >= 6
          ? "mañana"
          : "madrugada";

  const proxHodOlor = GEN_HOD_OLOR.filter((h) => h > hod);
  if (!proxHodOlor.length && hod < 14) proxHodOlor.push(...GEN_HOD_OLOR);

  const secciones = [];

  if (hoyRow) {
    const pct = Math.round(hoyRow.pGen * 100);
    const opPct = Math.round(hoyRow.pOp * 100);
    if (hoyRow.genDia && !hoyRow.falsoGen) {
      secciones.push({
        id: "hoy-gen",
        titulo: "Hoy",
        texto: `${fmtFechaLarga(hoyDate)} — día generoso en curso (${pct}% horas fuertes, ${hoyRow.n} h).`,
        tipo: "vive",
      });
    } else if (hoyRow.falsoGen) {
      secciones.push({
        id: "hoy-falso",
        titulo: "Hoy",
        texto: `${fmtFechaLarga(hoyDate)} — día partido: ${pct}% fuertes pero ${opPct}% opacas · mediana ${Math.round(hoyRow.medH)} (<600). Picos fuertes con suelo opaco; no tratarlo como día generoso limpio.`,
        tipo: "olor",
      });
    } else if (hoyRow.n < 8) {
      secciones.push({
        id: "hoy-temprano",
        titulo: "Hoy",
        texto: `${fmtFechaLarga(hoyDate)} — muy temprano (${hoyRow.n} h). Perfil DOW: ${perfilDow(hoyDate.getDay())} (hist ~${GEN_DOW_PGEN[hoyDate.getDay()]}% fuertes).`,
        tipo: "info",
      });
    } else {
      secciones.push({
        id: "hoy-normal",
        titulo: "Hoy",
        texto: `${fmtFechaLarga(hoyDate)} — ${pct}% horas fuertes (${hoyRow.nGen}/${hoyRow.n}). ${opPct >= 35 ? "Muchas opacas — no perfil generoso limpio." : "Día en curso."}`,
        tipo: "info",
      });
    }
  }

  if (ultimoGen) {
    secciones.push({
      id: "ultimo-gen",
      titulo: "Última ola",
      texto: `Último día generoso: ${fmtFechaLarga(ultimoGen.dt)} (${Math.round(ultimoGen.pGen * 100)}%, ${ultimoGen.nGen} h fuertes).${diasDesdeUltimo != null ? ` Hace ${diasDesdeUltimo} día${diasDesdeUltimo === 1 ? "" : "s"}.` : ""}`,
      tipo: "info",
    });
  }

  if (olorCentro && hoyDate) {
    const enVentana =
      hoyDate.getTime() >= olorDesde.getTime() &&
      hoyDate.getTime() <= olorHasta.getTime();
    let txt = `Olor día generoso: ${fmtFechaLarga(olorCentro)} (mediana ${GEN_MEDIAN_GAP_D} d desde la última ola). Rango: ${fmtFechaCorta(olorDesde)} – ${fmtFechaCorta(olorHasta)}.`;
    if (diasHastaOlor === 0) txt = `Hoy cae en la ventana de ola generosa (centro ${fmtFechaCorta(olorCentro)}).`;
    else if (diasHastaOlor > 0)
      txt += ` Faltan ~${diasHastaOlor} d para el centro.`;
    else if (enVentana) txt += " Estamos dentro del rango ±1.";
    secciones.push({
      id: "olor-ola",
      titulo: "Próxima ola",
      texto: txt,
      tipo: diasHastaOlor != null && diasHastaOlor <= 1 ? "olor" : "info",
    });
  }

  if (hodEnOlor || hodPG) {
    secciones.push({
      id: "hod-olor",
      titulo: `Esta hora (h${String(hod).padStart(2, "0")})`,
      texto: hodEnOlor
        ? `Ancla mediodía-tarde: h${String(hod).padStart(2, "0")} hist ~${hodPG ?? 22}% horas fuertes (67% en cluster ago).`
        : `Franja ${franja}. Próximos olores hod: ${proxHodOlor.map((h) => `h${String(h).padStart(2, "0")}`).join(", ")}.`,
      tipo: hodEnOlor ? "olor" : "info",
    });
  }

  secciones.push({
    id: "nota-g",
    titulo: "Nota",
    texto:
      "Casi todo día trae ≥1 h fuerte; la ola mira el día entero (≥25% horas ≥850 lumen). INFO · no boleto.",
    tipo: "muted",
  });

  return {
    ok: true,
    confianza,
    hoy: hoyRow
      ? {
          fecha: hoyRow.fecha,
          dow: hoyRow.dow,
          label: hoyDate ? fmtFechaLarga(hoyDate) : hoyRow.fecha,
          pGen: Math.round(hoyRow.pGen * 100),
          pOp: Math.round(hoyRow.pOp * 100),
          nHoras: hoyRow.n,
          nGen: hoyRow.nGen,
          medH: Math.round(hoyRow.medH),
          genDia: hoyRow.genDia,
          falsoGen: hoyRow.falsoGen,
          perfil: hoyDate ? perfilDow(hoyDate.getDay()) : "medio",
          etiqueta: hoyEtiqueta,
        }
      : null,
    ola: ultimoGen
      ? {
          ultimo: {
            label: fmtFechaLarga(ultimoGen.dt),
            fecha: fmtFechaCorta(ultimoGen.dt),
            dow: ultimoGen.dow,
            pGen: Math.round(ultimoGen.pGen * 100),
            haceDias: diasDesdeUltimo,
          },
          olorCentro: olorCentro
            ? {
                label: fmtFechaLarga(olorCentro),
                fecha: fmtFechaCorta(olorCentro),
                dow: DOW_ES[olorCentro.getDay()],
              }
            : null,
          olorRango:
            olorDesde && olorHasta
              ? {
                  desde: fmtFechaCorta(olorDesde),
                  hasta: fmtFechaCorta(olorHasta),
                }
              : null,
          diasDesdeUltimo,
          diasHastaOlor,
          confianza,
        }
      : { confianza },
    hod: {
      actual: hod,
      olorHora: hodEnOlor,
      franja,
      pGenHist: hodPG ?? null,
      proximos: proxHodOlor.map((h) => ({
        hod: h,
        label: `h${String(h).padStart(2, "0")}`,
        pGen: GEN_HOD_PGEN[h] ?? null,
      })),
    },
    ventana,
    secciones,
  };
}
