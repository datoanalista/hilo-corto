/**
 * Perfil por bloques — lab-intra-hora 2026-08-31.
 * @20+: bloque 00-19 · @40+: suma 20-39 · actualiza con cada G.
 */
const B1_HI = 19;
const B2_LO = 20;
const B2_HI = 39;
const SHOW_MIN = 20;
const B2_DONE = 40;

const ACUM_BAJO = 250;
const ACUM_FUERTE = 550;
const MEAN_FUERTE = 75;
const PICO = 400;
const MEAN_FLOCO = 80;
const DENSO_N = 3;
const DENSO_MEAN = 70;

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function gsEnRango(tiros = [], lo, hi, T) {
  return (tiros || [])
    .filter(
      (t) =>
        t &&
        String(t.color || "").toUpperCase().startsWith("G") &&
        lumenOf(t) != null &&
        t.m0 >= lo &&
        t.m0 <= hi &&
        t.m0 <= T
    )
    .sort((a, b) => a.m0 - b.m0 || (a.s0 || 0) - (b.s0 || 0));
}

function stats(tiros, lo, hi, T) {
  const gs = gsEnRango(tiros, lo, hi, T);
  const lums = gs.map((t) => lumenOf(t));
  return {
    n: gs.length,
    sum: lums.reduce((a, b) => a + b, 0),
    mean: lums.length ? lums.reduce((a, b) => a + b, 0) / lums.length : null,
    max: lums.length ? Math.max(...lums) : 0,
    firstM: gs.length ? gs[0].m0 : null,
  };
}

function idPerfilB1(s) {
  if (s.n === 0) return "vacio";
  if (s.n === 1 && s.firstM >= 15) return "tarde";
  if (s.firstM >= 15 && s.n >= 2 && s.mean != null && s.mean < MEAN_FLOCO) return "tarde_flaco";
  if (s.firstM >= 15) return "tarde_mixto";
  if (s.firstM <= 9 && s.n >= DENSO_N && s.mean != null && s.mean >= DENSO_MEAN) return "denso";
  if (s.firstM <= 9) return "normal";
  return "mixto";
}

function idPerfilB2(b1, b2) {
  const acum = b1.sum + b2.sum;
  if (b2.n === 0) return "sin_2039";
  if (acum < ACUM_BAJO) return "flaca";
  if (acum >= ACUM_FUERTE && b2.mean != null && b2.mean >= MEAN_FUERTE) return "fuerte";
  if (b2.max >= PICO) return "pico";
  return "medio";
}

function copyB1(id, s) {
  switch (id) {
    case "vacio":
      return {
        titulo: "Bloque inicial vacío",
        paso: "Sin G en los primeros 20 min.",
        olor: "Olor opaco: la hora recién arranca en 20–39. En cinta ~6 de cada 10 cierran flojas.",
      };
    case "tarde":
      return {
        titulo: "Apertura tardía",
        paso: `Primera G al min ${s.firstM} · ${s.n} G en 00–19.`,
        olor: "Olor opaco: en cinta ~7 de cada 10 horas así cierran flojas. Puede despertar en 20–39.",
      };
    case "tarde_flaco":
      return {
        titulo: "Ráfaga tardía flaca",
        paso: `Primera G al min ${s.firstM} · ${s.n} G en 00–19 · luz baja (~${Math.round(s.mean)} lm).`,
        olor: "Olor contenido: pocas G y bajas. A veces suma en 20–39; pico grande es raro.",
      };
    case "tarde_mixto":
      return {
        titulo: "Apertura tardía",
        paso: `Primera G al min ${s.firstM} · ${s.n} G en 00–19.`,
        olor: "Olor mixto: arrancó tarde; mira cómo responde 20–39.",
      };
    case "denso":
      return {
        titulo: "Apertura densa",
        paso: `${s.n} G en 00–19 · arrancó temprano · buena luz (~${Math.round(s.mean)} lm).`,
        olor: "Olor fuerte: en cinta ~4 de cada 10 cierran generosas. Vigilar cola en 40–59.",
      };
    case "normal":
      return {
        titulo: "Apertura normal",
        paso: `${s.n} G en 00–19 · primera al min ${s.firstM}.`,
        olor: "Perfil habitual: el bloque 20–39 define el cierre.",
      };
    default:
      return {
        titulo: "Apertura mixta",
        paso: `${s.n} G en 00–19 · primera al min ${s.firstM}.`,
        olor: "Sin sesgo claro; mirá cómo cae 20–39.",
      };
  }
}

