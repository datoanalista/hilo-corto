/**
 * Gesto entre G — este hueco (contador) + esperado al cerrar.
 * Esperado ≠ preciso. No mueve el tip LC-01.
 * Extra (tipo 5) no sienta ancla.
 */

const NOMBRE = {
  T: "tren",
  C: "casi",
  k: "corto",
  m: "medio",
  L: "cola",
  S: "sequía",
};

const RANGO = {
  T: "0 R",
  C: "1 R",
  k: "2–4 R",
  m: "5–8 R",
  L: "9–15 R",
  S: "16+ R",
};

const TONO = {
  T: "tren",
  C: "casi",
  k: "corto",
  m: "medio",
  L: "este-largo",
  S: "este-largo",
};

export function atomDeR(k) {
  const n = Number(k);
  if (!Number.isFinite(n) || n <= 0) return "T";
  if (n === 1) return "C";
  if (n <= 4) return "k";
  if (n <= 8) return "m";
  if (n <= 15) return "L";
  return "S";
}

function esNucleo(t) {
  if (!t) return false;
  if (!String(t.color || "").toUpperCase().startsWith("G")) return false;
  return Number(t.tipo) !== 5;
}

function etiqueta(atom, r) {
  if (atom === "T") return `Gesto: 0 R`;
  return `Gesto: ${NOMBRE[atom]} ${r}`;
}

/**
 * @returns {null | {
 *   ok: true,
 *   pill: string,
 *   linea: string,
 *   tono: string,
 *   tooltip: string,
 *   fingerprint: string,
 * }}
 */
export function buildGestoEsperado({ tiros = [] } = {}) {
  const list = tiros || [];
  const gIdx = [];
  for (let i = 0; i < list.length; i += 1) {
    if (esNucleo(list[i])) gIdx.push(i);
  }
  if (!gIdx.length) return null;

  const cerrados = [];
  for (let i = 0; i < gIdx.length - 1; i += 1) {
    const r = gIdx[i + 1] - gIdx[i] - 1;
    cerrados.push({ r, atom: atomDeR(r) });
  }
  const lastG = gIdx[gIdx.length - 1];
  const abiertoR = list.length - lastG - 1;
  const abiertoAtom = atomDeR(abiertoR);
  const ultimo = cerrados.length ? cerrados[cerrados.length - 1] : null;
  const penult = cerrados.length >= 2 ? cerrados[cerrados.length - 2] : null;
  const ultimoLargo = ultimo && (ultimo.atom === "L" || ultimo.atom === "S");
  const dosColas = penult?.atom === "L" && ultimo?.atom === "L";
  const esteLargo = abiertoAtom === "L" || abiertoAtom === "S";

  const pill = etiqueta(abiertoAtom, abiertoR);
  const tono = TONO[abiertoAtom];

  const esteTxt = `Este hueco: ${NOMBRE[abiertoAtom]} · ${abiertoR} R (${RANGO[abiertoAtom]}).`;
  const ultTxt = ultimo
    ? `Último cerrado: ${NOMBRE[ultimo.atom]} (${ultimo.r} R).`
    : "Primera G de la hora. Aún no hay hueco cerrado.";
  let esperado = "Al cerrar, lo esperado del siguiente es corto (2–4 R). No es un minuto.";
  if (esteLargo) {
    esperado = `Este ya es ${NOMBRE[abiertoAtom]}. Al cerrar, lo esperado es corto (2–4 R), no otro ${NOMBRE[abiertoAtom]}.`;
  } else if (dosColas) {
    esperado = `Últimos dos fueron colas (${penult.r} R y ${ultimo.r} R). Al cerrar: esperado corto. No una tercera cola.`;
  } else if (ultimoLargo) {
    esperado = `El último fue ${NOMBRE[ultimo.atom]}. Al cerrar: esperado corto, no otra ${NOMBRE[ultimo.atom]}.`;
  }

  const linea = `${esteTxt} ${esperado}`;
  const tips = [
    "[Gesto · este hueco · no es tip]",
    `• ${esteTxt}`,
    `• ${ultTxt}`,
    `• ${esperado}`,
    "• El Next a veces se pasa si todavía cree que el hueco es largo.",
  ];
  if (abiertoR > 4) {
    tips.splice(
      4,
      0,
      `• Van más de 4 R: el badge sigue el tipo (medio / cola / sequía), no se queda en corto.`
    );
  }

  return {
    ok: true,
    pill,
    linea,
    tono,
    tooltip: tips.join("\n"),
    fingerprint: `${gIdx.length}|${ultimo?.atom || "-"}|${abiertoR}|${abiertoAtom}`,
  };
}
