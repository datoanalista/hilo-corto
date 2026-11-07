/**
 * Eco INFO — puentes mean_G hora→hora (+1d).
 * Umbral origen: muy fuerte (≥85 lumen/G) desde @40.
 * Confirmación destino: @20 mean_G vs 48/74 · @40 vs 85 (misma escala Brillo).
 */
import { parseTag, parseTiro } from "./live.js";
import { MEAN_Q25, MEAN_Q75 } from "./brilloInfo.js";

export const ECO_MEAN_MIN = 85; // muy fuerte
export const ECO_MINUTO_MIN = 40;

/** Origen hod → destinos (+1 día). Los 9 tips. */
export const ECO_PUENTES = [
  { from: 17, to: [19, 14] },
  { from: 15, to: [19] },
  { from: 10, to: [8] },
  { from: 9, to: [10] },
  { from: 16, to: [11] },
  { from: 5, to: [15, 17] },
  { from: 11, to: [0] },
];

const STORAGE_KEY = "hilo-corto-eco-origenes-v1";

const PRIORIDAD_DEST = {
  "15-19": 1,
  "17-19": 1,
  "10-8": 2,
};

function pad(n) {
  return String(n).padStart(2, "0");
}

function tagDe(hod, dia, mes, anio) {
  return `h${hod}-${pad(dia)}${pad(mes)}${String(anio).slice(-2)}`;
}

function diaMas(t, deltaDias) {
  const d = new Date(t.anio, t.mes - 1, t.dia);
  d.setDate(d.getDate() + deltaDias);
  return {
    dia: d.getDate(),
    mes: d.getMonth() + 1,
    anio: d.getFullYear(),
  };
}

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

export function meanGDeTiros(tiros = []) {
  const gs = [];
  for (const t of tiros) {
    const color = (t.color || "").toUpperCase();
    if (!color.startsWith("G")) continue;
    const lm = lumenOf(t);
    if (lm == null || lm < 0) continue;
    gs.push(lm);
  }
  if (!gs.length) return { meanG: null, nG: 0, acumG: 0 };
  const acumG = gs.reduce((a, b) => a + b, 0);
  return { meanG: acumG / gs.length, nG: gs.length, acumG };
}

function tramosDeHora(lineas, tag) {
  if (!tag) return [];
  const needle = tag.trim().toLowerCase();
  const idx = (lineas || []).findIndex(
    (l) => (l || "").trim().toLowerCase() === needle
  );
  if (idx < 0) return [];
  const out = [];
  for (let i = idx + 1; i < lineas.length; i += 1) {
    const s = (lineas[i] || "").trim();
    if (!s) continue;
    if (/^h\d{1,2}-\d{6}$/i.test(s)) break;
    const tiro = parseTiro(s);
    if (tiro) out.push(tiro);
  }
  return out;
}

function leerStorage() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const j = JSON.parse(raw);
    return j && typeof j === "object" ? j : {};
  } catch {
    return {};
  }
}

function escribirStorage(map) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

/** Registra origen muy fuerte @40+ (idempotente). */
export function recordarOrigenEco(tag, meanG, nG, T) {
  if (!tag || meanG == null || nG < 2 || T < ECO_MINUTO_MIN) return;
  if (meanG < ECO_MEAN_MIN) return;
  const map = leerStorage();
  const prev = map[tag];
  if (prev && prev.meanG >= meanG) return;
  map[tag] = {
    meanG: Math.round(meanG * 10) / 10,
    nG,
    T,
    at: Date.now(),
  };
  // podar > 3 días
  const t = parseTag(tag);
  if (t) {
    const lim = diaMas(t, -3);
    for (const k of Object.keys(map)) {
      const p = parseTag(k);
      if (!p) {
        delete map[k];
        continue;
      }
      const dt = new Date(p.anio, p.mes - 1, p.dia);
      const dl = new Date(lim.anio, lim.mes - 1, lim.dia);
      if (dt < dl) delete map[k];
    }
  }
  escribirStorage(map);
}

function origenGuardado(tag, lineas) {
  const map = leerStorage();
  if (map[tag]) return map[tag];
  const tiros = tramosDeHora(lineas, tag);
  const { meanG, nG } = meanGDeTiros(tiros);
  if (meanG != null && nG >= 2 && meanG >= ECO_MEAN_MIN) {
    return { meanG, nG, T: 59, fromCinta: true };
  }
  return null;
}

