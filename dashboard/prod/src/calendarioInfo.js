/**
 * Calendario INFO — DOW×tramo, costuras y eco (lab calendario-hod R3).
 * Solo lectura; no boleto · no chips.
 */
import { parseTag } from "./live.js";

export const DOW_ES = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"];
export const DOW_LABEL = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
export const TRAMOS = [
  { id: "man", label: "Mañana", hod: "0–7h" },
  { id: "tar", label: "Tarde", hod: "8–15h" },
  { id: "noc", label: "Noche", hod: "16–23h" },
];

/** Celdas con holdout OK o patrón acumulado (894h · R3). */
export const CALENDARIO_CELDAS = [
  {
    dow: 5,
    tramo: "noc",
    lift: -17,
    holdout: -11,
    veredicto: "ok",
    titulo: "Vie noche",
  },
  {
    dow: 6,
    tramo: "noc",
    lift: -11,
    holdout: -5,
    veredicto: "ok",
    titulo: "Sáb noche",
  },
  {
    dow: 5,
    tramo: "man",
    lift: -7,
    holdout: -22,
    veredicto: "ok",
    titulo: "Vie mañana",
  },
  {
    dow: 2,
    tramo: "man",
    lift: 14,
    holdout: null,
    veredicto: "acumular",
    titulo: "Mar mañana",
  },
  {
    dow: 5,
    tramo: "tar",
    lift: 15,
    holdout: -9,
    veredicto: "flip",
    titulo: "Vie tarde",
  },
];

export const CALENDARIO_COSTURAS = [
  {
    id: "14-15-vie-tar",
    from: 14,
    to: 15,
    dow: 5,
    tramo: "tar",
    titulo: "h14 op → h15 (vie tarde)",
    texto:
      "Si h14 cierra opaca el viernes por la tarde, h15 mismo día suele subir (~+18 mean_G en masa cinta). Olor h15, no ficha.",
    activoEn: [14, 15],
  },
  {
    id: "10-11-tar",
    from: 10,
    to: 11,
    tramo: "tar",
    dow: null,
    titulo: "h10 op → h11 (tarde)",
    texto:
      "Si h10 cierra opaca en tarde, h11 mismo día med ~+12 lumen/G. Descriptivo.",
    activoEn: [10, 11],
  },
];

export const CALENDARIO_ECO_RESUMEN = [
  {
    from: 10,
    to: [8],
    deltaD: 1,
    titulo: "h10 → h08 (+1d)",
    texto: "Origen muy fuerte en h10 deja eco hacia h08 del día siguiente (r≈0.79 train).",
  },
  {
    from: 17,
    to: [19, 14],
    deltaD: 1,
    titulo: "h17 → h19 / h14",
    texto: "Puente Eco estable (tips bodega). Confirmar con luz @20/@40.",
  },
  {
    from: 15,
    to: [19],
    deltaD: 1,
    titulo: "h15 → h19",
    texto: "Eco prioritario si h15 cierra muy fuerte.",
  },
  {
    from: 9,
    to: [10],
    deltaD: 0,
    titulo: "h09 → h10 (mismo día)",
    texto: "Eco intradía — mismo día.",
  },
  {
    from: 5,
    to: [15, 17],
    deltaD: 0,
    titulo: "h05 → h15 / h17",
    texto: "Doble destino mismo día si h05 muy fuerte.",
  },
];

export const CALENDARIO_H08 = {
  spread: 32.5,
  texto:
    "h08 modula mucho por día de semana (spread ~33). Vie/sáb altos, dom bajo. Par fuerte mismo día: h08↔h14 (r≈+0.55). h08↔h09 global débil; lun n=5 anecdótico.",
};

export function tramoDeHod(hod) {
  if (hod <= 7) return "man";
  if (hod <= 15) return "tar";
  return "noc";
}

export function dowDeTag(tag) {
  const t = parseTag(tag);
  if (!t) return null;
  return new Date(t.anio, t.mes - 1, t.dia).getDay();
}

function celdaMap() {
  const m = new Map();
  for (const c of CALENDARIO_CELDAS) {
    m.set(`${c.dow}:${c.tramo}`, c);
  }
  return m;
}

const CELDA_BY_KEY = celdaMap();

export function lookupCelda(dow, tramo) {
  return CELDA_BY_KEY.get(`${dow}:${tramo}`) || null;
}

function toneDeLift(lift, veredicto) {
  if (veredicto === "flip") return "mixto";
  if (lift == null) return "mute";
  if (lift <= -8) return "opaco";
  if (lift >= 8) return "brill";
  return "normal";
}

