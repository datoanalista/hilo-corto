/**
 * Costuras hora→hora mismo día — INFO decisión.
 * h14→h15 lab-h15 · h08→h09 lab-h678 · h15→h16 lab-costura.
 */
import { parseTag } from "./live.js";
import { refuerzoAperturaCostura1415 } from "./intraHoraInfo.js";
import { GEN_SUM_OPACO, horasDeLineasCached } from "./generosidadInfo.js";

export const COSTURA_SUM_FUERTE = 850;

/** @typedef {"opaco"|"normal"|"fuerte"|"en_curso"} CosturaBanda */

const PAIRS = [
  {
    id: "14-15",
    from: 14,
    to: 15,
    lab: "lab-h15",
    nTrain: 33,
    lift: { opaco: 345, normal: 212, fuerte: -183 },
    tituloDecision: "Costura h14→h15 · decisión",
    tituloPreview: "Costura → h15",
  },
  {
    id: "8-9",
    from: 8,
    to: 9,
    lab: "lab-h678",
    nTrain: 33,
    lift: { opaco: 314, normal: -27, fuerte: -679 },
    tituloDecision: "Costura h08→h09 · aviso",
    tituloPreview: "Costura → h09",
  },
  {
    id: "15-16",
    from: 15,
    to: 16,
    lab: "lab-costura",
    nTrain: 34,
    lift: { opaco: 220, normal: -88, fuerte: -780 },
    tituloDecision: "Costura h15→h16 · aviso",
    tituloPreview: "Costura → h16",
  },
];

function tagHodSameDay(tag, hod) {
  const t = parseTag(tag);
  if (!t) return null;
  const dd = String(t.dia).padStart(2, "0");
  const mm = String(t.mes).padStart(2, "0");
  const yy = String(t.anio).slice(-2);
  return `h${hod}-${dd}${mm}${yy}`;
}

/** Clasifica cierre (o parcial en vivo). */
export function clasificarCostura({
  sumG = null,
  meanG = null,
  enCurso = false,
  T = 0,
} = {}) {
  if (sumG != null && sumG >= COSTURA_SUM_FUERTE) return "fuerte";
  if (sumG != null && sumG < GEN_SUM_OPACO) return "opaco";
  if (meanG != null && meanG < 42) return "opaco";
  if (enCurso) {
    if (T >= 20 && meanG != null && meanG >= 74) return "fuerte";
    if (T >= 20 && ((sumG != null && sumG < 380) || (meanG != null && meanG <= 48))) {
      return "opaco";
    }
    return "en_curso";
  }
  return "normal";
}

/** @deprecated alias lab-h15 */
export const clasificarH14 = clasificarCostura;

function labelBanda(banda) {
  if (banda === "opaco") return "opaca";
  if (banda === "fuerte") return "fuerte";
  if (banda === "en_curso") return "en curso";
  return "normal";
}