function copyB2(id, b1, b2) {
  const acum = b1.sum + b2.sum;
  switch (id) {
    case "sin_2039":
      return {
        tituloB2: "Sin actividad en 20–39",
        pasoB2: `Nada en 20–39 · acumulado bajo (~${acum} lm).`,
        olorB2: "Cierre probablemente flojo; poco que esperar en 40–59.",
      };
    case "flaca":
      return {
        tituloB2: "Hora flaca hasta ahora",
        pasoB2: `Pocas G y poca luz hasta el min 39 (~${acum} lm).`,
        olorB2: "Olor opaco al cierre. El tercer bloque suele sumar poco.",
      };
    case "pico":
      return {
        tituloB2: "Pico en 20–39",
        pasoB2: `Hubo una G fuerte en 20–39 (hasta ~${b2.max} lm).`,
        olorB2: "Olor de cola o repetición en 40–59; no asumir opaca.",
      };
    case "fuerte":
      return {
        tituloB2: "Hora fuerte hasta ahora",
        pasoB2: `Buena masa en 20–39 (~${b2.sum} lm · ~${Math.round(b2.mean)} lm/G).`,
        olorB2: "Olor de cierre vivo; posible G grande en 40–59.",
      };
    default:
      return {
        tituloB2: "Ritmo normal en 20–39",
        pasoB2: `Ritmo parejo en 20–39 (${b2.n} G · ~${b2.sum} lm).`,
        olorB2: "Cierre abierto: 40–59 decide si opaca, normal o fuerte.",
      };
  }
}

function tituloCombo(c1, c2) {
  const a = c1.titulo;
  const b = c2.tituloB2;
  if (c1.titulo === "Apertura tardía" && c2.tituloB2 === "Ritmo normal en 20–39") {
    return "Apertura tardía · despertó en 20–39";
  }
  if (c1.titulo === "Apertura tardía" && c2.tituloB2 === "Hora flaca hasta ahora") {
    return "Apertura tardía · hora flaca";
  }
  if (c1.titulo === "Apertura densa" && c2.tituloB2 === "Hora fuerte hasta ahora") {
    return "Apertura densa · hora fuerte";
  }
  return `${a} · ${b.toLowerCase()}`;
}

/**
 * @returns {null | { ok, parpadea, fase, titulo, lineas, fingerprint }}
 */
export function buildBloquePerfil({ tiros = [], minuto = 0 } = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  if (T < SHOW_MIN) return null;

  const b1 = stats(tiros, 0, B1_HI, Math.min(T, B1_HI));
  const b1Id = idPerfilB1(b1);
  const c1 = copyB1(b1Id, b1);
  const b2Parcial = T >= B2_LO && T < B2_DONE ? stats(tiros, B2_LO, B2_HI, T) : null;

  if (T < B2_DONE) {
    const lineas = [c1.paso, c1.olor];
    if (b2Parcial && b2Parcial.n > 0) {
      lineas.splice(
        1,
        0,
        `20–39 hasta ahora: ${b2Parcial.n} G · ~${b2Parcial.sum} lm.`
      );
    }
    return {
      ok: true,
      parpadea: true,
      fase: "bloque1",
      titulo: c1.titulo,
      lineas,
      fingerprint: `b1|${b1Id}|${b1.n}|${b1.sum}|${b2Parcial?.n ?? 0}|${b2Parcial?.sum ?? 0}`,
    };
  }

  const b2 = stats(tiros, B2_LO, B2_HI, Math.min(T, B2_HI));
  const b2Id = idPerfilB2(b1, b2);
  const c2 = copyB2(b2Id, b1, b2);
  const b3Parcial = stats(tiros, 40, 59, T);

  const lineas = [
    b1.n === 0
      ? "00–19: sin G."
      : `00–19: primera G al ${b1.firstM} · ${b1.n} G${b1.mean != null ? ` · ~${Math.round(b1.mean)} lm/G` : ""}.`,
    b2.n === 0
      ? `20–39: sin G · acumulado ~${b1.sum + b2.sum} lm.`
      : `20–39: ${b2.n} G · ~${b2.sum} lm (acum ~${b1.sum + b2.sum} lm).`,
    c2.olorB2,
  ];

  if (b3Parcial.n > 0) {
    lineas.splice(2, 0, `40–59 hasta ahora: ${b3Parcial.n} G · ~${b3Parcial.sum} lm.`);
  }

  return {
    ok: true,
    parpadea: false,
    fase: "bloque2",
    titulo: tituloCombo(c1, c2),
    lineas,
    fingerprint: `b12|${b1Id}|${b2Id}|${b1.n}|${b2.n}|${b1.sum}|${b2.sum}|${b3Parcial.n}|${b3Parcial.sum}|${T}`,
  };
}

export function bloquePerfilTooltip(lectura) {
  if (!lectura?.ok) return "";
  return [lectura.titulo, ...(lectura.lineas || [])].join("\n");
}