function destinosDe(fromHod) {
  const out = [];
  for (const p of ECO_PUENTES) {
    if (p.from === fromHod) out.push(...p.to);
  }
  return [...new Set(out)];
}

function origenesHacia(toHod) {
  const out = [];
  for (const p of ECO_PUENTES) {
    if (p.to.includes(toHod)) out.push(p.from);
  }
  return [...new Set(out)];
}

function sortOrigenes(list, destHod) {
  return [...list].sort((a, b) => {
    const ka = `${a}-${destHod}`;
    const kb = `${b}-${destHod}`;
    return (PRIORIDAD_DEST[ka] || 9) - (PRIORIDAD_DEST[kb] || 9);
  });
}

function tirosHastaMin(tiros, maxMin) {
  return (tiros || []).filter((t) => t && t.m0 <= maxMin);
}

function lecturaEnMin(tiros, maxMin) {
  const { meanG, nG } = meanGDeTiros(tirosHastaMin(tiros, maxMin));
  return {
    meanG,
    nG,
    listo: meanG != null && nG >= 2,
  };
}

/** Qué comparar @20/@40 para confirmar (o desmentir) el eco en la hora destino. */
function lineasConfirmacionEco(tiros, T, origenMeanG) {
  const out = [];
  const ayer = origenMeanG != null ? Math.round(origenMeanG) : "—";
  const c20 = lecturaEnMin(tiros, 20);
  const c40 = lecturaEnMin(tiros, 40);

  function texto20() {
    if (!c20.listo) {
      return T >= 20
        ? "@20: todavía no hay 2 G — no se puede leer la tendencia temprana."
        : null;
    }
    const m = Math.round(c20.meanG);
    if (c20.meanG >= MEAN_Q75) {
      return `@20: cada G ~${m} lumen (≥${MEAN_Q75} fuerte) — el eco se ve bien en la apertura.`;
    }
    if (c20.meanG <= MEAN_Q25) {
      return `@20: cada G ~${m} lumen (≤${MEAN_Q25} opaco) — el olor de ayer (~${ayer}) no se refleja acá.`;
    }
    return `@20: cada G ~${m} lumen (banda normal ${MEAN_Q25}–${MEAN_Q75}) — eco posible pero sin confirmar.`;
  }

  function texto40() {
    if (!c40.listo) {
      return T >= 40
        ? "@40: todavía no hay 2 G — falta la lectura fuerte del medio de hora."
        : `@40 (pendiente): con 2+ G, confirmá si cada una trae ≥${ECO_MEAN_MIN} lumen (ayer ~${ayer}).`;
    }
    const m = Math.round(c40.meanG);
    if (c40.meanG >= ECO_MEAN_MIN) {
      return `@40: cada G ~${m} lumen (≥${ECO_MEAN_MIN} muy fuerte) — eco confirmado; la hora va luminosa como el origen de ayer.`;
    }
    if (c40.meanG >= MEAN_Q75) {
      return `@40: cada G ~${m} lumen (fuerte, pero <${ECO_MEAN_MIN}) — eco parcial; brillo alto pero no al nivel de ayer (~${ayer}).`;
    }
    if (c40.meanG <= MEAN_Q25) {
      return `@40: cada G ~${m} lumen (opaco) — eco no confirmado; el puente no se sostiene.`;
    }
    return `@40: cada G ~${m} lumen (normal) — eco débil; no cierra fuerte.`;
  }

  if (T < 20) {
    out.push(
      `Confirmación: @20 compará luz por G de esta hora — fuerte si ≥${MEAN_Q75}, opaca si ≤${MEAN_Q25}. @40: muy fuerte si ≥${ECO_MEAN_MIN} (como ayer ~${ayer} lumen/G).`
    );
    return out;
  }

  const l20 = texto20();
  if (l20) out.push(l20);

  if (T < 40) {
    out.push(texto40());
    return out;
  }

  out.push(texto40());
  return out;
}

/**
 * @param {{ tag, minuto, tiros, lineas }} opts
 */
