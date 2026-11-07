/**
 * Supernova INFO — alerta live sum≥1600 (lab medición @40).
 * Registro por bloques 00–19 / 20–39 / 40–59.
 */
import { buildBrilloLectura, ESCALA_TOTAL } from "./brilloInfo.js";
import { buildGenerosidadLectura } from "./generosidadInfo.js";
import { parseTag } from "./live.js";

export const SN_UMBRAL = 1600;
export const SN_OLOR = 1400;
export const SN_MIN_OLOR = 30;
export const SN_MIN_ALERTA = 40;

export const BLOQUES = [
  { id: 0, label: "00–19", lo: 0, hi: 19 },
  { id: 1, label: "20–39", lo: 20, hi: 39 },
  { id: 2, label: "40–59", lo: 40, hi: 59 },
];

/** Índice 0..5 en escala total según lumen acumulado. */
export function bandIndexForSum(sum) {
  if (sum == null || Number.isNaN(sum)) return -1;
  const v = Number(sum);
  for (let i = 0; i < ESCALA_TOTAL.length; i += 1) {
    const b = ESCALA_TOTAL[i];
    if (v >= b.min && v <= b.max) return i;
  }
  if (v > ESCALA_TOTAL[ESCALA_TOTAL.length - 1].min) {
    return ESCALA_TOTAL.length - 1;
  }
  return 0;
}

/**
 * Indicadores de escala según avance de hora (actual + proyección).
 */
export function buildIndicadoresProyeccion({
  acum = 0,
  predLo = null,
  predHi = null,
  T = 0,
} = {}) {
  const actualIdx = bandIndexForSum(acum);
  const projLoIdx = predLo != null ? bandIndexForSum(predLo) : -1;
  const projHiIdx = predHi != null ? bandIndexForSum(predHi) : -1;
  const projCenter =
    predLo != null && predHi != null ? (predLo + predHi) / 2 : null;
  const projIdx = projCenter != null ? bandIndexForSum(projCenter) : -1;

  const niveles = ESCALA_TOTAL.map((b, i) => {
    let estado = "off";
    if (i === actualIdx && i === projIdx && projIdx >= 0) estado = "actual-proy";
    else if (i === actualIdx && actualIdx >= 0) estado = "actual";
    else if (
      projLoIdx >= 0 &&
      projHiIdx >= 0 &&
      i >= projLoIdx &&
      i <= projHiIdx
    ) {
      estado = i === projIdx ? "proy" : "rango";
    } else if (i === projIdx && projIdx >= 0) estado = "proy";
    return {
      id: b.id,
      label: b.label,
      min: b.min,
      max: b.max,
      estado,
    };
  });

  const fase = T < 15 ? "apertura" : T < 40 ? "tendencia" : "cierre";
  const confianza =
    predHi == null ? "nula" : T < 20 ? "baja" : T < 40 ? "media" : "alta";

  return {
    niveles,
    actualIdx,
    projIdx,
    projLoIdx,
    projHiIdx,
    actualLabel: actualIdx >= 0 ? ESCALA_TOTAL[actualIdx].label : null,
    projLabel: projIdx >= 0 ? ESCALA_TOTAL[projIdx].label : null,
    projRangoLabel:
      projLoIdx >= 0 && projHiIdx >= 0 && projLoIdx !== projHiIdx
        ? `${ESCALA_TOTAL[projLoIdx].label} – ${ESCALA_TOTAL[projHiIdx].label}`
        : null,
    fase,
    confianza,
    bloqueActual: T < 20 ? 0 : T < 40 ? 1 : 2,
  };
}

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function statsAt(tiros, T) {
  const cerrados = (tiros || []).filter((t) => t && t.m0 <= T);
  let acum = 0;
  let sumG = 0;
  let nG = 0;
  let maxG = 0;
  for (const t of cerrados) {
    const lm = lumenOf(t);
    if (lm == null) continue;
    acum += lm;
    if (t.color === "G") {
      sumG += lm;
      nG += 1;
      if (lm > maxG) maxG = lm;
    }
  }
  const meanG = nG > 0 ? sumG / nG : null;
  let n500 = 0;
  for (const t of cerrados) {
    if (t.color === "G") {
      const lm = lumenOf(t);
      if (lm != null && lm > 500) n500 += 1;
    }
  }
  return { acum, sumG, nG, meanG, maxG, n500, T };
}

/** Primer minuto en que el acumulado cruza el umbral SN. */
export function minutoConfirmacionSn(tiros = [], T = 59) {
  const lim = Math.min(59, Math.max(0, Number(T) || 0));
  for (let m = 0; m <= lim; m += 1) {
    if (statsAt(tiros, m).acum >= SN_UMBRAL) return m;
  }
  return null;
}

