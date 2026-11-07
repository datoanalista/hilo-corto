import { paqueteTipsCiudad } from "./ciudad.js";

export function pad(m) {
  return String(m).padStart(2, "0");
}

/** Alias solo vista: Mesa-0…Mesa-5 (primera mayúscula). */
const ETIQUETA_ALIAS = {
  oficial: "Mesa-0",
  "beta-v1": "Mesa-1",
  "beta-v3": "Mesa-2",
  "beta-v4": "Mesa-3",
  "beta-v2": "Mesa-4",
  "beta-v5": "Mesa-5",
  "EJ-01": "Mesa-1",
  "EJ-02": "Mesa-2",
  "EJ-03": "Mesa-3",
  "EJ-01c": "Mesa-4",
  "EJ-05v2": "Mesa-5",
  OFICIAL: "Mesa-0",
  "BETA 01": "Mesa-1",
  "BETA 02": "Mesa-2",
  "BETA 03": "Mesa-3",
  "BETA 04": "Mesa-4",
  "BETA 05": "Mesa-5",
  "BETA 01-C": "Mesa-4",
  "BETA 05-V2": "Mesa-5",
  "lc-01": "Mesa-7",
  inter2: "Mesa-8",
  "live-rc": "Mesa-10",
  "pool-9": "Mesa-9",
  "oficial-classic": "Mesa-9",
  "POOL 9": "Mesa-9",
};

/** Fijo arriba en vista pools: Pool 7. El resto se ordena por score live. */
export const PINNED_POOL_IDS = ["lc-01", "live-rc"];

/** Pools que siguen en backend/lógica pero no se muestran en el tablero. */
export const UI_HIDDEN_POOL_IDS = ["live-rc", "inter2"];

/** Mismos minutos en el mismo orden. */
export function chipsIguales(a, b) {
  const xs = [...(a || [])].sort((x, y) => x - y);
  const ys = [...(b || [])].sort((x, y) => x - y);
  if (xs.length !== ys.length) return false;
  return xs.every((v, i) => v === ys[i]);
}

/** Pool 9 = motor clásico; oculto si INTER2 hizo fallback (= mismos chips que Pool 0). */
export function pool9IgualOficial(mesas) {
  const p0 = mesas?.oficial?.prediccion?.chips;
  const p9 = panelPool9(mesas)?.prediccion?.chips;
  if (!p9?.length && !p0?.length) return true;
  return chipsIguales(p0, p9);
}

export function poolHiddenInUI(id, panel = null, mesas = null) {
  const raw = id || panel?.id || "";
  const norm = normalizePoolRowId(raw, panel || {});
  if (UI_HIDDEN_POOL_IDS.includes(norm) || UI_HIDDEN_POOL_IDS.includes(raw)) {
    return true;
  }
  if (
    mesas &&
    (norm === "pool-9" || raw === "pool-9" || panel?.pool9 || panel?.classic)
  ) {
    return pool9IgualOficial(mesas);
  }
  return false;
}

export function pinnedPoolIdsForUI() {
  return PINNED_POOL_IDS.filter((id) => !UI_HIDDEN_POOL_IDS.includes(id));
}

/** Normaliza id legacy del motor clásico (oficial-classic → pool-9). */
export function normalizePoolRowId(id, panel) {
  if (
    id === "oficial-classic" ||
    id === "pool-9" ||
    panel?.pool9 ||
    panel?.classic
  ) {
    return "pool-9";
  }
  return id;
}

export function panelPool9(mesas) {
  return mesas?.["pool-9"] || mesas?.["oficial-classic"] || null;
}

/** Etiqueta corta de vista: Mesa-0 … Mesa-5 · Mesa-7 · Mesa-8 · Mesa-9 */
export function etiquetaMesa(panel) {
  if (!panel) return "—";
  if (panel.inter2 || panel.id === "inter2") return "Mesa-8";
  if (panel.liveRc || panel.id === "live-rc") return "Mesa-10";
  if (panel.lc || panel.id === "lc-01") return "Mesa-7";
  if (
    panel.pool9 ||
    panel.classic ||
    panel.id === "pool-9" ||
    panel.id === "oficial-classic"
  )
    return "Mesa-9";
  if (panel.id === "oficial" || panel.nombre === "OFICIAL") return "Mesa-0";
  if (panel.id && ETIQUETA_ALIAS[panel.id]) return ETIQUETA_ALIAS[panel.id];
  if (panel.ej && ETIQUETA_ALIAS[panel.ej]) return ETIQUETA_ALIAS[panel.ej];
  if (panel.nombre && ETIQUETA_ALIAS[panel.nombre])
    return ETIQUETA_ALIAS[panel.nombre];
  if (!panel.beta) return panel.nombre || "Mesa";
  return panel.nombre || "Mesa";
}

