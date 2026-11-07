/**
 * Cola G INFO — lab-g-cola (4 rondas). G suelta >400/500.
 * INFO · no boleto · no supernova (suma hora).
 */
import { anteriorTag, parseTag } from "./live.js";
import {
  GEN_DIA_PCT,
  GEN_HOD_OLOR,
  GEN_SUM_UMBRAL,
  horasDeLineasCached,
} from "./generosidadInfo.js";
import {
  refuerzoAperturaCostura1415,
  tirosDeHoraEnLineas,
} from "./intraHoraInfo.js";
import { SN_UMBRAL } from "./supernovaInfo.js";
import { COSTURA_SUM_FUERTE } from "./costuraInfo.js";

export const COLA_UMBRAL_ALTO = 400;
export const COLA_UMBRAL = 500;
const CORTE_LARGO_S = 70;
const MIN_HORAS_DIA = 12;

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function tagHodSameDay(tag, hod) {
  const t = parseTag(tag);
  if (!t) return null;
  const dd = String(t.dia).padStart(2, "0");
  const mm = String(t.mes).padStart(2, "0");
  const yy = String(t.anio).slice(-2);
  return `h${hod}-${dd}${mm}${yy}`;
}

function estadoCola(tiros = [], T = 0) {
  const gs = [];
  let acum = 0;
  let maxG = 0;
  for (const t of tiros || []) {
    if (!t || t.m0 > T) continue;
    const lm = lumenOf(t);
    if (lm == null) continue;
    acum += lm;
    if (String(t.color || "").toUpperCase().startsWith("G")) {
      gs.push({ ...t, lumen: lm });
      if (lm > maxG) maxG = lm;
    }
  }
  const nG = gs.length;
  const sumG = gs.reduce((a, g) => a + g.lumen, 0);
  const meanG = nG > 0 ? sumG / nG : null;
  const n400 = gs.filter((g) => g.lumen > COLA_UMBRAL_ALTO).length;
  const n500 = gs.filter((g) => g.lumen > COLA_UMBRAL).length;
  return { acum, maxG, meanG, nG, n400, n500, gs };
}

function horasDelDia(tag, lineas = []) {
  const t = parseTag(tag);
  if (!t || !lineas.length) return [];
  const dk = `${t.dia}-${t.mes}-${t.anio}`;
  return horasDeLineasCached(lineas).filter((h) => h.dayKey === dk);
}

function diaGeneroso(hs) {
  if (hs.length < MIN_HORAS_DIA) return false;
  return hs.filter((h) => h.generosa).length / hs.length >= GEN_DIA_PCT;
}

function g34Fuerte(tiros, T, minLm = 70) {
  return (tiros || []).some(
    (t) =>
      t.m0 <= T &&
      String(t.color || "").toUpperCase().startsWith("G") &&
      lumenOf(t) != null &&
      lumenOf(t) >= minLm &&
      (t.tipo === 3 || t.tipo === 4 || t.tipo === "3" || t.tipo === "4")
  );
}

function duracionS(t) {
  const a = t.m0 * 60 + (t.s0 || 0);
  const b = t.m1 * 60 + (t.s1 || 0);
  return (b - a + 3600) % 3600;
}

function rLargoAntes(tiros, m0G) {
  const tirosOrd = [...(tiros || [])].sort(
    (a, b) => a.m0 - b.m0 || (a.s0 || 0) - (b.s0 || 0)
  );
  for (let i = 0; i < tirosOrd.length; i += 1) {
    const t = tirosOrd[i];
    if (t.color !== "G" || t.m0 !== m0G) continue;
    if (i === 0) return false;
    const prev = tirosOrd[i - 1];
    if (prev.color !== "R") return false;
    return duracionS(prev) >= CORTE_LARGO_S;
  }
  return false;
}

/** Última G fuerte reciente — cola confirmada (descriptivo). */
function colaConfirmada(tiros, T, ventana = 12) {
  const gs = (tiros || [])
    .filter(
      (t) =>
        t.m0 <= T &&
        String(t.color || "").toUpperCase().startsWith("G") &&
        lumenOf(t) != null &&
        lumenOf(t) >= COLA_UMBRAL_ALTO
    )
    .sort((a, b) => b.m0 - a.m0);
  if (!gs.length) return null;
  const g = gs[0];
  if (T - g.m0 > ventana) return null;
  const tipo = g.tipo != null ? Number(g.tipo) : null;
  const es34 = tipo === 3 || tipo === 4;
  const rl = rLargoAntes(tiros, g.m0);
  if (!es34 && lumenOf(g) < COLA_UMBRAL) return null;
  if (!rl && lumenOf(g) < COLA_UMBRAL) return null;
  return { m0: g.m0, lumen: lumenOf(g), tipo, rLargo: rl };
}