function expectativa(pair, banda) {
  if (pair.id === "14-15") {
    switch (banda) {
      case "opaco":
        return {
          id: "rebote",
          fuerte: true,
          alerta: false,
          tono: "brill",
          titulo: "h15 suele venir fuerte",
          decision:
            "h14 cerró opaca — en cinta h15 rebota (+345 mediana). Favorecer hora fuerte.",
          detalle: "VIVE lab-h15: valle h14 → pico h15.",
        };
      case "normal":
        return {
          id: "sube",
          fuerte: true,
          alerta: false,
          tono: "brill",
          titulo: "h15 suele subir",
          decision:
            "h14 normal — h15 sube +212 mediana. Favorecer por encima del histórico (~733).",
          detalle: "Rebote moderado estable en train.",
        };
      case "fuerte":
        return {
          id: "techo",
          fuerte: false,
          alerta: true,
          tono: "alerta",
          titulo: "AVISO · h15 no suele seguir fuerte",
          decision:
            "h14 cerró fuerte — h15 baja -183 mediana. No asumir segunda hora fuerte seguida.",
          detalle: "Techo/regresión tras pico en h14.",
        };
      case "en_curso":
        return {
          id: "pendiente",
          fuerte: null,
          alerta: false,
          tono: "mute",
          titulo: "Costura h14→h15 en juego",
          decision:
            "h14 en curso — opaca favorece h15 fuerte; fuerte → cautela en h15.",
          detalle: "Mirá cierre h14 antes de decidir h15.",
        };
      default:
        return null;
    }
  }

  if (pair.id === "8-9") {
    switch (banda) {
      case "opaco":
        return {
          id: "rebote",
          fuerte: true,
          alerta: false,
          tono: "brill",
          titulo: "h09 puede rebote",
          decision:
            "h08 cerró opaca — h09 suele normalizar (+314 mediana). No arrastrar opaco de h08.",
          detalle: "OLOR lab-h678: rebote post-h08 opaco.",
        };
      case "normal":
        return {
          id: "plano",
          fuerte: null,
          alerta: false,
          tono: "mute",
          titulo: "h09 en banda normal",
          decision:
            "h08 normal — h09 plano (-27 mediana). Sin sesgo fuerte de costura.",
          detalle: "Bloque mañana: sin empuje claro h08→h09.",
        };
      case "fuerte":
        return {
          id: "techo",
          fuerte: false,
          alerta: true,
          tono: "alerta",
          titulo: "AVISO · h09 probablemente baja",
          decision:
            "h08 cerró fuerte — h09 cae -679 mediana. No asumir continuidad del pico matutino.",
          detalle: "VIVE lab-h678: h08 pico → h09 regresión (espejo inverso h14→h15).",
        };
      case "en_curso":
        return {
          id: "pendiente",
          fuerte: null,
          alerta: false,
          tono: "mute",
          titulo: "Costura h08→h09 en juego",
          decision:
            "h08 en curso — si cierra fuerte, AVISO en h09 (techo); opaca → rebote posible.",
          detalle: "Vigilá cierre h08: fuerte = cautela fuerte en h09.",
        };
      default:
        return null;
    }
  }

  if (pair.id === "15-16") {
    switch (banda) {
      case "opaco":
        return {
          id: "rebote",
          fuerte: true,
          alerta: false,
          tono: "brill",
          titulo: "h16 puede rebote",
          decision:
            "h15 cerró opaca — h16 suele normalizar (+220 mediana). No arrastrar opaco de h15.",
          detalle: "OLOR lab-costura: tras h15 débil, h16 compensa.",
        };
      case "normal":
        return {
          id: "plano",
          fuerte: null,
          alerta: false,
          tono: "mute",
          titulo: "h16 en banda normal",
          decision:
            "h15 normal — h16 plano (-88 mediana). Sin empuje fuerte de costura.",
          detalle: "Mediodía: h16 no hereda pico de h15.",
        };
      case "fuerte":
        return {
          id: "techo",
          fuerte: false,
          alerta: true,
          tono: "alerta",
          titulo: "AVISO · h16 probablemente baja",
          decision:
            "h15 cerró fuerte — h16 cae -780 mediana. No asumir continuidad tras el pico de h15.",
          detalle: "OLOR lab-costura: cierra ciclo h14→h15→h16 (rebote luego techo).",
        };
      case "en_curso":
        return {
          id: "pendiente",
          fuerte: null,
          alerta: false,
          tono: "mute",
          titulo: "Costura h15→h16 en juego",
          decision:
            "h15 en curso — si cierra fuerte, AVISO en h16 (techo); opaca → rebote posible en h16.",
          detalle: "Vigilá cierre h15: fuerte = cautela fuerte en h16.",
        };
      default:
        return null;
    }
  }

  return null;
}

function statsOrigenCerrada(horas, tagDestino, fromHod) {
  const tagFrom = tagHodSameDay(tagDestino, fromHod);
  if (!tagFrom) return null;
  const row = horas.find((h) => h.tag === tagFrom.toLowerCase()) || null;
  if (!row) return null;
  const banda = clasificarCostura({ sumG: row.sumG, meanG: row.meanG, enCurso: false });
  return {
    hod: fromHod,
    tag: tagFrom,
    sumG: row.sumG,
    meanG: row.meanG,
    banda,
    bandaLabel: labelBanda(banda),
    enCurso: false,
  };
}

