/**
 * Go! sequía — alineado a Next 3 (poda +1).
 * Ventana = 3 tiros +2,+3,+4 tras G (se deja pasar el pegado).
 * Excepción: Tren (2+ G) o Estirada (G ≥100 s) → el pegado SÍ entra.
 * Sequía: gap≥5 (rachaR ≥ 4) → No-Go. Alarma MP3 = solo Pool 7.
 */
import { minutoDesdeEnCurso, tipSiguienteG } from "./tipProxima.js";

/** Tamaño de la ventana (3 tiros). Tras poda vive en gaps 2..4. */
export const VENTANA_SEQUIA = 3;
/** Primer gap de ventana tras dejar pasar el pegado. */
export const VENTANA_GAP_MIN = 2;
/** Último gap de ventana (+4). Sequía desde gap 5. */
export const VENTANA_GAP_MAX = 4;

function distAnillo(a, b) {
  const d = Math.abs((Number(a) % 60) - (Number(b) % 60));
  return Math.min(d, 60 - d);
}

/**
 * Duración en segundos de un tiro ({m0, s0, m1, s1}).
 */
function duracionSegundos(t) {
  if (!t || t.m0 == null || t.s0 == null || t.m1 == null || t.s1 == null) return null;
  const sIni = Number(t.m0) * 60 + Number(t.s0);
  const sFin = Number(t.m1) * 60 + Number(t.s1);
  return ((sFin - sIni) + 3600) % 3600;
}

/**
 * Diagnóstico completo del estado de pulso y riesgo para el tiro en curso.
 * @param {Array<{ color?: string, m0?: number, s0?: number, m1?: number, s1?: number, tipo?: number, vecino?: number, lumen?: number }>|null|undefined} tiros
 */