function pushTip(tips, seen, tip) {
  if (!tip || seen.has(tip.id)) return;
  seen.add(tip.id);
  tips.push(tip);
}

/**
 * Tips cola G para Brillo / Extracción live.
 * @returns {Array<{id:string, texto:string, alerta?:boolean, tono?:string}>}
 */
export function buildColaGTips({
  tag = "",
  tiros = [],
  minuto = 0,
  lineas = [],
  acum = null,
  meanG = null,
  nG = null,
  maxG = null,
} = {}) {
  const tips = [];
  const seen = new Set();
  const meta = parseTag(tag);
  if (!meta) return tips;

  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const st = estadoCola(tiros, T);
  const acumNow = acum != null ? acum : st.acum;
  const meanNow = meanG != null ? meanG : st.meanG;
  const nGNow = nG != null ? nG : st.nG;
  const maxGNow = maxG != null ? maxG : st.maxG;
  const hod = meta.hora;
  const hsDia = horasDelDia(tag, lineas);
  const hsPrev = hsDia.filter((h) => h.hod < hod);
  const nColaPrev = hsPrev.filter((h) => h.cola500).length;
  const nGenPrev = hsPrev.filter((h) => h.generosa).length;
  const esGenDia = diaGeneroso(hsDia);

  // —— Post supernova H-1 ——
  const prevTag = anteriorTag(tag);
  const prevH = prevTag
    ? horasDeLineasCached(lineas).find((h) => h.tag === prevTag.toLowerCase())
    : null;
  if (prevH?.sumG >= SN_UMBRAL && T <= 35 && st.n500 === 0) {
    pushTip(tips, seen, {
      id: "post-sn-frio",
      texto:
        "Hora anterior cerró supernova — suele enfriar; olor de cola G suelta bajo (lab-g-cola · post-SN).",
      tono: "mute",
    });
  }

  // —— Contexto día ——
  if (esGenDia && T <= 45) {
    pushTip(tips, seen, {
      id: "dia-generoso",
      texto:
        "Día generoso (≥25% horas fuertes) — sube el olor de G >400/500 en horas que sigan (lab-g-cola R4).",
      tono: "olor",
    });
  }
  if (nColaPrev >= 1 && T <= 50) {
    pushTip(tips, seen, {
      id: "dia-caliente-cola",
      texto: `Ya hubo cola G>500 hoy (${nColaPrev} h antes) — día caliente; olor de otra cola en horas siguientes.`,
      tono: "olor",
      alerta: nColaPrev >= 1 && hod >= 14 && hod <= 20,
    });
  }
  if (nGenPrev >= 2 && st.n500 === 0 && T >= 15 && T <= 45) {
    pushTip(tips, seen, {
      id: "dia-vivo-generoso",
      texto:
        "Dos o más horas generosas ya cerraron hoy — la tanda sigue viva; olor cola si esta hora se pone fuerte.",
      tono: "olor",
    });
  }

  // —— Costura h14→h15 ——
  if (hod === 15 && lineas.length) {
    const tag14 = tagHodSameDay(tag, 14);
    const ref = refuerzoAperturaCostura1415({
      lineas,
      tagOrigen: tag14,
    });
    if (ref) {
      pushTip(tips, seen, {
        id: "costura-h14-h15-cola",
        texto: `${ref.linea} Olor de cola G fuerte en h15 (lab-g-cola · costura).`,
        tono: "olor",
        alerta: true,
      });
    }
  }

  // —— Post-h15 techo → h16 ——
  if (hod === 16 && lineas.length) {
    const tag15 = tagHodSameDay(tag, 15);
    const tiros15 = tag15 ? tirosDeHoraEnLineas(lineas, tag15) : [];
    const st15 = estadoCola(tiros15, 59);
    const h15Row = hsDia.find((h) => h.hod === 15);
    const fuerte =
      (h15Row && h15Row.sumG >= COSTURA_SUM_FUERTE) ||
      st15.acum >= COSTURA_SUM_FUERTE;
    if (fuerte && T <= 30) {
      pushTip(tips, seen, {
        id: "post-h15-techo",
        texto:
          "Post-h15 fuerte: costura h15→h16 suele techo/enfriar — no buscar cola tipo supernova en h16 (lab-costura).",
        tono: "mute",
      });
    }
  }

  // —— Hod olor + día generoso ——
  if (
    esGenDia &&
    GEN_HOD_OLOR.includes(hod) &&
    T >= 10 &&
    T <= 40 &&
    st.n500 === 0
  ) {
    pushTip(tips, seen, {
      id: "hod-olor-dia-gen",
      texto: `h${String(hod).padStart(2, "0")} en día generoso — hod con más colas en cinta; olor si la hora se calienta (@39).`,
      tono: "olor",
    });
  }

  // —— Lectura tardía @35+ — hora generosa sin cola aún ——
  if (T >= 35 && st.n500 === 0 && nGNow >= 7 && meanNow != null && meanNow >= 72) {
    pushTip(tips, seen, {
      id: "generosa-39-olor",
      texto:
        "Hora muy viva al cerrar 20–39 — olor de cola G fuerte en lo que queda (40–59 o más). INFO, no pleno.",
      tono: "olor",
      alerta: true,
    });
  }

  // —— Tier B estricto @38+ ——
  if (
    T >= 38 &&
    st.n500 === 0 &&
    maxGNow >= 200 &&
    meanNow != null &&
    meanNow >= 70 &&
    acumNow >= 450 &&
    g34Fuerte(tiros, T, 80)
  ) {
    pushTip(tips, seen, {
      id: "cierre-g34-estricto",
      texto:
        "Perfil cola_cierre: generosa + G3/G4 fuerte sin cola aún — olor máximo en cierre 40–59 (lab-g-cola R2/R3).",
      tono: "fuerte",
      alerta: true,
    });
  }

  // —— Cola confirmada (post-tiro) ——
  const conf = colaConfirmada(tiros, T);
  if (conf) {
    const tipoTxt = conf.tipo ? `G${conf.tipo}` : "G";
    pushTip(tips, seen, {
      id: "cola-confirmada",
      texto: `Cola activa — ${tipoTxt} ${conf.lumen} lm al min ${conf.m0}${
        conf.rLargo ? " tras R largo" : ""
      } (~7/10 colas traen R largo · G3/G4). Descriptivo, no predice la siguiente.`,
      tono: "confirmada",
      alerta: true,
    });
  }

  return tips;
}