/** Última G>500 después de la confirmación SN (ola nueva en la misma hora). */
export function ultimaOlaPostSn(tiros = [], T = 59, minConf = null) {
  if (minConf == null) return null;
  const lim = Math.min(59, Math.max(0, Number(T) || 0));
  let best = null;
  for (const t of tiros || []) {
    if (!t || t.color !== "G" || t.m0 <= minConf || t.m0 > lim) continue;
    const lm = lumenOf(t);
    if (lm == null || lm <= 500) continue;
    if (!best || t.m0 > best.m0) best = { m0: t.m0, lumen: lm };
  }
  return best;
}

/** Tips lab-supernova (ACTA 2026-08-28) — INFO, no boleto. */
export function buildTipsLab({ st, alerta, indicadores, brillo, T, parpadeaba = false }) {
  const tips = [];
  const n500 = st.n500 ?? 0;
  const predHi = brillo?.predHi ?? null;
  const projAlto =
    (predHi != null && predHi >= 1100) ||
    (indicadores?.projIdx != null && indicadores.projIdx >= 4) ||
    st.acum >= 850;

  if (T >= 20 && n500 === 0 && projAlto) {
    tips.push({
      id: "sin-cola",
      texto:
        "Sin G>500 en la hora: muy fuerte posible, supernova improbable (13/13 SN traen cola >500).",
    });
  }

  if (T >= 20 && n500 > 0) {
    tips.push({
      id: "con-cola",
      texto:
        "Hay G>500 — condición necesaria para supernova. Falta ver si la suma cierra ≥1600.",
    });
  }

  const alertaSn =
    alerta?.estado === "confirmada" ||
    alerta?.estado === "alerta" ||
    (alerta?.estado === "enfrió" && parpadeaba);

  if (alertaSn) {
    tips.push({
      id: "cooldown",
      texto:
        "Tras supernova o alerta SN: la hora siguiente suele enfriar más que una hora brillante normal.",
    });
  }

  return tips;
}

/** Snapshot de un bloque al cerrarlo (minuto = hi del bloque). */
export function snapshotBloque({ tiros = [], tag = "", blockId = 0 } = {}) {
  const bloque = BLOQUES[blockId];
  if (!bloque) return null;
  const T = bloque.hi;
  const st = statsAt(tiros, T);
  const brillo = buildBrilloLectura({ tiros, minuto: T, tag });
  const predHi = brillo.predHi;
  const predLo = brillo.predLo;

  let olor = "—";
  if (st.acum >= SN_UMBRAL) olor = "confirmada";
  else if (predHi != null && predHi >= SN_UMBRAL) olor = "alerta";
  else if (predHi != null && predHi >= SN_OLOR) olor = "olor";
  else if (T >= SN_MIN_ALERTA && predHi != null) olor = "baja";

  return {
    id: blockId,
    label: bloque.label,
    minuto: T,
    acum: Math.round(st.acum),
    nG: st.nG,
    meanG: st.meanG != null ? Math.round(st.meanG) : null,
    maxG: st.maxG,
    predLo,
    predHi,
    olor,
    cierreEst: brillo.bandaTotal || "—",
  };
}

/**
 * Actualiza registro de bloques: cierra bloques ya pasados.
 * @returns {Array} registro completo (0..2)
 */
export function actualizarRegistroBloques(registroPrev = [], { tiros = [], minuto = 0, tag = "" } = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const byId = new Map((registroPrev || []).map((b) => [b.id, b]));

  for (const bloque of BLOQUES) {
    if (T >= bloque.hi && !byId.has(bloque.id)) {
      const snap = snapshotBloque({ tiros, tag, blockId: bloque.id });
      if (snap) byId.set(bloque.id, { ...snap, cerradoEn: T });
    }
  }

  // Bloque en curso (parcial)
  const curId = T < 20 ? 0 : T < 40 ? 1 : 2;
  const cur = BLOQUES[curId];
  const st = statsAt(tiros, T);
  const brillo = buildBrilloLectura({ tiros, minuto: T, tag });
  const enCurso = {
    id: curId,
    label: cur.label,
    minuto: T,
    enCurso: true,
    acum: Math.round(st.acum),
    nG: st.nG,
    meanG: st.meanG != null ? Math.round(st.meanG) : null,
    maxG: st.maxG,
    predLo: brillo.predLo,
    predHi: brillo.predHi,
    cierreEst: brillo.bandaTotal || "—",
    olor: "—",
  };
  if (st.acum >= SN_UMBRAL) enCurso.olor = "confirmada";
  else if (T >= SN_MIN_ALERTA && brillo.predHi != null && brillo.predHi >= SN_UMBRAL) {
    enCurso.olor = "alerta";
  } else if (T >= SN_MIN_OLOR && brillo.predHi != null && brillo.predHi >= SN_OLOR) {
    enCurso.olor = "olor";
  } else if (T >= SN_MIN_ALERTA) enCurso.olor = "baja";

  const ordenados = BLOQUES.map((b) => byId.get(b.id)).filter(Boolean);
  return { cerrados: ordenados, enCurso, curId };
}