export function diagnosticarGo(tiros) {
  const list = tiros || [];
  const gIndices = [];
  for (let i = 0; i < list.length; i += 1) {
    if (String(list[i].color || "").toUpperCase().startsWith("G")) {
      gIndices.push(i);
    }
  }

  // 1. Caso: ninguna G en la hora (mesa sin arrancar aún)
  if (!gIndices.length) {
    const rachaR = list.length;
    const desc = rachaR > 0 ? `${rachaR} R seguidas sin G` : "Esperando primer tiro";
    return {
      activo: false,
      gap: rachaR + 1,
      tipo: "nogo",
      etiqueta: "No-Go",
      badge: rachaR > 0 ? `${rachaR} R` : "—",
      subtitulo: rachaR >= 4 ? `Sequía activa (${rachaR} R)` : `Mesa fría (${rachaR} R)`,
      riesgo: "alto",
      riesgoLabel: "Riesgo Alto (Evitar)",
      probabilidad: "< 5% · Desierto",
      rachaR,
      gConsecutivas: 0,
      durG: null,
      multG: null,
      motivo: rachaR >= 4
        ? `Sequía activa: van ${rachaR} tiros rojos seguidos sin G. No gastar fichas.`
        : `La hora aún no abre su primera G (${rachaR} R). Esperar al rompe-sequía.`,
      tooltip: [
        `[No-Go · Riesgo Alto]`,
        `• Estado: Sequía inicial (${rachaR} R sin G)`,
        `• Diagnóstico: Mesa fría · fuera de ventana`,
        `• Recomendación: No apostar · esperar que caiga la primera G`,
      ].join("\n"),
    };
  }

  const lastGIdx = gIndices[gIndices.length - 1];
  const gap = list.length - lastGIdx; // 1 = último cerrado fue G, 2 = 1 R entremedio, etc.
  const ultimaG = list[lastGIdx];
  const durG = duracionSegundos(ultimaG);
  const esLarga = durG != null && durG >= 100;
  const multG = ultimaG?.vecino ?? ultimaG?.lumen ?? (ultimaG?.tipo != null ? `G${ultimaG.tipo}` : null);
  const gConsecutivas = gConsecutivasHasta(list, lastGIdx);
  const trenOEstirada = gConsecutivas >= 2 || esLarga;
  const gTxt = `${multG ? `x${multG}` : "G"} (${durG ?? "—"}s)`;

  // 2. Caso: Gap = 1 (pegado). Poda, salvo Tren / Estirada.
  if (gap === 1) {
    if (gConsecutivas >= 2) {
      return {
        activo: true,
        gap: 1,
        tipo: "tren",
        etiqueta: "Go! ⚡ Tren",
        badge: "⚡ Tren",
        subtitulo: `${gConsecutivas} G seguidas · el pegado sí entra`,
        riesgo: "bajo",
        riesgoLabel: "Inercia Tren · pegado entra",
        probabilidad: "Inercia · pegado sí entra",
        rachaR: 0,
        gConsecutivas,
        durG,
        multG,
        motivo: `Tren activo: ${gConsecutivas} G consecutivas. Inercia: el pegado sí entra (excepción a la poda +1).`,
        tooltip: [
          `[Go! ⚡ Tren · inercia]`,
          `• Diagnóstico: Tren (${gConsecutivas} G seguidas) · G previa: ${gTxt}`,
          `• Excepción: el pegado sí entra (no se poda)`,
          `• Después: ventana de 3 = los tiros +2,+3,+4`,
          `• Recomendación: Inercia · sí jugar este tiro`,
        ].join("\n"),
      };
    }

    if (esLarga) {
      return {
        activo: true,
        gap: 1,
        tipo: "estirada",
        etiqueta: "Go! ⏱ Estirada",
        badge: "⏱ Estirada",
        subtitulo: `Bonus ${durG}s · el pegado sí entra`,
        riesgo: "bajo",
        riesgoLabel: "Inercia Estirada · pegado entra",
        probabilidad: "Inercia · pegado sí entra",
        rachaR: 0,
        gConsecutivas: 1,
        durG,
        multG,
        motivo: `Estirada: la última G duró ${durG}s. Inercia: el pegado sí entra (excepción a la poda +1).`,
        tooltip: [
          `[Go! ⏱ Estirada · inercia]`,
          `• Diagnóstico: Bonus largo (${durG}s) · ${multG ? `x${multG}` : "G"}`,
          `• Excepción: el pegado sí entra (no se poda)`,
          `• Después: ventana de 3 = los tiros +2,+3,+4`,
          `• Recomendación: Inercia · sí jugar este tiro`,
        ].join("\n"),
      };
    }

    return {
      activo: false,
      gap: 1,
      tipo: "pasa",
      etiqueta: "Pasa",
      badge: "pasa",
      subtitulo: `Poda +1 · se deja pasar el pegado`,
      riesgo: "pasa",
      riesgoLabel: "Poda +1 (no jugar el pegado)",
      probabilidad: "Pasa · ventana = +2,+3,+4",
      rachaR: 0,
      gConsecutivas: 1,
      durG,
      multG,
      motivo: `Poda +1: se deja pasar el pegado. La ventana Go! son los 3 tiros siguientes (+2,+3,+4), no este.`,
      tooltip: [
        `[Pasa · poda +1]`,
        `• Diagnóstico: G normal · G previa: ${gTxt}`,
        `• Este tiro: se deja pasar (no es el primero de la ventana)`,
        `• Ventana: los 3 siguientes (+2,+3,+4) vs tip ±1`,
        `• Recomendación: No jugar el pegado · esperar la ventana`,
      ].join("\n"),
    };
  }

  // 3. Ventana de 3 tras la poda (gaps 2, 3, 4 = tiros 1/3, 2/3, 3/3)
  if (gap === 2) {
    return {
      activo: true,
      gap: 2,
      tipo: "go1",
      etiqueta: "Go! 1",
      badge: "Tiro 1/3",
      subtitulo: `Ventana 1/3 · pegado ya pasó`,
      riesgo: "medio-bajo",
      riesgoLabel: "Ventana 1/3 (tras poda)",
      probabilidad: "Ventana +2,+3,+4 · minutos vs tip ±1",
      rachaR: 1,
      gConsecutivas: 0,
      durG,
      multG,
      motivo: `Primer tiro de la ventana (el pegado se dejó pasar). Tres tiros: +2,+3,+4.`,
      tooltip: [
        `[Go! 1 · ventana 1/3]`,
        `• Diagnóstico: Se dejó pasar el pegado · G previa: ${gTxt}`,
        `• Ventana: tiro 1 de 3 (este es el +2, no el primero tras G)`,
        `• Oficio: minutos de la ventana vs tip ±1 · no P(tiro=G)`,
        `• Recomendación: En ventana · primer tiro de los tres`,
      ].join("\n"),
    };
  }

  if (gap === 3) {
    return {
      activo: true,
      gap: 3,
      tipo: "go2",
      etiqueta: "Go! 2",
      badge: "Tiro 2/3",
      subtitulo: `Ventana 2/3 · pegado ya pasó`,
      riesgo: "medio",
      riesgoLabel: "Ventana 2/3 (tras poda)",
      probabilidad: "Ventana +2,+3,+4 · minutos vs tip ±1",
      rachaR: 2,
      gConsecutivas: 0,
      durG,
      multG,
      motivo: `Segundo tiro de la ventana (el pegado se dejó pasar). Queda este y el +4.`,
      tooltip: [
        `[Go! 2 · ventana 2/3]`,
        `• Diagnóstico: Ventana tras poda · G previa: ${gTxt}`,
        `• Ventana: tiro 2 de 3 (este es el +3)`,
        `• Oficio: minutos de la ventana vs tip ±1 · no P(tiro=G)`,
        `• Recomendación: En ventana · segundo de los tres`,
      ].join("\n"),
    };
  }

  if (gap === 4) {
    return {
      activo: true,
      gap: 4,
      tipo: "go3",
      etiqueta: "Go! 3",
      badge: "Tiro 3/3",
      subtitulo: `Ventana 3/3 · último de los tres`,
      riesgo: "alerta",
      riesgoLabel: "Ventana 3/3 (cierre)",
      probabilidad: "Último de +2,+3,+4 · minutos vs tip ±1",
      rachaR: 3,
      gConsecutivas: 0,
      durG,
      multG,
      motivo: `Último tiro de la ventana (+4). Si no es G, sequía: no perseguir.`,
      tooltip: [
        `[Go! 3 · ventana 3/3]`,
        `• Diagnóstico: Cierre de ventana · G previa: ${gTxt}`,
        `• Ventana: tiro 3 de 3 (este es el +4; el pegado ya se dejó pasar)`,
        `• Oficio: minutos de la ventana vs tip ±1 · no P(tiro=G)`,
        `• Recomendación: Último de los tres · si falla, No-Go`,
      ].join("\n"),
    };
  }

  // 4. Gap >= 5 (4 o más R · sequía, un tiro más tarde que antes)
  const rachaR = gap - 1;
  return {
    activo: false,
    gap,
    tipo: "nogo",
    etiqueta: "No-Go",
    badge: `${rachaR} R`,
    subtitulo: `Sequía activa (${rachaR} R sin G)`,
    riesgo: "alto",
    riesgoLabel: "Riesgo Alto (Evitar)",
    probabilidad: "Fuera de ventana · sequía",
    rachaR,
    gConsecutivas: 0,
    durG,
    multG,
    motivo: `Sequía: van ${rachaR} tiros rojos seguidos sin G (la ventana +2,+3,+4 ya pasó). No perseguir.`,
    tooltip: [
      `[No-Go · sequía]`,
      `• Diagnóstico: Sequía (${rachaR} R sin G) · ventana +2,+3,+4 cerrada`,
      `• Estado: Fuera de ventana · no perseguir`,
      `• Recomendación: No apostar · esperar que la mesa rompa con una G`,
    ].join("\n"),
  };
}

