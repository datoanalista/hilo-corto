/**
 * Oficio Piso — Urna / Pintor / Extra (dashboard).
 * Sordo a ciudad. Cero chips. Filas para Tips.
 */

function pad(m) {
  return String(m).padStart(2, "0");
}

/**
 * Une filas de ciudad + piso (capas sordas).
 * Piso va después de Faro/Lluvia cabecera, antes de orillas,
 * o al final si preferimos: al final de cabecera.
 */
export function fusionFilasTips(filasCiudad = [], filasPiso = []) {
  if (!filasPiso?.length) return filasCiudad || [];
  const ciudad = filasCiudad || [];
  const cabecera = [];
  const resto = [];
  for (const f of ciudad) {
    if (f.id === "sombra" || f.id === "faro" || f.id === "pronostico") {
      cabecera.push(f);
    } else resto.push(f);
  }
  // Orden fijo: recomendación → faro → lluvia → piso → resto
  const orden = { sombra: 0, faro: 1, pronostico: 2 };
  cabecera.sort((a, b) => (orden[a.id] ?? 9) - (orden[b.id] ?? 9));
  return [...cabecera, ...filasPiso, ...resto];
}

/** Texto corto para párrafo Habla (arranque). */
export function notaPiso(piso) {
  if (!piso?.ok) return null;
  const dom = piso.dominante || "—";
  const partes = [
    `Piso (tiro): dominan ${dom}. Se nombra; no elige minutos del boleto.`,
  ];
  if (piso.n_boost) {
    partes.push(
      `Si ves potenciador (${piso.n_boost}) → anotás; no agregues ficha.`
    );
  }
  if (piso.n_extra) {
    partes.push(
      `Si ves extra (${piso.n_extra}) → se nombra; no se sienta.`
    );
  }
  return partes.join(" ");
}

export async function pedirPiso(hora, T = null) {
  if (!hora) return null;
  const q = new URLSearchParams({ hora });
  if (T != null) q.set("T", String(T));
  const r = await fetch(`/api/piso?${q}`, { credentials: "include" });
  if (r.status === 401) return null;
  if (!r.ok) return null;
  return r.json();
}

export function padMin(m) {
  return pad(m);
}