/**
 * Estado de alerta supernova para la hora en curso.
 */
export function evalAlertaSupernova({
  brillo,
  minuto = 0,
  acum = 0,
  n500 = 0,
  horaCerrada = false,
} = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const predHi = brillo?.predHi ?? null;

  if (acum >= SN_UMBRAL || (brillo?.acum != null && brillo.acum >= SN_UMBRAL)) {
    return {
      estado: "confirmada",
      activa: true,
      parpadea: false,
      pasada: true,
      nivel: 3,
    };
  }

  // Hora cerrada o último tramo sin llegar a 1600 — antes que proyección stale
  if (horaCerrada || T >= 58) {
    return {
      estado: "descartada",
      activa: false,
      parpadea: false,
      pasada: true,
      nivel: 0,
    };
  }

  if (T >= SN_MIN_ALERTA && predHi != null && predHi >= SN_UMBRAL) {
    return {
      estado: "alerta",
      activa: true,
      parpadea: true,
      pasada: false,
      nivel: 2,
    };
  }

  if (T >= SN_MIN_OLOR && predHi != null && predHi >= SN_OLOR) {
    return {
      estado: "olor",
      activa: true,
      parpadea: true,
      pasada: false,
      nivel: 1,
    };
  }

  // Signo temprano SN: cola G>500 + proyección ≥1400 desde min 20 (lab)
  if (T >= 20 && n500 > 0 && predHi != null && predHi >= SN_OLOR) {
    return {
      estado: "olor",
      activa: true,
      parpadea: true,
      pasada: false,
      nivel: 1,
      temprano: true,
    };
  }

  return {
    estado: "reposo",
    activa: false,
    parpadea: false,
    pasada: false,
    nivel: 0,
  };
}

/**
 * Lectura completa para modal + icono.
 */