/**
 * @param {Array<{ color?: string }>|null|undefined} tiros cerrados de la hora (orden).
 * @returns {boolean} true = Go! · false = No-Go
 */
export function esGoSequia(tiros) {
  return diagnosticarGo(tiros).activo;
}

/**
 * ¿Esta G cayó en ventana Go! de la G previa?
 * Normal: gaps 2..4 (+2,+3,+4). Tren/Estirada: también gap 1 (pegado).
 */
function enVentanaGo(gap, trenOEstirada) {
  if (gap === 1) return trenOEstirada;
  return gap >= VENTANA_GAP_MIN && gap <= VENTANA_GAP_MAX;
}

/**
 * Minutos de G reales donde hubo Go! (ventana +2..+4, o pegado Tren/Estirada)
 * y tip LC acertó banda ±1.
 * @param {Array<{ color?: string, m0?: number }>|null|undefined} tiros
 * @returns {number[]}
 */
export function minutosGoAcierto(tiros) {
  const list = tiros || [];
  const gIdx = [];
  for (let i = 0; i < list.length; i += 1) {
    if (String(list[i].color || "").toUpperCase().startsWith("G")) gIdx.push(i);
  }
  const hits = [];
  for (let k = 1; k < gIdx.length; k += 1) {
    const prev = gIdx[k - 1];
    const gap = gIdx[k] - prev;
    const durPrev = duracionSegundos(list[prev]);
    const trenOEstirada =
      gConsecutivasHasta(list, prev) >= 2 || (durPrev != null && durPrev >= 100);
    if (!enVentanaGo(gap, trenOEstirada)) continue;
    const luces = gIdx.slice(0, k).map((i) => list[i].m0);
    const { tip } = tipSiguienteG({ luces, minutoAhora: null });
    const real = list[gIdx[k]].m0;
    if (tip != null && distAnillo(tip, real) <= 1) hits.push(real);
  }
  return hits;
}