/** Línea corta para tooltip Brillo. */
export function colaGTooltipExtra(tips = []) {
  const t = tips.find((x) => x.alerta) || tips[0];
  if (!t) return null;
  const txt = t.texto.length > 72 ? `${t.texto.slice(0, 69)}…` : t.texto;
  return `Cola: ${txt}`;
}

export function colaGTagLive(tips = []) {
  if (!tips.some((t) => t.alerta || t.tono === "confirmada")) return null;
  if (tips.some((t) => t.id === "cola-confirmada")) return "Cola · activa";
  if (tips.some((t) => t.alerta)) return "Cola · olor";
  return null;
}

function fmtHod(h) {
  return `h${String(h).padStart(2, "0")}`;
}

function filaHoraCinta(h) {
  const hh = fmtHod(h.hod);
  let txt = `${hh}: ${h.sumG} lm · ${h.nG} G · max ${h.maxG}`;
  const marcas = [];
  if (h.cola500) marcas.push("cola >500");
  else if (h.cola400) marcas.push("G>400");
  if (h.generosa) marcas.push("generosa");
  else if (h.opaca) marcas.push("opaca");
  if (marcas.length) txt += ` — ${marcas.join(", ")}`;
  return txt;
}

function textoAnterior(h) {
  if (!h) return null;
  const hh = fmtHod(h.hod);
  if (h.cola500) {
    return `${hh} cerró con cola G>${COLA_UMBRAL} (max ${h.maxG} lm, ${h.sumG} lm total).`;
  }
  if (h.generosa) {
    return `${hh} cerró generosa (${h.sumG} lm, max G ${h.maxG}) — calienta la tanda.`;
  }
  if (h.opaca) {
    return `${hh} cerró opaca (${h.sumG} lm) — poco arrastre de cola.`;
  }
  return `${hh} cerró con ${h.sumG} lm (max G ${h.maxG}).`;
}