/** Bloques de 20 min: 00–19 · 20–39 · 40–59 */
export const BLOQUES_20 = [
  { key: "a", label: "00–19", lo: 0, hi: 19 },
  { key: "b", label: "20–39", lo: 20, hi: 39 },
  { key: "c", label: "40–59", lo: 40, hi: 59 },
];

export function chipsPorBloque(chips) {
  return BLOQUES_20.map((b) => ({
    ...b,
    chips: (chips || []).filter((m) => m >= b.lo && m <= b.hi),
  }));
}

export function cubre(m) {
  const x = ((m % 60) + 60) % 60;
  return [(x + 59) % 60, x, (x + 1) % 60];
}

export function dist(a, b) {
  const d = Math.abs(a - b) % 60;
  return Math.min(d, 60 - d);
}

export function andenDe(m) {
  if (m <= 19) return "temprano";
  if (m <= 39) return "medio";
  return "tarde";
}

export function andenFrase(m) {
  if (m < 20) return "primer tercio";
  if (m < 40) return "el medio";
  return "el final";
}

export function andenRango(m) {
  if (m < 20) return "00–19";
  if (m < 40) return "20–39";
  return "40–59";
}

export function lucesHasta(oficiales, T) {
  return (oficiales || []).filter((m) => m <= T);
}

export function cobraFicha(m, oficiales) {
  return (oficiales || []).filter((x) => dist(x, m) <= 1);
}

/** Desplazamiento en el anillo (−29…30). Vecino: −1 o +1. */
export function deltaAnillo(de, a) {
  let d = (((Number(a) - Number(de)) % 60) + 60) % 60;
  if (d > 30) d -= 60;
  return d;
}

export function etiquetaVecino(m, hits) {
  return (hits || [])
    .filter((x) => x !== m)
    .map((luz) => deltaAnillo(m, luz))
    .sort((a, b) => a - b)
    .map((d) => (d > 0 ? `+${d}` : `${d}`))
    .join("\n");
}

export function ventanaVista(m, hasta, pleno = false) {
  if (hasta == null || hasta < 0) return false;
  const mins = pleno ? [((m % 60) + 60) % 60] : cubre(m);
  return mins.every((x) => x <= hasta);
}

export function enJuego(m, T) {
  if (m === 0) return T <= 1 || T >= 59;
  if (m === 59) return T >= 58;
  return T >= m - 1 && T <= m + 1;
}

export function yaPaso(m, T) {
  if (m === 0) return T >= 2 && T < 59;
  if (m === 59) return false;
  return T > m + 1;
}

/** Parpadea desde 3 min antes del chip hasta que cierra su ventana (m+1). */
/**
 * Empieza a parpadear 30s antes de que arranque el minuto anterior (m-1) y sigue
 * hasta que cierra la ventana de la ficha (fin del minuto m+1).
 */
export function avisoCerca(m, T, segundo = 0) {
  const HORA = 3600;
  const ahoraSeg = (((T * 60 + (segundo || 0)) % HORA) + HORA) % HORA;
  const inicioSeg = (((m * 60 - 90) % HORA) + HORA) % HORA;
  const d = (((ahoraSeg - inicioSeg) % HORA) + HORA) % HORA;
  return d <= 210;
}

export function rolFicha(tiro) {
  const flag = tiro?.flag;
  if (flag === "SEGURO") return "pleno";
  if (flag === "TIBIO") return "ficha";
  if (flag === "NUCLEO") return "núcleo";
  if (flag === "ANILLO") return "anillo";
  if (flag) return String(flag).toLowerCase();
  return "ficha";
}