export function buildEcoLectura({
  tag = "",
  minuto = 0,
  tiros = [],
  lineas = [],
} = {}) {
  const t = parseTag(tag);
  if (!t) {
    return {
      pill: "sin señal",
      lineas: ["Eco: sin hora viva."],
      tone: "mute",
      modo: "vacio",
      fingerprint: "empty",
    };
  }

  const T = Math.max(0, Math.min(59, Number(minuto) || 0));
  const { meanG, nG } = meanGDeTiros(tiros);
  const hod = t.hora;

  // persistir si somos origen @40+
  if (T >= ECO_MINUTO_MIN && meanG != null && nG >= 2 && meanG >= ECO_MEAN_MIN) {
    if (destinosDe(hod).length) {
      recordarOrigenEco(tag, meanG, nG, T);
    }
  }

  const ayer = diaMas(t, -1);
  const manana = diaMas(t, 1);

  // —— T2/T3: estamos en destino ——
  const froms = sortOrigenes(origenesHacia(hod), hod);
  const activos = [];
  for (const fh of froms) {
    const otag = tagDe(fh, ayer.dia, ayer.mes, ayer.anio);
    const o = origenGuardado(otag, lineas);
    if (o) activos.push({ hod: fh, tag: otag, ...o });
  }

  if (activos.length >= 2) {
    const hs = activos.map((a) => `h${pad(a.hod)}`).join(" y ");
    return {
      pill: `h${pad(hod)} (doble)`,
      lineas: [
        `Eco: dos horas de ayer llegaron a cada G muy fuerte (${hs}) y ambas apuntan olor hacia h${pad(hod)}.`,
        `El eco es más claro de lo usual. Confirmá con la luz de esta hora:`,
        ...lineasConfirmacionEco(
          tiros,
          T,
          Math.max(...activos.map((a) => a.meanG))
        ),
        `Solo lectura — no es boleto.`,
      ],
      tone: "brill",
      modo: "doble",
      fingerprint: `doble:${tag}:${activos.map((a) => a.tag).join(",")}:${T}`,
      activos,
    };
  }

  if (activos.length === 1) {
    const a = activos[0];
    return {
      pill: `activo desde h${pad(a.hod)}`,
      lineas: [
        `Eco: ayer a las ${pad(a.hod)}h cada G trajo luz muy alta (~${Math.round(a.meanG)} lumen por G).`,
        `Eso deja olor de brillo fuerte hacia esta hora (h${pad(hod)}). No garantiza el cierre — hay que ver si esta hora confirma la luz:`,
        ...lineasConfirmacionEco(tiros, T, a.meanG),
      ],
      tone: "brill",
      modo: "activo",
      fingerprint: `activo:${tag}:${a.tag}:${Math.round(a.meanG)}:${T}`,
      activos,
    };
  }

  // —— T1 / T7 / T4: somos origen ——
  const dests = destinosDe(hod);
  if (dests.length) {
    if (T < ECO_MINUTO_MIN) {
      return {
        pill: "esperando @40",
        lineas: [
          `Eco: el puente se lee desde el minuto 40, cuando cada G está en zona muy fuerte (≥85 lumen).`,
          `Todavía es pronto — si se confirma @40, anunciamos el eco hacia ${dests.map((d) => `h${pad(d)}`).join(" / ")}.`,
        ],
        tone: "mute",
        modo: "esperando",
        fingerprint: `esp:${tag}:${T}`,
        destinos: dests,
      };
    }

    if (nG < 2) {
      return {
        pill: "sin señal",
        lineas: [
          `Eco: hace falta al menos 2 G para leer si cada una trae luz muy alta.`,
          `Sin eso no hay eco hacia ${dests.map((d) => `h${pad(d)}`).join(" / ")}.`,
        ],
        tone: "mute",
        modo: "muestra",
        fingerprint: `ng:${tag}:${nG}`,
        destinos: dests,
      };
    }

    if (meanG >= ECO_MEAN_MIN) {
      if (dests.length >= 2) {
        const pillDoble = hod === 5 ? "tarde/noche" : `h${pad(dests[0])} · h${pad(dests[1])}`;
        return {
          pill: pillDoble,
          lineas: [
            `Eco: h${pad(hod)} ya muestra cada G muy luminosa (~${Math.round(meanG)} lumen por G, desde el minuto ${T}).`,
            `En la cinta eso suele dejar olor de brillo en h${pad(dests[0])} y h${pad(dests[1])} del día siguiente.`,
            `Mañana confirmar en esas horas: @20 ≥${MEAN_Q75} lumen/G (fuerte) · @40 ≥${ECO_MEAN_MIN} (muy fuerte).`,
            `Dos ventanas para mirar — ninguna es boleto.`,
          ],
          tone: "brill",
          modo: "emite-doble",
          fingerprint: `emi2:${tag}:${Math.round(meanG)}:${T}`,
          destinos: dests,
          meanG,
        };
      }
      const d0 = dests[0];
      const destTag = tagDe(d0, manana.dia, manana.mes, manana.anio);
      return {
        pill: `h${pad(d0)} olor fuerte`,
        lineas: [
          `Eco: esta hora ya muestra cada G muy luminosa (~${Math.round(meanG)} lumen por G, desde el minuto ${T}).`,
          `En la cinta, cuando pasa eso en h${pad(hod)}, la hora h${pad(d0)} del día siguiente suele venir más luminosa (olor — no es seguro).`,
          `Mañana en h${pad(d0)} confirmar: @20 ≥${MEAN_Q75} lumen/G · @40 ≥${ECO_MEAN_MIN} — eso validaría el eco.`,
          `Solo lectura — no es boleto.`,
        ],
        tone: "brill",
        modo: "emite",
        fingerprint: `emi:${tag}:${destTag}:${Math.round(meanG)}:${T}`,
        destinos: dests,
        meanG,
      };
    }

    // origen del mapa pero no muy fuerte
    return {
      pill: "sin señal",
      lineas: [
        `Eco: h${pad(hod)} puede dejar eco, pero hace falta cada G en zona muy fuerte (≥85 lumen) desde el minuto 40.`,
        `Ahora: ${nG} G · ~${meanG != null ? Math.round(meanG) : "—"} lumen por G. Seguimos con el brillo de esta hora.`,
      ],
      tone: "mute",
      modo: "bajo",
      fingerprint: `bajo:${tag}:${meanG == null ? "-" : Math.round(meanG)}:${T}`,
      destinos: dests,
    };
  }

  // —— T4 pendiente: hay origen reciente hacia un destino futuro hoy/mañana ——
  // Buscar en storage orígenes de AYER o HOY que apunten a destinos aún no llegados
  const map = leerStorage();
  const pendientes = [];
  for (const [otag, o] of Object.entries(map)) {
    const ot = parseTag(otag);
    if (!ot || o.meanG < ECO_MEAN_MIN) continue;
    for (const d of destinosDe(ot.hora)) {
      const destDia = diaMas(ot, 1);
      const destDate = new Date(destDia.anio, destDia.mes - 1, destDia.dia, d);
      const now = new Date(t.anio, t.mes - 1, t.dia, hod, T);
      if (destDate > now) {
        pendientes.push({ from: ot.hora, to: d, meanG: o.meanG });
      }
    }
  }
  pendientes.sort((a, b) => (PRIORIDAD_DEST[`${a.from}-${a.to}`] || 9) - (PRIORIDAD_DEST[`${b.from}-${b.to}`] || 9));
  if (pendientes.length) {
    const p = pendientes[0];
    return {
      pill: `pendiente h${pad(p.to)}`,
      lineas: [
        `Eco: h${pad(p.from)} ya estuvo en zona muy fuerte (~${Math.round(p.meanG)} lumen por G).`,
        `El puente apunta a h${pad(p.to)} (aún no llega). Queda anotado para entonces.`,
      ],
      tone: "brill",
      modo: "pendiente",
      fingerprint: `pend:${tag}:${p.from}-${p.to}`,
      pendientes,
    };
  }

  return {
    pill: "sin señal",
    lineas: [
      `Eco: no hay puente activo hacia esta hora.`,
      `El brillo de horas cercanas no dejó un eco claro para ahora. Seguimos con la lectura de brillo de esta hora.`,
    ],
    tone: "mute",
    modo: "sin",
    fingerprint: `sin:${tag}`,
  };
}