function esperaDesdeTip(tip, ctx) {
  const { hod, T, nColaPrev } = ctx;
  switch (tip.id) {
    case "cola-confirmada":
      return "Ya cayó una G suelta >400 lm — mirá si el bloque 40–59 trae otra G grande o si la hora se calma.";
    case "cierre-g34-estricto":
      return "Bloque 40–59: perfil muy fuerte (G3/G4 alto, mucha luz acumulada) — ahí puede salir una G >500 lm.";
    case "generosa-39-olor":
      return `Bloque 40–59: hora muy viva al min ${T} (${ctx.nG} G, ~${ctx.meanG} lm de media) — en ese tramo puede explotar una G >500 lm.`;
    case "costura-h14-h15-cola":
      return "h14 abrió tarde — en h15 mirá bloque 20–39 (rebote de luz) y bloque 40–59 (G sueltas grandes).";
    case "dia-caliente-cola":
      return `Día caliente: ${nColaPrev} hora(s) ya tuvieron G>500 — en tarde (14–20) otra G suelta grande es más probable.`;
    case "hod-olor-dia-gen":
      return `${fmtHod(hod)} en día generoso — bloque 40–59 suele traer G >500 lm si la hora se calienta.`;
    case "dia-vivo-generoso":
      return "Varias horas generosas ya cerraron hoy — si esta hora sigue fuerte, bloque 40–59 puede traer G >500 lm.";
    case "dia-generoso":
      return "Día generoso — las horas que sigan tienen más chance de una G suelta >400/500 lm, sobre todo en 40–59.";
    case "post-sn-frio":
      return "Hora anterior cerró supernova — esta hora suele enfriar; G sueltas >500 lm menos probables.";
    case "post-h15-techo":
      return "Post-h15 fuerte — h16 suele techo; G sueltas gigantes menos probables que en h14–h15.";
    default:
      return tip.texto
        .replace(/\s*\(lab-g-cola[^)]*\)/gi, "")
        .replace(/\s*· lab-g-cola[^.]*\./gi, ".")
        .replace(/\s*INFO, no pleno\.?/gi, "")
        .replace(/cola tardía/gi, "G suelta >500 lm en bloque 40–59")
        .replace(/\bolor\b/gi, "aviso")
        .trim();
  }
}

function ventanaEspera(T, pill) {
  if (pill === "Cola · activa") {
    return [
      "Ya cayó una G suelta grande — mirá si el bloque 40–59 trae otra G >500 lm o si la hora se estabiliza.",
    ];
  }
  if (T < 20) {
    return [
      "Bloque 20–39: si las G traen luz alta (>400 lm), puede aparecer una G suelta >500 lm en ese tramo.",
      "Bloque 40–59: ventana principal — si la hora cierra fuerte, ahí suelen explotar las G >500 lm.",
    ];
  }
  if (T < 35) {
    return [
      "Bloque 20–39 (ahora): cada G fuerte (>400 lm) avisa que el cierre puede ser explosivo.",
      "Bloque 40–59 (próximo): si la hora sigue viva, ahí suele caer la G suelta >500 lm.",
    ];
  }
  if (T < 45) {
    return [
      "Bloque 40–59 (activo): mirá cada tiro G — una sola puede superar 500 lm.",
    ];
  }
  return [
    "Últimos minutos del bloque 40–59: si no hubo G>500, el aviso se apaga; si cae, pasa a Cola · activa.",
  ];
}

function buildLead({
  pill,
  hod,
  T,
  acum,
  nG,
  meanG,
  maxG,
  esGenDia,
  nColaPrev,
  nGenPrev,
  anterior,
}) {
  const hh = fmtHod(hod);
  const confParts = [];

  if (pill === "Cola · activa") {
    return `En ${hh} ya hay cola activa — G suelta >${COLA_UMBRAL_ALTO} lm reciente. Mirá el detalle abajo.`;
  }

  const vivaSinCola =
    T >= 35 && nG >= 7 && meanG != null && meanG >= 72 && (maxG == null || maxG < COLA_UMBRAL);
  const generosaCurso = meanG != null && meanG >= 70 && nG >= 5;

  if (vivaSinCola) {
    confParts.push(
      `La ${hh} va generosa y muy viva al min ${T} — ${nG} G, ~${Math.round(meanG)} lm de media, ${acum} lm acumulados — sin G>${COLA_UMBRAL} todavía.`
    );
  } else if (generosaCurso) {
    confParts.push(
      `La ${hh} va generosa (${acum} lm, ${nG} G, max G ${maxG ?? "—"}).`
    );
  } else if (nColaPrev >= 1 && esGenDia) {
    confParts.push(
      `La ${hh} entra en tarde con día caliente y generoso — ya ${nColaPrev} cola(s) G>${COLA_UMBRAL} hoy.`
    );
  } else if (nColaPrev >= 1) {
    confParts.push(
      `La ${hh} sigue un día caliente — ${nColaPrev} hora(s) ya cerraron con cola G>${COLA_UMBRAL}.`
    );
  } else if (esGenDia) {
    confParts.push(`La ${hh} en un día generoso (≥25% horas fuertes en cinta).`);
  } else if (nGenPrev >= 2) {
    confParts.push(
      `La ${hh} con tanda viva — ${nGenPrev} horas generosas ya cerraron hoy.`
    );
  } else {
    confParts.push(`La ${hh} muestra olor de cola G suelta según el perfil en curso.`);
  }

  confParts.push(
    "El patrón encaja con horas que suelen cerrar con una G grande sin haberla visto aún."
  );

  if (anterior) {
    confParts.push(`Ahora: ${textoAnterior(anterior).replace(/\.$/, "")}.`);
  }

  return confParts.join(" ");
}