export function estadoFicha(m, { T, oficiales = [], tiro, marca } = {}) {
  const hasta = lucesHasta(oficiales, T);
  const hits = cobraFicha(m, hasta);
  const [a, c, b] = cubre(m);
  const rol = rolFicha(tiro);
  const cobroTxt =
    rol === "pleno"
      ? `pleno ${pad(m)}`
      : `${pad(m)} cobra ${pad(a)}, ${pad(c)} y ${pad(b)}`;

  if (hits.length) {
    const exacto = hits.includes(m);
    return {
      clave: "cobro",
      etiqueta: exacto ? "exacto" : etiquetaVecino(m, hits),
      frase: exacto
        ? `Cobraste el ${cobroTxt}.`
        : `Cobraste de vecino: salió ${hits.map(pad).join(" y ")}. ${cobroTxt}.`,
      hits,
    };
  }
  if (enJuego(m, T)) {
    return {
      clave: "juego",
      etiqueta: "está jugando",
      frase: `Ahora mismo: ${cobroTxt}.`,
      hits,
    };
  }
  if (yaPaso(m, T)) {
    if (marca && marca.acerto === false) {
      return {
        clave: "muerta",
        etiqueta: "tiro fallido",
        frase: `No hubo nada en ${pad(a)}, ${pad(c)} y ${pad(b)}. No persigas esos tres.`,
        hits,
      };
    }
    return {
      clave: "muerta",
      etiqueta: "ya jugó",
      frase: `Ya pasó: ${cobroTxt}. ¿Acertó?`,
      hits,
    };
  }
  const falta = (m - T + 60) % 60;
  return {
    clave: "viva",
    etiqueta: falta === 1 ? "en 1 min" : `en ${falta} mins`,
    frase: `Más adelante: ${cobroTxt}.`,
    hits,
  };
}

function listaMins(xs) {
  const ys = (xs || []).map(pad);
  if (!ys.length) return "";
  if (ys.length === 1) return ys[0];
  if (ys.length === 2) return `${ys[0]} y ${ys[1]}`;
  return `${ys.slice(0, -1).join(", ")} y ${ys[ys.length - 1]}`;
}

/** Orillas a dos minutos de las islas de H−1. Se nombran, no se fichan. */
export function orillasDe(h1) {
  const s = new Set((h1 || []).map((x) => ((Number(x) % 60) + 60) % 60));
  const out = new Set();
  for (const i of s) {
    for (const d of [2, -2]) {
      const m = (i + d + 60) % 60;
      if (!s.has(m)) out.add(m);
    }
  }
  return [...out].sort((a, b) => a - b);
}

/** @deprecated usar paqueteTipsCiudad */
export function filasTipsResto(opts) {
  return paqueteTipsCiudad(opts);
}

function avisosResto(luces, chips, h1, T) {
  const out = [];
  if (!h1?.length) return out;
  const extras = (luces || []).filter(
    (m) => !(chips || []).some((c) => dist(m, c) <= 1)
  );
  const recientes = [...extras].sort((a, b) => a - b).slice(-3);
  const vistos = new Set();
  for (const m of recientes) {
    const d = Math.min(...h1.map((x) => dist(m, x)));
    if (d === 2) {
      out.push(
        `Cayó el ${pad(m)}, a dos de la foto. Se nombra; no es ficha nueva.`
      );
      continue;
    }
    if (d < 3) continue;
    const juntas = extras.filter((x) => dist(x, m) <= 4).sort((a, b) => a - b);
    if (juntas.length >= 2) {
      const clave = juntas.join("-");
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      out.push(
        `Cayeron ${listaMins(juntas)} lejos de tus fichas, juntas. No persigas otra silla en ese hueco.`
      );
    } else {
      out.push(
        `Cayó el ${pad(m)} lejos de tus fichas. Si viene otra cerca, no persigas esa compañera.`
      );
    }
  }
  if (luces.length) {
    const ultima = Math.max(...luces);
    if (ultima <= 57) {
      const gesto = (ultima + 2) % 60;
      const yaChip = (chips || []).includes(gesto);
      if (!yaChip && !yaPaso(gesto, T) && T >= ultima) {
        out.push(
          `No pongas ficha en ${pad(gesto)} solo porque acaba de caer ${pad(ultima)}.`
        );
      }
    }
  }
  return out;
}

/** Última luz ya salida a este minuto. */
export function ultimaLuzHasta(luces, T) {
  const xs = (luces || []).filter((m) => m <= T);
  if (!xs.length) return null;
  return Math.max(...xs);
}

/**
 * Cómo VA la hora: hueco, recuento, final.
 * No es “cómo se viene” (no nombra el próximo minuto).
 */