function esColorG(t) {
  return String(t?.color || "").toUpperCase().startsWith("G");
}

function padMin(m) {
  if (m == null || Number.isNaN(Number(m))) return "—";
  return String(Math.floor(Number(m) % 60)).padStart(2, "0");
}

function gConsecutivasHasta(list, lastGIdx) {
  let n = 0;
  for (let i = lastGIdx; i >= 0; i -= 1) {
    if (esColorG(list[i])) n += 1;
    else break;
  }
  return n;
}

/** Minuto estimado del tiro en shotIdx (cerrado, en curso o pendiente ~+1 min/tiro). */
function minutoEstimadoSlot(shotIdx, list, tiroEnCurso) {
  if (shotIdx < list.length) {
    const m0 = list[shotIdx]?.m0;
    return m0 != null && !Number.isNaN(Number(m0)) ? Number(m0) : null;
  }
  const mCurso = minutoDesdeEnCurso(tiroEnCurso);
  if (shotIdx === list.length && mCurso != null) return mCurso;

  let base = null;
  let fromIdx = list.length - 1;
  if (mCurso != null) {
    base = mCurso;
    fromIdx = list.length;
  } else if (list.length) {
    const last = list[list.length - 1];
    base = last.m1 != null ? Number(last.m1) : Number(last.m0);
  }
  if (base == null || Number.isNaN(base)) return null;
  return (Math.floor(base) + (shotIdx - fromIdx)) % 60;
}

function enZonaTip(minEst, tipVal) {
  if (tipVal == null || minEst == null || Number.isNaN(Number(minEst))) return false;
  return distAnillo(Math.floor(Number(minEst)), tipVal) <= 1;
}

function deltaVsTip(tipVal, minEst) {
  if (tipVal == null || minEst == null || Number.isNaN(Number(minEst))) return null;
  let d = (Math.floor(Number(minEst)) - Math.floor(Number(tipVal)) + 60) % 60;
  if (d > 30) d -= 60;
  return d;
}

function fmtDelta(d) {
  if (d == null) return null;
  if (d === 0) return "Δ 0";
  return d > 0 ? `Δ +${d}` : `Δ ${d}`;
}

function marcaSlot(esPoda, zona) {
  if (esPoda) return "pasa";
  if (zona) return "zona";
  return "fuera";
}

/**
 * Next 3 — cronómetro de la ventana V3 (3 tiros), no adivina color.
 * Cada casilla: minuto del tiro + pasa / zona / fuera vs tip Pool 7 ±1.
 * Poda +1 (salvo Tren/Estirada). Sequía: 3 tiros de ventana sin G → silencio.
 * El tono no estira el tip.
 */
