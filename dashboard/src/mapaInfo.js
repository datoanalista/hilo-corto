/**
 * Mapa hod × franja — foto train cinta (~870 h · 37 d).
 * Solo lectura; overlay live desde buildBrilloLectura.
 */

export const MAPA_TRAIN_H = 870;

export const FRANJAS = [
  { id: "madrugada", label: "Madrugada", hrs: [0, 1, 2, 3, 4, 5] },
  { id: "manana", label: "Mañana", hrs: [6, 7, 8, 9, 10, 11] },
  { id: "mediodia", label: "Mediodía", hrs: [12, 13, 14, 15, 16, 17] },
  { id: "noche", label: "Noche", hrs: [18, 19, 20, 21, 22, 23] },
];

/** med sum · P_gen · P_op · moda banda · n muestras */
export const MAPA_HOD = {
  0: { med: 566, pGen: 22, pOp: 33, moda: "muy_apag", n: 36 },
  1: { med: 532, pGen: 14, pOp: 34, moda: "muy_apag", n: 35 },
  2: { med: 630, pGen: 28, pOp: 31, moda: "muy_apag", n: 36 },
  3: { med: 609, pGen: 14, pOp: 25, moda: "normal", n: 36 },
  4: { med: 584, pGen: 17, pOp: 28, moda: "normal", n: 36 },
  5: { med: 599, pGen: 14, pOp: 17, moda: "normal", n: 35 },
  6: { med: 659, pGen: 14, pOp: 19, moda: "normal", n: 36 },
  7: { med: 658, pGen: 25, pOp: 33, moda: "muy_apag", n: 36 },
  8: { med: 661, pGen: 25, pOp: 17, moda: "normal", n: 36 },
  9: { med: 560, pGen: 17, pOp: 19, moda: "opaco", n: 36 },
  10: { med: 582, pGen: 27, pOp: 27, moda: "opaco", n: 37 },
  11: { med: 516, pGen: 17, pOp: 33, moda: "opaco", n: 36 },
  12: { med: 525, pGen: 16, pOp: 35, moda: "muy_apag", n: 37 },
  13: { med: 558, pGen: 14, pOp: 30, moda: "opaco", n: 37 },
  14: { med: 492, pGen: 22, pOp: 44, moda: "muy_apag", n: 36 },
  15: { med: 733, pGen: 30, pOp: 19, moda: "normal", n: 37 },
  16: { med: 554, pGen: 11, pOp: 27, moda: "normal", n: 37 },
  17: { med: 618, pGen: 24, pOp: 35, moda: "muy_apag", n: 37 },
  18: { med: 535, pGen: 16, pOp: 43, moda: "muy_apag", n: 37 },
  19: { med: 606, pGen: 22, pOp: 30, moda: "normal", n: 37 },
  20: { med: 546, pGen: 22, pOp: 47, moda: "muy_apag", n: 36 },
  21: { med: 612, pGen: 8, pOp: 25, moda: "normal", n: 36 },
  22: { med: 629, pGen: 22, pOp: 25, moda: "normal", n: 36 },
  23: { med: 536, pGen: 8, pOp: 28, moda: "opaco", n: 36 },
};

/** % horas por banda dentro de cada franja */
export const MAPA_FRANJA = {
  madrugada: {
    med: 594,
    pGen: 18,
    bandas: { muy_apag: 28, opaco: 24, normal: 30, fuerte: 13, muy_fuerte: 5, sn: 1 },
    deltaBrill: 133,
  },
  manana: {
    med: 595,
    pGen: 21,
    bandas: { muy_apag: 25, opaco: 26, normal: 29, fuerte: 13, muy_fuerte: 6, sn: 1 },
    deltaBrill: 27,
  },
  mediodia: {
    med: 583,
    pGen: 19,
    bandas: { muy_apag: 32, opaco: 19, normal: 30, fuerte: 11, muy_fuerte: 6, sn: 2 },
    deltaBrill: 160,
  },
  noche: {
    med: 586,
    pGen: 17,
    bandas: { muy_apag: 33, opaco: 19, normal: 32, fuerte: 10, muy_fuerte: 6, sn: 1 },
    deltaBrill: 18,
  },
};

export const MAPA_OLOR_HOD = [8, 14, 15, 19];

const MODA_LABEL = {
  muy_apag: "muy apagado",
  opaco: "opaco",
  normal: "normal",
  fuerte: "fuerte",
  muy_fuerte: "muy fuerte",
  sn: "supernova",
};

const BANDA_STACK = [
  { id: "muy_apag", cls: "mapa-band-apag" },
  { id: "opaco", cls: "mapa-band-opaco" },
  { id: "normal", cls: "mapa-band-norm" },
  { id: "fuerte", cls: "mapa-band-fuerte" },
  { id: "muy_fuerte", cls: "mapa-band-mf" },
  { id: "sn", cls: "mapa-band-sn" },
];

function franjaDe(hod) {
  for (const f of FRANJAS) {
    if (f.hrs.includes(hod)) return f;
  }
  return FRANJAS[0];
}

function deltaTexto(acum, hist) {
  if (acum == null || hist == null) return null;
  const d = acum - hist;
  if (Math.abs(d) < 25) return "cerca del histórico";
  return d > 0 ? `+${d} vs med hist` : `${d} vs med hist`;
}

/**
 * @param {object} opts
 * @param {number} [opts.hod=0]
 * @param {number} [opts.acum]
 * @param {number} [opts.T=0]
 * @param {string} [opts.bandaTotal]
 */
export function buildMapaLectura({ hod = 0, acum = null, T = 0, bandaTotal = null } = {}) {
  const h = Math.max(0, Math.min(23, Number(hod) || 0));
  const celda = MAPA_HOD[h] || MAPA_HOD[0];
  const franja = franjaDe(h);
  const frStats = MAPA_FRANJA[franja.id] || MAPA_FRANJA.madrugada;

  const celdas = [];
  for (const f of FRANJAS) {
    for (const hr of f.hrs) {
      const row = MAPA_HOD[hr];
      celdas.push({
        hod: hr,
        franja: f.id,
        ...row,
        modaLabel: MODA_LABEL[row.moda] || row.moda,
        olor: MAPA_OLOR_HOD.includes(hr),
        actual: hr === h,
      });
    }
  }

  const enCurso = T < 59 && acum != null && acum > 0;
  const comparacion =
    acum != null
      ? {
          acum,
          histMed: celda.med,
          delta: acum - celda.med,
          texto: enCurso
            ? `${deltaTexto(acum, celda.med) || "—"} · hora en curso`
            : deltaTexto(acum, celda.med),
        }
      : null;

  const franjaStack = BANDA_STACK.map((b) => ({
    id: b.id,
    cls: b.cls,
    pct: frStats.bandas[b.id] ?? 0,
  }));

  return {
    trainH: MAPA_TRAIN_H,
    hod: h,
    franja: {
      id: franja.id,
      label: franja.label,
      med: frStats.med,
      pGen: frStats.pGen,
      deltaBrill: frStats.deltaBrill,
      stack: franjaStack,
    },
    celda: {
      hod: h,
      med: celda.med,
      pGen: celda.pGen,
      pOp: celda.pOp,
      moda: MODA_LABEL[celda.moda] || celda.moda,
      olor: MAPA_OLOR_HOD.includes(h),
    },
    celdas,
    comparacion,
    bandaLive: bandaTotal,
    leyenda: { minMed: 480, maxMed: 760 },
  };
}