export function consejoEspera(luces, T) {
  const ultima = ultimaLuzHasta(luces, T);
  const hueco = ultima == null ? T : T - ultima;
  const n = (luces || []).length;
  const out = [];
  if (T >= 4 && hueco >= 4) {
    if (ultima == null) {
      out.push(
        `Ejemplo de ahora: van ${hueco} minutos en blanco. El ${pad(T)} no está más caliente que el 03. No agregues una ficha porque “ya toca”.`
      );
    } else {
      const prox = Math.min(59, ultima + hueco);
      out.push(
        `Ejemplo de ahora: cayó el ${pad(ultima)} y estamos en el ${pad(T)} (${hueco} min sin luz). El ${pad(prox)} no “debe” prender por la espera. No pongas ficha nueva en ese hueco.`
      );
    }
  }
  const recuento =
    n >= 3 && (hueco >= 4 || T === 20 || T === 40) && T < 50;
  if (recuento) {
    out.push(
      `Van ${n} luces. Ni el recuento ni un hueco largo calientan la próxima: no extra para fichar.`
    );
  } else if (n <= 1 && T >= 8 && hueco >= 4) {
    out.push(
      "Si cae una luz suelta en este hueco, se nombra. No es ficha nueva: la mesa flaca no se ‘completa’ con extras."
    );
  }
  if (T >= 50) {
    out.push(
      n >= 3
        ? `Vamos por el ${pad(T)}. Van ${n} luces. Ni el final del reloj ni el recuento calientan: un tiro que empieza ahora tiene la misma chance que a las 10. Lo gordo es el que cruza la hora.`
        : `Vamos por el ${pad(T)}. Estos minutos no calientan: un tiro que empieza ahora tiene la misma chance que a las 10. Lo gordo es el que cruza la hora, no el ${pad(T)}.`
    );
  }
  return out;
}