export function diagnosticarNext3({ tiros = [], tiroEnCurso = null, tipProx = null } = {}) {
  const list = tiros || [];
  const gIndices = [];
  for (let i = 0; i < list.length; i += 1) {
    if (esColorG(list[i])) gIndices.push(i);
  }

  if (!gIndices.length) {
    const enC = Boolean(tiroEnCurso);
    return {
      activo: false,
      enSequia: false,
      fase: "espera",
      rachaR: list.length,
      slots: [
        {
          slot: 1,
          marca: null,
          texto: enC ? "⏳" : "·",
          clase: enC ? "en-curso espera" : "espera",
          title: enC ? `Tiro 1: en juego (${tiroEnCurso}) · esperando 1ª G` : "Tiro 1: esperando 1ª G",
        },
        { slot: 2, marca: null, texto: "·", clase: "espera", title: "Tiro 2: pendiente" },
        { slot: 3, marca: null, texto: "·", clase: "espera", title: "Tiro 3: pendiente" },
      ],
      textoResumen: enC ? "⏳ · ·" : "· · ·",
      aciertosG: 0,
      tooltip: "Next 3 · Esperando primera G · después: minutos de la ventana vs tip ±1",
    };
  }

  const lastGIdx = gIndices[gIndices.length - 1];
  const gap = list.length - lastGIdx;
  const ultimaG = list[lastGIdx];
  const durG = duracionSegundos(ultimaG);
  const trenOEstirada = gConsecutivasHasta(list, lastGIdx) >= 2 || (durG != null && durG >= 100);
  const tipVal = tipProx?.tip != null && !Number.isNaN(Number(tipProx.tip)) ? Number(tipProx.tip) : null;
  const tipTxt = tipVal != null ? padMin(tipVal) : "—";

  const fase = gap === 1 ? (trenOEstirada ? "inercia" : "poda") : "ventana";
  const windowStart = gap === 1 ? lastGIdx + 1 : lastGIdx + 2;
  const rachaR = Math.max(0, gap - 1);
  const enSequia = fase === "ventana" && rachaR >= 4;

  const slots = [];
  let aciertosG = 0;

  for (let s = 1; s <= 3; s += 1) {
    const shotIdx = windowStart + s - 1;
    const stepFromG = shotIdx - lastGIdx;
    const esPoda = stepFromG === 1 && !trenOEstirada;
    const sellado = shotIdx < list.length;
    const enCurso = !sellado && shotIdx === list.length && tiroEnCurso != null;
    let minEst = null;
    if (sellado) {
      const m0 = list[shotIdx].m0;
      minEst = m0 != null && !Number.isNaN(Number(m0)) ? Number(m0) : null;
    } else {
      minEst = minutoEstimadoSlot(shotIdx, list, tiroEnCurso);
    }
    const zona = !esPoda && enZonaTip(minEst, tipVal);
    const marca =
      minEst == null && !sellado && !enCurso ? null : marcaSlot(esPoda, zona);
    const dlt = fmtDelta(deltaVsTip(tipVal, minEst));

    if (enSequia && !sellado && !enCurso) {
      slots.push({
        slot: s,
        marca: null,
        minEst,
        zona: false,
        tipHit: false,
        texto: "—",
        clase: "espera sequia",
        title: `Tiro ${s} · sequía · ventana de 3 cerrada · tip ${tipTxt}`,
      });
      continue;
    }

    const actual = sellado ? (esColorG(list[shotIdx]) ? "G" : "R") : null;
    if (actual === "G") aciertosG += 1;
    const tipHit = zona && actual === "G";

    let texto = minEst == null ? "·" : `${padMin(minEst)} ${marca}`;
    let clase = `${marca || "espera"} pendiente`;
    if (sellado) {
      texto = minEst == null ? "—" : `${padMin(minEst)} ${marca}`;
      clase = `${marca || "espera"} sellado${tipHit ? " tip-hit" : ""}`;
    } else if (enCurso) {
      texto = minEst == null ? "⏳" : `${padMin(minEst)}⏳`;
      clase = `${marca || "espera"} en-curso`;
    }

    slots.push({
      slot: s,
      marca,
      minEst,
      zona,
      tipHit,
      texto,
      clase,
      title: [
        `Tiro ${s}${enCurso ? ` en juego (${tiroEnCurso})` : sellado ? " sellado" : " pendiente"}`,
        minEst != null ? `min ${padMin(minEst)}` : null,
        marca,
        dlt,
        tipVal != null ? `tip ${tipTxt} ±1` : "sin tip aún",
        esPoda ? "Poda +1 · se deja pasar" : null,
        trenOEstirada && stepFromG === 1 ? "Inercia Tren/Estirada · sí entra" : null,
        tipHit ? "G en zona Pool 7" : null,
        sellado && actual ? `salió ${actual}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
    });
  }

  const textoResumen = slots.map((s) => s.texto).join(" · ");
  const motivoFase =
    fase === "poda"
      ? `Poda +1: se deja pasar · los otros dos ya miran tip ${tipTxt} ±1`
      : fase === "inercia"
        ? `Inercia Tren/Estirada · el pegado sí entra`
        : enSequia
          ? `Sequía: 3 tiros de ventana sin G · no perseguir`
          : `Ventana · minuto de cada tiro vs tip ${tipTxt} ±1`;

  return {
    activo: !enSequia,
    enSequia,
    fase,
    rachaR,
    slots,
    textoResumen,
    aciertosG,
    tooltip: [`Next 3: ${textoResumen}`, motivoFase, `G ancla min ${padMin(ultimaG?.m0)}`].join(" · "),
  };
}

const APOSTADOR_TOOLTIP = "silla · si cae G, banda ~88% hold · no es color";

/**
 * Apostador (SILLA / SOLO_ZONA) — pastilla Sí / No / Pasa.
 * Causal: ancla = última G, tip = tipProx.tip, gap = tiros desde ancla,
 * m_est = (m0_ancla + gap) % 60. Dist anillo ≤1.
 * Sí = silla de minuto. NO es “apuesta que este tiro es G” (SILLA_TODOS FRÍO).
 * Pasa = G recién caída, +1, poda (salvo Tren 2+ G o Estirada ≥100s).
 * No = sequía (4 R / gap≥5), mesa sin G, o ventana +2..+4 fuera del tip.
 * tiroEnCurso nombra el slot (en curso o próximo); no entra a m_est.
 */
export function diagnosticarApostador({
  tiros = [],
  tiroEnCurso = null,
  tipProx = null,
} = {}) {
  void tiroEnCurso;
  const list = tiros || [];
  const gIndices = [];
  for (let i = 0; i < list.length; i += 1) {
    if (esColorG(list[i])) gIndices.push(i);
  }

  const tipVal =
    tipProx?.tip != null && !Number.isNaN(Number(tipProx.tip))
      ? Number(tipProx.tip)
      : null;

  const pack = (estado, extra = {}) => ({
    estado,
    etiqueta: estado === "si" ? "Sí" : estado === "pasa" ? "Pasa" : "No",
    tooltip: APOSTADOR_TOOLTIP,
    silla: Boolean(extra.silla),
    gap: extra.gap ?? null,
    mEst: extra.mEst ?? null,
    tip: tipVal,
    mAncla: extra.mAncla ?? null,
    trenOEstirada: Boolean(extra.trenOEstirada),
    motivo: extra.motivo || "",
  });

  if (!gIndices.length) {
    return pack("no", { gap: list.length + 1, rachaR: list.length, motivo: "mesa sin G" });
  }

  const lastGIdx = gIndices[gIndices.length - 1];
  const gap = list.length - lastGIdx;
  const ultimaG = list[lastGIdx];
  const mAncla =
    ultimaG?.m0 != null && !Number.isNaN(Number(ultimaG.m0))
      ? Math.floor(Number(ultimaG.m0))
      : null;
  const durG = duracionSegundos(ultimaG);
  const trenOEstirada =
    gConsecutivasHasta(list, lastGIdx) >= 2 || (durG != null && durG >= 100);
  const mEst = mAncla != null ? (mAncla + gap) % 60 : null;
  const silla = tipVal != null && mEst != null && distAnillo(mEst, tipVal) <= 1;

  if (gap >= 5) {
    return pack("no", {
      gap,
      mEst,
      mAncla,
      silla: false,
      trenOEstirada,
      motivo: "sequía",
    });
  }

  if (gap === 1 && !trenOEstirada) {
    return pack("pasa", {
      gap,
      mEst,
      mAncla,
      silla: false,
      trenOEstirada,
      motivo: "poda +1",
    });
  }

  if (silla) {
    return pack("si", {
      gap,
      mEst,
      mAncla,
      silla: true,
      trenOEstirada,
      motivo: trenOEstirada && gap === 1 ? "tren/estirada silla" : "silla",
    });
  }

  return pack("no", {
    gap,
    mEst,
    mAncla,
    silla: false,
    trenOEstirada,
    motivo: trenOEstirada && gap === 1 ? "tren/estirada fuera tip" : "ventana fuera tip",
  });
}