/**
 * Lectura narrativa para modal Cola — horas reales del día + expectativa.
 */
export function buildColaLectura({ brillo = null, cintaLineas = [] } = {}) {
  if (!brillo?.tag) return null;
  const tips = brillo.tipsColaG || [];
  const pill = colaGTagLive(tips);
  if (!pill) return null;

  const meta = parseTag(brillo.tag);
  const hod = brillo.hod ?? meta?.hora ?? 0;
  const T = brillo.T ?? 0;
  const acum = brillo.acum ?? 0;
  const nG = brillo.nG ?? 0;
  const meanG = brillo.meanG;
  const maxG = brillo.maxG;

  const hsDia = horasDelDia(brillo.tag, cintaLineas);
  const hsPrev = hsDia.filter((h) => h.hod < hod).sort((a, b) => a.hod - b.hod);
  const esGenDia = diaGeneroso(hsDia);
  const nColaPrev = hsPrev.filter((h) => h.cola500).length;
  const nGenPrev = hsPrev.filter((h) => h.generosa).length;
  const anterior = hsPrev.length ? hsPrev[hsPrev.length - 1] : null;

  const ctx = { hod, T, nColaPrev, nG, meanG, acum, maxG };
  const ventana = ventanaEspera(T, pill);
  const ventanaLista = Array.isArray(ventana) ? ventana : [ventana];
  const alertTips = tips.filter((t) => t.alerta || t.tono === "confirmada");
  const esperaTips = alertTips.map((t) => esperaDesdeTip(t, ctx));

  const tone = pill === "Cola · activa" ? "activa" : "olor";
  const fingerprint = [brillo.tag, pill, T, nG, maxG, nColaPrev].join("|");

  return {
    ok: true,
    pill,
    tone,
    tag: brillo.tag,
    hod,
    T,
    lead: buildLead({
      pill,
      hod,
      T,
      acum,
      nG,
      meanG,
      maxG,
      esGenDia,
      nColaPrev,
      nGenPrev,
      anterior,
    }),
    pasadas: hsPrev.map((h) => ({
      hod: h.hod,
      tag: h.tag,
      linea: filaHoraCinta(h),
      cola: h.cola500,
      generosa: h.generosa,
    })),
    anterior: anterior
      ? {
          hod: anterior.hod,
          tag: anterior.tag,
          texto: textoAnterior(anterior),
          cola: anterior.cola500,
          generosa: anterior.generosa,
          sumG: anterior.sumG,
          maxG: anterior.maxG,
        }
      : null,
    enCurso: {
      hod,
      tag: brillo.tag,
      minuto: T,
      acum,
      nG,
      meanG,
      maxG,
      sinCola: maxG == null || maxG < COLA_UMBRAL,
      linea: `${fmtHod(hod)} · min ${String(T).padStart(2, "0")}: ${acum} lm · ${nG} G${
        meanG != null ? ` · media ~${meanG} lm` : ""
      }${maxG != null ? ` · max G ${maxG}` : ""}${
        maxG != null && maxG >= COLA_UMBRAL ? " — cola presente" : " — sin G>500"
      }`,
    },
    espera: [...new Set([...ventanaLista, ...esperaTips])].filter(Boolean),
    diaGeneroso: esGenDia,
    nColaPrev,
    fingerprint,
  };
}