export function buildSupernovaLectura({
  tiros = [],
  minuto = 0,
  tag = "",
  registroBloques = [],
  alertaPrev = null,
  lineas = [],
  horaCerrada = false,
  brillo: brilloIn = null,
} = {}) {
  const meta = parseTag(tag);
  const hod = meta?.hora ?? 0;
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const brillo =
    brilloIn || buildBrilloLectura({ tiros, minuto: T, tag, cintaLineas: lineas });
  const st = statsAt(tiros, T);

  let alerta = evalAlertaSupernova({
    brillo,
    minuto: T,
    acum: st.acum,
    n500: st.n500,
    horaCerrada,
  });

  const minSn = minutoConfirmacionSn(tiros, T);
  if (alerta.estado === "confirmada") {
    alerta = { ...alerta, minSn };
  }

  // Persistir parpadeo solo mientras la hora sigue en curso
  if (alertaPrev?.parpadeaba && !alerta.pasada && !horaCerrada) {
    if (alerta.estado === "reposo" && alertaPrev.nivel >= 1) {
      const projBajo =
        brillo.predHi == null || brillo.predHi < SN_OLOR;
      if (projBajo && T >= 40) {
        alerta = {
          estado: "enfrió",
          activa: false,
          parpadea: false,
          pasada: true,
          nivel: 0,
        };
      } else if (!projBajo) {
        alerta = { ...alertaPrev, parpadea: true, activa: true, pasada: false };
      }
    }
  }

  const parpadeaba =
    !horaCerrada &&
    (alerta.parpadea || (alertaPrev?.parpadeaba && !alerta.pasada));
  const indicadores = buildIndicadoresProyeccion({
    acum: st.acum,
    predLo: brillo.predLo,
    predHi: brillo.predHi,
    T,
  });
  const lineasTexto = [];

  if (alerta.estado === "confirmada") {
    lineasTexto.push(
      `Supernova confirmada${minSn != null ? ` al min ${minSn}` : ""}: van ${Math.round(st.acum)} lumen (≥${SN_UMBRAL}).`
    );
    if (!horaCerrada) {
      lineasTexto.push(
        `SN ya pasó — icono fijo. Olor de cola post-SN va en el icono ~ junto a Next.`
      );
    }
    lineasTexto.push(
      `Cada G ~${st.meanG != null ? Math.round(st.meanG) : "—"} lumen · ${st.nG} G hasta el min ${T}.`
    );
    if (horaCerrada) {
      lineasTexto.push(`La hora cerró en zona excepcional.`);
    }
  } else if (alerta.estado === "alerta") {
    lineasTexto.push(`Alerta supernova al min ${T} (~9/10 si cierra ≥${SN_UMBRAL}).`);
    lineasTexto.push(
      `Van ${Math.round(st.acum)} lumen · proyección ${brillo.predLo}–${brillo.predHi}.`
    );
    lineasTexto.push(`La cola (40–59) suele definir el cierre.`);
  } else if (alerta.estado === "olor") {
    lineasTexto.push(`Olor de supernova desde el min ${T}.`);
    lineasTexto.push(
      `Proyección ${brillo.predLo ?? "—"}–${brillo.predHi ?? "—"} · confirmación fiable ~min 40.`
    );
  } else if (alerta.estado === "enfrió") {
    lineasTexto.push(`La alerta enfrió: proyección ya no apunta a supernova.`);
    lineasTexto.push(`Van ${Math.round(st.acum)} lumen al min ${T}.`);
  } else if (alerta.estado === "descartada") {
    lineasTexto.push(`Hora sin supernova (cierra bajo ${SN_UMBRAL}).`);
    lineasTexto.push(`Total ${Math.round(st.acum)} lumen · ${st.nG} G.`);
  } else if (T < SN_MIN_OLOR) {
    lineasTexto.push(`Proyección: sesgo hod hasta el min ${SN_MIN_OLOR}.`);
    if (indicadores.projLabel) {
      lineasTexto.push(`Banda estimada al cierre: ${indicadores.projLabel}.`);
    }
    lineasTexto.push(`Alerta supernova fiable ~min ${SN_MIN_ALERTA} (≥${SN_UMBRAL}).`);
  } else {
    lineasTexto.push(`Proyección al min ${T}: ${indicadores.projLabel || "—"}.`);
    if (indicadores.projRangoLabel) {
      lineasTexto.push(`Rango posible: ${indicadores.projRangoLabel} · confianza ${indicadores.confianza}.`);
    }
    if (indicadores.actualLabel) {
      lineasTexto.push(`Luz acumulada ahora: ${Math.round(st.acum)} (${indicadores.actualLabel}).`);
    }
    if (brillo.predLo != null) {
      lineasTexto.push(`Cierre estimado: ${brillo.predLo}–${brillo.predHi} lumen.`);
    }
  }

  const pill =
    alerta.estado === "confirmada"
      ? "confirmada"
      : alerta.estado === "alerta"
        ? "alerta"
        : alerta.estado === "olor"
          ? "olor"
          : alerta.estado === "enfrió"
            ? "enfrió"
            : alerta.estado === "descartada"
              ? "sin SN"
              : T < SN_MIN_OLOR
                ? "esperando"
                : "reposo";

  const pillProy = indicadores.projLabel || brillo.bandaTotal || pill;

  const visible = true;

  const fingerprint = [
    tag,
    alerta.estado,
    pillProy,
    T,
    Math.round(st.acum / 50) * 50,
    brillo.predHi ?? "-",
    indicadores.projIdx,
    registroBloques?.length ?? 0,
  ].join("|");

  return {
    ok: true,
    tag,
    hod,
    T,
    pill: pillProy,
    pillAlerta: pill,
    tone:
      alerta.estado === "confirmada"
        ? "confirmada"
        : alerta.estado === "alerta"
          ? "alerta"
          : alerta.estado === "olor"
            ? "olor"
            : "reposo",
    lineas: lineasTexto,
    brillo,
    alerta,
    parpadea: horaCerrada ? false : alerta.parpadea || (parpadeaba && !alerta.pasada),
    parpadeaba,
    visible,
    registroBloques,
    acum: Math.round(st.acum),
    predLo: brillo.predLo,
    predHi: brillo.predHi,
    indicadores,
    n500: st.n500,
    maxG: st.maxG,
    tipsLab: buildTipsLab({
      st,
      alerta,
      indicadores,
      brillo,
      T,
      parpadeaba,
    }),
    generosidad: buildGenerosidadLectura({
      tag,
      lineas,
      hod,
      acumHora: st.acum,
    }),
    fingerprint,
  };
}

export function supernovaTooltipTitle(lectura) {
  if (!lectura) return "Supernova";
  const ind = lectura.indicadores;
  const proy = ind?.projLabel ? `Proyecta: ${ind.projLabel}` : "";
  const conf = ind?.confianza ? `Confianza: ${ind.confianza}` : "";
  const base =
    lectura.alerta?.estado === "confirmada"
      ? `SN confirmada al min ${lectura.alerta.minSn ?? "—"} · ${lectura.acum} lm`
      : lectura.parpadea
        ? `Supernova · signos SN activos`
        : `Supernova · min ${lectura.T}`;
  const parts = [base, proy, conf].filter(Boolean);
  if (lectura.predLo != null) {
    parts.push(`${lectura.predLo}–${lectura.predHi} lumen`);
  }
  return parts.join("\n");
}