function buildOneCostura(pair, { tag, hod, horas, lineas = [], acum, meanG, T }) {
  const h = Number(hod);
  if (h !== pair.from && h !== pair.to) return null;

  let origen = null;
  if (h === pair.to) {
    origen = statsOrigenCerrada(horas, tag, pair.from);
    if (!origen) {
      return {
        ok: false,
        pairId: pair.id,
        fromHod: pair.from,
        toHod: pair.to,
        modo: `h${pair.to}`,
        titulo: pair.tituloDecision,
        lineas: [
          `Sin dato de h${pair.from} mismo día — no se lee la costura h${pair.from}→h${pair.to}.`,
          `Cuando h${pair.from} cierre, volvé a abrir Brillo en h${pair.to}.`,
        ],
        tono: "mute",
        alerta: false,
      };
    }
  } else {
    const banda = clasificarCostura({
      sumG: acum > 0 ? acum : null,
      meanG,
      enCurso: true,
      T,
    });
    origen = {
      hod: pair.from,
      tag: tag.toLowerCase(),
      sumG: acum > 0 ? Math.round(acum) : null,
      meanG,
      banda,
      bandaLabel: labelBanda(banda),
      enCurso: banda === "en_curso" || T < 59,
    };
  }

  const exp =
    origen.banda === "en_curso"
      ? expectativa(pair, "en_curso")
      : expectativa(pair, origen.banda);
  if (!exp) return null;

  const lift = pair.lift[origen.banda] ?? null;
  const fromLabel = `h${String(pair.from).padStart(2, "0")}`;
  const origenTxt =
    origen.sumG != null
      ? `${origen.sumG} lumen${origen.meanG != null ? ` · ~${Math.round(origen.meanG)} lumen/G` : ""}`
      : origen.meanG != null
        ? `~${Math.round(origen.meanG)} lumen/G (parcial min ${T})`
        : "sin lectura aún";

  const lineasOut = [
    `${fromLabel} ${origen.enCurso ? "va" : "cerró"} ${origen.bandaLabel} (${origenTxt}).`,
    exp.decision,
  ];
  if (lift != null && origen.banda !== "en_curso") {
    lineasOut.push(
      `Train: lift h${pair.to} vs h${pair.from} ${lift >= 0 ? "+" : ""}${lift} mediana (${pair.lab} · n=${pair.nTrain}).`
    );
  }

  let detalle = exp.detalle;
  if (pair.id === "14-15" && h === pair.to && lineas.length) {
    const ref = refuerzoAperturaCostura1415({
      lineas,
      tagOrigen: origen.tag,
      enCurso: false,
    });
    if (ref?.linea) lineasOut.push(ref.linea);
    if (ref?.detalle) detalle = `${exp.detalle} · ${ref.detalle}`;
  }

  return {
    ok: true,
    pairId: pair.id,
    fromHod: pair.from,
    toHod: pair.to,
    modo: h === pair.to ? `h${pair.to}` : `h${pair.from}`,
    titulo: h === pair.to ? pair.tituloDecision : pair.tituloPreview,
    origen,
    h14: origen,
    expectativa: exp,
    lift,
    lineas: lineasOut,
    detalle,
    tono: exp.tono,
    alerta: Boolean(exp.alerta),
    fingerprint: [pair.id, tag, origen.banda, origen.sumG ?? "-", exp.id].join("|"),
  };
}

/**
 * Todas las costuras aplicables a la hora viva.
 */
export function buildCosturasLectura({
  tag = "",
  hod = 0,
  lineas = [],
  acum = 0,
  meanG = null,
  nG = 0,
  T = 0,
} = {}) {
  const horas = lineas.length ? horasDeLineasCached(lineas) : [];
  const out = [];
  for (const pair of PAIRS) {
    const c = buildOneCostura(pair, { tag, hod, horas, lineas, acum, meanG, T });
    if (c) out.push(c);
  }
  return out;
}

/** Primera costura o la que tiene AVISO. */
export function buildCosturaLectura(opts = {}) {
  const all = buildCosturasLectura(opts);
  return all.find((c) => c.alerta) || all[0] || null;
}

/** Tooltip compacto — prioriza AVISO. */
export function costuraTooltipLine(costuras) {
  const list = Array.isArray(costuras) ? costuras : costuras ? [costuras] : [];
  const c = list.find((x) => x.alerta && x.ok) || list.find((x) => x.ok);
  if (!c?.ok) return null;
  const from = `h${String(c.fromHod).padStart(2, "0")}`;
  return `${c.alerta ? "AVISO " : ""}Costura: ${from} ${c.origen?.bandaLabel} → ${c.expectativa?.titulo || ""}`;
}