function lineaCelda(c) {
  if (!c) return null;
  const signo = c.lift > 0 ? "+" : "";
  const ho =
    c.holdout != null ? ` · holdout ${c.holdout > 0 ? "+" : ""}${c.holdout}%` : "";
  if (c.veredicto === "flip") {
    return `${c.titulo}: train ${signo}${c.lift}% pero holdout inestable — contexto, no ley.`;
  }
  if (c.veredicto === "acumular") {
    return `${c.titulo}: olor +${c.lift}% train — acumular más semanas.`;
  }
  return `${c.titulo}: mean_G ~${signo}${c.lift}% vs base (38d${ho}). Solo lectura.`;
}

/**
 * @param {{ reloj, tagHora, ecoLectura, brilloLectura }} opts
 */
export function buildCalendarioLectura({
  reloj,
  tagHora,
  ecoLectura = null,
  brilloLectura = null,
} = {}) {
  const tag = tagHora || reloj?.tag || "";
  const t = parseTag(tag);
  const hod = t?.hora ?? reloj?.hora ?? 0;
  const dow = dowDeTag(tag);
  const tramo = tramoDeHod(hod);
  const celda = dow != null ? lookupCelda(dow, tramo) : null;

  const grid = [];
  for (const tr of TRAMOS) {
    const fila = { tramo: tr.id, label: tr.label, hod: tr.hod, celdas: [] };
    for (let d = 0; d < 7; d += 1) {
      const c = lookupCelda(d, tr.id);
      const activo = d === dow && tr.id === tramo;
      fila.celdas.push({
        dow: d,
        dowLabel: DOW_LABEL[d],
        tramo: tr.id,
        activo,
        lift: c?.lift ?? null,
        veredicto: c?.veredicto ?? null,
        tone: c ? toneDeLift(c.lift, c.veredicto) : "vacio",
        titulo: c?.titulo ?? null,
      });
    }
    grid.push(fila);
  }

  const ahoraLineas = [];
  if (dow != null) {
    ahoraLineas.push(
      `${DOW_LABEL[dow]} · ${TRAMOS.find((x) => x.id === tramo)?.label || tramo} · h${String(hod).padStart(2, "0")}`
    );
  }
  if (celda) {
    const ln = lineaCelda(celda);
    if (ln) ahoraLineas.push(ln);
  } else if (dow != null) {
    ahoraLineas.push(
      "Sin patrón DOW×tramo fuerte cableado para este tramo — mirá la grilla."
    );
  }
  if (hod === 8) {
    ahoraLineas.push(CALENDARIO_H08.texto);
  }

  const costuras = CALENDARIO_COSTURAS.map((c) => ({
    ...c,
    activo:
      dow != null &&
      c.activoEn.includes(hod) &&
      (c.dow == null || c.dow === dow) &&
      (c.tramo == null || c.tramo === tramo),
    extra: "",
  }));
  for (const c of costuras) {
    if (!c.activo) continue;
    if (
      hod === 14 &&
      brilloLectura?.tone === "opaco" &&
      c.id === "14-15-vie-tar"
    ) {
      c.extra = " h14 opaca ahora — oler h15.";
    }
    if (hod === 15 && c.id === "14-15-vie-tar" && dow === 5) {
      c.extra = " Revisá cierre h14.";
    }
  }

  const ecos = CALENDARIO_ECO_RESUMEN.map((e) => ({
    ...e,
    activo: e.to.includes(hod) || e.from === hod,
    rol:
      e.from === hod
        ? e.deltaD === 1
          ? "origen"
          : "origen_hoy"
        : e.to.includes(hod)
          ? e.deltaD === 1
            ? "destino"
            : "destino_hoy"
          : null,
  }));

  if (ecoLectura?.lineas?.length && ecoLectura.modo !== "vacio") {
    ahoraLineas.push(`Eco live: ${ecoLectura.pill} — ${ecoLectura.lineas[0]}`);
  }

  const pill =
    celda && celda.veredicto === "ok"
      ? `${DOW_ES[dow]}/${celda.tramo} ${celda.lift > 0 ? "+" : ""}${celda.lift}%`
      : celda?.veredicto === "flip"
        ? `${DOW_ES[dow]}/${celda.tramo} ~`
        : "Cal";

  const tone = celda ? toneDeLift(celda.lift, celda.veredicto) : "mute";

  return {
    pill,
    tone,
    hod,
    dow,
    tramo,
    celda,
    ahoraLineas,
    grid,
    costuras,
    ecos,
    fingerprint: `${tag}:${dow}:${tramo}:${celda?.veredicto || "—"}`,
  };
}

export function calendarioTooltipTitle(lectura) {
  if (!lectura?.ahoraLineas?.length) return "Calendario INFO — DOW×tramo";
  return lectura.ahoraLineas.slice(0, 2).join(" · ");
}
