/**
 * Intra-hora INFO — apertura vs cola (lab-intra-hora 2026-08-29).
 * sin G min 0-9 → sum ~474 vs ~604 · h14 sin apertura → h15 +345.
 */
import { parseTiro } from "./live.js";

const APERTURA_MAX = 9;
const TIP_MIN = 10;

/** Tiros nucleo de una hora cerrada en cinta. */
export function tirosDeHoraEnLineas(lineas = [], tag = "") {
  const t = (tag || "").trim().toLowerCase();
  if (!t || !lineas.length) return [];
  const out = [];
  let i = 0;
  while (i < lineas.length) {
    const row = (lineas[i] || "").trim();
    if (row.toLowerCase() === t) {
      i += 1;
      while (i < lineas.length) {
        const s = (lineas[i] || "").trim();
        if (!s) {
          i += 1;
          continue;
        }
        if (/^h\d{1,2}-\d{6}$/i.test(s)) break;
        const tr = parseTiro(s);
        if (tr) out.push(tr);
        i += 1;
      }
      break;
    }
    i += 1;
  }
  return out;
}

function gsDeTiros(tiros = [], maxMin = null) {
  let gs = (tiros || []).filter(
    (t) => t && String(t.color || "").toUpperCase().startsWith("G") && t.lumen != null
  );
  if (maxMin != null) {
    gs = gs.filter((t) => t.m0 <= maxMin);
  }
  return gs;
}

/**
 * Perfil apertura de la hora (live o cerrada).
 */
export function perfilAperturaHora({
  tiros = [],
  lineas = [],
  tag = "",
  T = 59,
  enCurso = false,
} = {}) {
  let src = tiros;
  if (!src.length && lineas.length && tag) {
    src = tirosDeHoraEnLineas(lineas, tag);
    enCurso = false;
  }
  const maxMin = enCurso ? Math.min(59, Math.max(0, T)) : 59;
  const gs = gsDeTiros(enCurso ? src.filter((t) => t.m0 <= maxMin) : src);
  if (!gs.length) {
    return {
      sinG: true,
      sinEarly: true,
      nG: 0,
      firstM: null,
      nEarly: 0,
    };
  }
  const early = gs.filter((t) => t.m0 <= APERTURA_MAX);
  return {
    sinG: false,
    sinEarly: early.length === 0,
    nG: gs.length,
    nEarly: early.length,
    firstM: Math.min(...gs.map((t) => t.m0)),
  };
}

const FLACA_BLOQUE_MAX = 19;

/** Tips apertura en Brillo (live @min>=10). */
export function buildIntraHoraTips({ tiros = [], minuto = 0, nG = 0 } = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  if (T < TIP_MIN) return [];

  const perfil = perfilAperturaHora({ tiros, T, enCurso: true });
  const tips = [];
  const gs019 = gsDeTiros(
    (tiros || []).filter((t) => t.m0 <= T),
    FLACA_BLOQUE_MAX
  );

  // Lab hora flaca · señal @20
  if (T >= 20 && T <= 38 && gs019.length <= 1) {
    tips.push({
      id: "flaca-olor-20",
      texto:
        "Apertura muy flaca (≤1 G en 0–19) — olor opaca al cierre ~48% vs ~27% base (lab flaca). La hora aún puede despertar.",
      tono: "olor",
    });
  }

  if (perfil.sinG || nG === 0) {
    if (T < 20) {
      tips.push({
        id: "sin-g-apertura",
        texto:
          "Sin G en apertura (min 0–10): olor hora opaca o débil — en cinta cierran ~474 lumen vs ~604 cuando sí hay G temprano. El 1er G puede ser cola del L anterior (min 0–3).",
      });
    }
    return tips;
  }

  if (perfil.sinEarly && T < 20) {
    tips.push({
      id: "g-tardia-apertura",
      texto: `Sin G en min 0–9 (1er G min ${perfil.firstM}): apertura tardía — olor suma más baja. Si cierra opaca, mirá costura con la hora siguiente.`,
    });
  }

  return tips;
}

/** Refuerzo costura h14→h15 cuando h14 sin G apertura. */
export function refuerzoAperturaCostura1415({
  lineas = [],
  tiros = [],
  tagOrigen = "",
  enCurso = false,
  T = 0,
} = {}) {
  const perfil = perfilAperturaHora({
    tiros: enCurso ? tiros : [],
    lineas: enCurso ? [] : lineas,
    tag: tagOrigen,
    T,
    enCurso,
  });
  if (!perfil?.sinEarly) return null;
  const extra =
    perfil.sinG || perfil.firstM == null
      ? ""
      : ` (1er G min ${perfil.firstM})`;
  return {
    linea: `Apertura h14: sin G en min 0–9${extra} — rebote h15 más marcado en cinta (+345 vs +128 cuando h14 sí abre temprano).`,
    detalle: "lab-intra-hora H5 · OLOR apertura refuerza costura.",
  };
}