export function hablaMesa({
  T = 0,
  oficiales = [],
  chips = [],
  tiros = [],
  hayPleno = false,
  plenoMin = null,
  fotoVacia = false,
  h1 = [],
  nGClima = null,
  k = null,
  som02Meta = null,
  modo = "viva",
  hora = "",
  abierta = false,
}) {
  const tips = paqueteTipsCiudad({
    h1,
    oficiales,
    T,
    chips,
    tiros,
    nGClima,
    k,
    som02Meta,
  });
  const conTips = (obj) => ({ ...obj, tips });

  const luces = lucesHasta(oficiales, T);
  const n0019 =
    T < 20
      ? oficiales.filter((m) => m <= T && m <= 19).length
      : oficiales.filter((m) => m <= 19).length;
  const n2039 =
    T < 40
      ? oficiales.filter((m) => m >= 20 && m <= 39 && m <= T).length
      : oficiales.filter((m) => m >= 20 && m <= 39).length;
  const nTarde = oficiales.filter((m) => m >= 40 && m <= T).length;

  const byMin = new Map((tiros || []).map((t) => [t.minuto, t]));
  const cobradas = (chips || []).filter(
    (m) => cobraFicha(m, luces).length > 0
  );
  const propias0019 = (chips || []).filter((m) => m <= 19);
  const propiasCobraron =
    T >= 19
      ? propias0019.filter((m) => cobraFicha(m, luces).length > 0)
      : [];

  const kicker =
    modo === "replay"
      ? `Así hablaba ${hora || "esa mesa"} al minuto ${pad(T)}`
      : abierta
        ? `${hora || "Esta mesa"} · minuto ${pad(T)} · ${andenFrase(T)} (${andenRango(T)})`
        : `${hora || "La próxima mesa"} · minuto ${pad(T)} · ${andenFrase(T)} (${andenRango(T)})`;

  const titulo = hora
    ? `Tips de la hora ${hora} · ${andenFrase(T)} (${andenRango(T)})`
    : "Tips de la hora";

  const avisos = [];
  for (const m of cobradas) {
    const [a, c, b] = cubre(m);
    avisos.push(
      `La ficha ${pad(m)} ya cobró: no persigas ${pad(a)}, ${pad(c)} y ${pad(b)}.`
    );
  }
  avisos.push(...avisosResto(luces, chips, h1, T));

  if (fotoVacia && T === 0) {
    return conTips({
      tono: "planta",
      kicker,
      titulo,
      verbo: "No te sentés a esta mesa",
      parrafos: [
        "La mesa anterior no dejó minutos para copiar. Sin ese mapa, la mitad de estas horas se van en blanco. Conservar las fichas acá es acierto.",
      ],
      avisos,
      n0019,
      n2039,
      luces: luces.length,
    });
  }

  if (T === 0 && luces.length === 0) {
    const parrafos = [];
    if (hayPleno && plenoMin != null) {
      parrafos.push(
        `Hay un pleno: el ${pad(plenoMin)}. Es la única apuesta al número exacto. No lo retires.`
      );
    } else {
      parrafos.push(
        "No hay pleno: el cierre anterior fue corto. Cada ficha cobra si sale ese minuto o el de al lado."
      );
    }
    parrafos.push(
      chips.length
        ? `Ponemos ${chips.length === 1 ? "una ficha" : `${chips.length} fichas`}: los minutos que prendieron la vez anterior. No agregues de más.`
        : "No hay fichas en el boleto."
    );
    parrafos.push(
      "Mientras corre, mirá las luces de la mesa — las tuyas y las otras. El primer corte útil es al minuto 20. Un aviso a los 30 lava el plantate. Un hueco largo no significa “ya toca”; van 4 luces no cambia la próxima; el 55 no está más caliente porque es tarde."
    );
    if (tips.sombra?.ok) {
      const m = tips.sombra.minuto;
      const prox = tips.sombra.proxima;
      const lineas = [
        `Recomendación principal: mirá si prende luz en el ${pad(m)} (o ${pad((m + 59) % 60)} / ${pad((m + 1) % 60)}). Nada más en esta pista.`,
      ];
      if (prox != null) {
        lineas.push(
          `Si marca el ${pad(m)} → no vayas por el ${pad(prox)}. Si no marca el ${pad(m)} pero marca el de al lado → mantenete con el ${pad(prox)}.`
        );
      } else {
        lineas.push(
          `Si marca el ${pad(m)} → no agregues fichas. Si marca el de al lado → seguí el boleto. Si no marca nada → el boleto sigue igual.`
        );
      }
      parrafos.unshift(...lineas);
    } else if (tips.sombra && !tips.sombra.ok) {
      parrafos.unshift(tips.sombra.nota);
    }
    if (tips.faro) {
      const f = tips.faro;
      parrafos.push(
        `Cupo de la mesa: clima ${f.clima.toLowerCase()}. Se esperan unas ${Math.round(f.nG_esperado)} luces (entre ${f.banda[0]} y ${f.banda[1]}). Si caen de más o de menos → no agregues fichas por eso.`
      );
    }
    if (tips.nOrillas) {
      parrafos.push(
        `Orillas: ${listaMins(tips.orillas)}. Mirá si prende alguna. Si prende → nombrá; no agregues ficha. Si no prende → normal (solo ~17% suelen prender). Probable: ${tips.cuanto}.`
      );
    }
    return conTips({
      tono: hayPleno ? "pleno" : "antes",
      kicker,
      titulo,
      verbo: hayPleno ? `Hay pleno: el ${pad(plenoMin)}` : "",
      parrafos,
      avisos,
      n0019,
      n2039,
      luces: luces.length,
    });
  }

  let tono = "sigue";
  let verbo = "Seguí el plan";
  const parrafos = [];

  if (tips.sombra?.ok) {
    const m = tips.sombra.minuto;
    const prox = tips.sombra.proxima;
    parrafos.push(
      `Recomendación principal: mirá si prende luz en el ${pad(m)} (o ${pad((m + 59) % 60)} / ${pad((m + 1) % 60)}). Nada más en esta pista.`
    );
    if (prox != null) {
      parrafos.push(
        `Si marca el ${pad(m)} → no vayas por el ${pad(prox)}. Si no marca el ${pad(m)} pero marca el de al lado → mantenete con el ${pad(prox)}.`
      );
    } else {
      parrafos.push(
        `Si marca el ${pad(m)} → no agregues fichas. Si marca el de al lado → seguí el boleto. Si no marca nada → el boleto sigue igual.`
      );
    }
  }

  if (T < 20) {
    if (n0019 === 0) {
      tono = "espera";
      verbo = "Todavía no cayó ninguna luz";
      parrafos.push(
        `Vamos por el ${pad(T)}. El plantate se decide al llegar al 20: si el primer tercio sigue en blanco, esas mesas suelen ser cortas.`
      );
      parrafos.push("No agregues fichas. Dejá correr las que ya están.");
    } else if (n0019 === 1) {
      tono = "gris";
      verbo = "Una luz: a menudo corta";
      parrafos.push(
        "Ya prendió una. No agregues. Seguí las tuyas; no persigas el hueco del medio."
      );
    } else if (n0019 === 2) {
      tono = "sigue";
      verbo = "Dos luces: mesa normal";
      parrafos.push("Seguí el plan. No canceles. No agregues minutos nuevos.");
    } else {
      tono = "viva";
      verbo = "Mesa viva: no llenes el reloj";
      parrafos.push(
        `Van ${n0019} luces y el último tercio no se hincha: sigue trayendo unas tres. Dejá correr el boleto que ya está.`
      );
    }
  } else if (T < 40) {
    if (n0019 === 0) {
      tono = "planta";
      verbo = "Plantate";
      parrafos.push(
        "De 00 a 19 no cayó ninguna luz. Esas mesas suelen ser cortas. No persigas el hueco. No agregues."
      );
      parrafos.push(
        "Si dejás fichas de después, pagan un poco menos; no es grial. Conservar acá es acierto."
      );
    } else if (n0019 === 1) {
      tono = "gris";
      verbo = "El primer tercio fue flaco";
      parrafos.push(
        "Una sola luz de 00 a 19: a menudo corta. No agregues. Seguí tus fichas."
      );
    } else if (n0019 === 2) {
      tono = "sigue";
      verbo = "Seguí el plan";
      parrafos.push(
        "Dos luces en el primer tercio: mesa normal. No canceles. No agregues."
      );
    } else {
      tono = "viva";
      verbo = "Mesa viva";
      parrafos.push(
        "El final no es premio: trae unas tres luces igual. No vayas a todas. No ingestar el resto del reloj."
      );
    }
    if (propias0019.length && propiasCobraron.length === 0 && n0019 > 0) {
      parrafos.push(
        "Ninguna de las tuyas cobró todavía. El resto sigue cobrando como siempre: no canceles la mesa."
      );
    }
  } else {
    if (n2039 === 0) {
      tono = "planta";
      verbo = "El medio quedó en blanco";
      parrafos.push(
        "De 20 a 39 no cayó ninguna luz. Otra vez corta. No persigas. Última carta = tus fichas de 40–59, no el hueco."
      );
    } else if (n0019 === 0) {
      tono = "planta";
      verbo = "Plantate";
      parrafos.push(
        "El primer tercio ya había quedado en blanco. No persigas ahora el final."
      );
    } else {
      tono = n0019 >= 3 ? "viva" : "sigue";
      verbo = nTarde ? "Última carta: las fichas que ya están" : "Última carta";
      parrafos.push(
        "El último tercio no se hincha. Seguí el boleto. No sientes minutos nuevos."
      );
    }
  }

  parrafos.push(...consejoEspera(luces, T));

  if (chips.length) {
    const vivas = chips.filter((m) => {
      const e = estadoFicha(m, { T, oficiales, tiro: byMin.get(m) });
      return e.clave === "viva" || e.clave === "juego";
    });
    if (vivas.length) {
      parrafos.push(
        vivas.length === 1
          ? `Sigue en juego la ficha ${pad(vivas[0])}.`
          : `Siguen en juego ${listaMins(vivas)}.`
      );
    }
  }

  if (modo === "viva" && !abierta && T > 0 && (oficiales || []).length === 0) {
    parrafos.unshift(
      "Esta hora todavía no está en la cinta. Lo que leés es el ensayo: cómo hablaría si llegara a este minuto sin luces."
    );
  }

  if (tips.nOrillas && T > 0) {
    const orillasVivas = tips.orillas.filter((m) => !yaPaso(m, T) || enJuego(m, T));
    if (orillasVivas.length) {
      parrafos.push(
        `Orillas aún en juego: ${listaMins(orillasVivas)}. Si prende una → nombrá; no agregues ficha. Si no → seguí el boleto. Probable en la hora: ${tips.cuanto}.`
      );
    }
  }

  return conTips({
    tono,
    kicker,
    titulo,
    verbo,
    parrafos,
    avisos,
    n0019,
    n2039,
    luces: luces.length,
  });
}
