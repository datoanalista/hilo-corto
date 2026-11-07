/**
 * Motor ciudad — lectura del reloj (dashboard).
 * Espejo de lab-ciudad/ciudad. Tres capas sordas. Cero chips.
 */
import { proponerSom02Chip, som02ChipTip, som02ProdTip } from "./som02Info.js";

const LLUVIA = 0.1701;
const HUECO = 4;
/** Diff B TEST W33-34 */
const P_PAREJA = 0.233;
const P_SOLA = 0.695;

const FARO_MEDIANA = {
  1: 10, 2: 14, 4: 6.5, 5: 10, 6: 10, 7: 11, 8: 9, 9: 9, 10: 10,
  11: 10, 12: 10, 13: 9, 14: 11, 15: 11, 16: 9.5, 17: 11, 18: 10,
};

function pad(m) {
  return String(m).padStart(2, "0");
}

function dist(a, b) {
  const d = Math.abs(a - b) % 60;
  return Math.min(d, 60 - d);
}

function orillasDe(h1) {
  const s = new Set((h1 || []).map((x) => ((x % 60) + 60) % 60));
  const out = new Set();
  for (const i of s) {
    for (const d of [2, -2]) {
      const m = (i + d + 60) % 60;
      if (!s.has(m)) out.add(m);
    }
  }
  return [...out].sort((a, b) => a - b);
}

function listaMins(xs) {
  const ys = (xs || []).map(pad);
  if (!ys.length) return "—";
  if (ys.length === 1) return ys[0];
  if (ys.length === 2) return `${ys[0]} y ${ys[1]}`;
  return `${ys.slice(0, -1).join(", ")} y ${ys[ys.length - 1]}`;
}

function andenRango(m) {
  m = ((m % 60) + 60) % 60;
  if (m <= 19) return "00–19";
  if (m <= 39) return "20–39";
  return "40–59";
}

function andenFrase(m) {
  m = ((m % 60) + 60) % 60;
  if (m < 20) return "primer tercio";
  if (m < 40) return "el medio";
  return "el final";
}

function lucesHasta(oficiales, T) {
  return (oficiales || []).filter((m) => m <= T);
}

function enJuego(m, T) {
  if (m === 0) return T <= 1 || T >= 59;
  if (m === 59) return T >= 58;
  return T >= m - 1 && T <= m + 1;
}

function yaPaso(m, T) {
  if (m === 0) return T >= 2 && T < 59;
  if (m === 59) return false;
  return T > m + 1;
}

function cubre(m) {
  const x = ((m % 60) + 60) % 60;
  return [(x + 59) % 60, x, (x + 1) % 60];
}

function minDistH1(m, h1) {
  if (!h1?.length) return 99;
  return Math.min(...h1.map((x) => dist(m, x)));
}

function racimosLejos(xs, hueco = 4) {
  const s = [...new Set(xs)].sort((a, b) => a - b);
  if (!s.length) return [];
  const g = [[s[0]]];
  for (let i = 1; i < s.length; i++) {
    const m = s[i];
    const prev = g[g.length - 1];
    if (dist(m, prev[prev.length - 1]) <= hueco) prev.push(m);
    else g.push([m]);
  }
  if (
    g.length >= 2 &&
    dist(g[0][0], g[g.length - 1][g[g.length - 1].length - 1]) <= hueco
  ) {
    g[0] = g[g.length - 1].concat(g[0]);
    g.pop();
  }
  return g;
}

function climaDesdeNg(nG) {
  if (nG <= 7) return "FLOJA";
  if (nG >= 12) return "RICA";
  return "NORMAL";
}

/** Mediana de huecos entre luces de la mesa anterior (fallback 4). */
function pasoSombra(h1) {
  const xs = [...new Set((h1 || []).map((x) => ((x % 60) + 60) % 60))].sort(
    (a, b) => a - b
  );
  if (xs.length < 2) return 4;
  const gaps = [];
  for (let i = 0; i < xs.length - 1; i++) gaps.push((xs[i + 1] - xs[i] + 60) % 60);
  gaps.push((xs[0] + 60 - xs[xs.length - 1]) % 60);
  const buenos = gaps.filter((g) => g >= 1 && g <= 20);
  if (!buenos.length) return 4;
  const s = [...buenos].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
}

/**
 * Recomendación principal (Tips): a dónde mirar el reloj.
 * No es ficha del boleto. Incluye si-entonces vs la próxima ficha.
 */
function leerSombra(h1, chips = []) {
  const islas = [...new Set((h1 || []).map((x) => ((x % 60) + 60) % 60))];
  if (!islas.length) {
    return {
      ok: false,
      minuto: null,
      paso: 4,
      ultima: null,
      proxima: null,
      nota: "La mesa anterior no dejó luces para proyectar. Sin recomendación de reloj.",
    };
  }
  const paso = pasoSombra(islas);
  const ultima = Math.max(...islas);
  const minuto = (ultima + paso) % 60;
  const flojo01 = minuto === 1;
  const antes = (minuto + 59) % 60;
  const despues = (minuto + 1) % 60;

  // Próxima ficha del boleto después del minuto recomendado (anillo)
  const xs = [
    ...new Set((chips || []).map((x) => ((x % 60) + 60) % 60)),
  ].sort((a, b) => a - b);
  let proxima = null;
  if (xs.length) {
    const adelante = xs.filter((c) => dist(c, minuto) > 1 && c > minuto);
    const wrap = xs.filter((c) => dist(c, minuto) > 1 && c <= minuto);
    proxima = adelante.length ? adelante[0] : wrap.length ? wrap[0] : null;
  }

  const mira = `Mirá si prende luz en el ${pad(minuto)} (también cuenta el ${pad(antes)} o el ${pad(despues)}).`;
  const origen = `La mesa anterior cerró luces cerca del ${pad(ultima)}. Sumá ~${paso} minutos → zona del ${pad(minuto)}.`;

  let siEntonces;
  if (proxima != null) {
    siEntonces = [
      `Si prende el ${pad(minuto)} → no vayas por el ${pad(proxima)}: esa luz ya dio la lectura; dejá la ficha del ${pad(proxima)} sin perseguir de más.`,
      `Si el ${pad(minuto)} no prende, pero prende el ${pad(despues)} (o el ${pad(antes)}) → mantenete con el ${pad(proxima)}: el plan del boleto sigue.`,
      `Si no prende ninguno de esos tres → no inventes fichas; seguí el boleto como está.`,
    ];
  } else {
    siEntonces = [
      `Si prende el ${pad(minuto)} → ya tenés la lectura de reloj; no agregues minutos nuevos “porque tocó”.`,
      `Si el ${pad(minuto)} no prende, pero prende el ${pad(despues)} o el ${pad(antes)} → la mesa viene corrida un minuto; seguí tus fichas del boleto.`,
      `Si no prende ninguno de esos tres → no inventes fichas; solo anotás que la pista no pegó.`,
    ];
  }

  const nota = [
    origen,
    mira,
    "No es una ficha nueva: solo te dice qué mirar y qué hacer después.",
    ...siEntonces,
    flojo01 ? "Ojo: el minuto 01 suele ser flojo." : null,
  ]
    .filter(Boolean)
    .join(" ");

  return {
    ok: true,
    minuto,
    paso,
    ultima,
    flojo01,
    antes,
    despues,
    proxima,
    mira,
    siEntonces,
    nota,
  };
}

function leerFaro(nG_h1, nisl) {
  const key = Math.max(0, Math.min(18, nG_h1));
  const ng = FARO_MEDIANA[key] ?? 10.03 - 0.009 * nG_h1;
  const cl = climaDesdeNg(nG_h1);
  const lo = Math.max(3, Math.floor(ng) - 2);
  const hi = Math.min(18, Math.floor(ng) + 3);
  return {
    clima: cl,
    nG_esperado: ng,
    banda: [lo, hi],
    nota: `Cupo ${cl.toLowerCase()}: unas ${ng.toFixed(1)} luces (banda ${lo}–${hi}). No elige minutos.`,
  };
}

function ventanaActiva(m1, T) {
  if (T < m1) return false;
  return T - m1 <= HUECO;
}

function avisoTrasPrimeraLejos(m1, luces, h1, T) {
  if (!ventanaActiva(m1, T)) return null;
  if (minDistH1(m1, h1) < 3) return null;
  const lejos = luces.filter((m) => minDistH1(m, h1) >= 3);
  if (!lejos.includes(m1)) return null;
  const companeras = lejos.filter((x) => x !== m1 && dist(x, m1) <= HUECO);
  if (companeras.length) return null;
  const cerca = [(m1 + 59) % 60, (m1 + 1) % 60, (m1 + 2) % 60, (m1 + 58) % 60];
  return {
    id: `aviso-primera-${m1}`,
    minuto: m1,
    tipo: "Luz lejos (primera)",
    estado: "ventana abierta",
    anden: andenRango(m1),
    mira: `Mirá si en los próximos minutos prende otra luz cerca del ${pad(m1)} (hueco de hasta 4 minutos).`,
    siEntonces: [
      `Si prende otra luz cerca del ${pad(m1)} → es pareja: solo nombrá; no agregues ficha en el medio.`,
      `Si no prende ninguna cerca → suele quedar sola (~7 de cada 10). Seguí el boleto.`,
      "En ningún caso agregues fichas nuevas alrededor solo por esta luz.",
    ],
    resumen: `Cayó el ${pad(m1)} lejos de la mesa anterior. Suele quedar sola: no fichés alrededor.`,
    detalle: [
      `Qué mirás: si aparece otra luz cerca del ${pad(m1)} en los próximos minutos.`,
      `Si prende otra cerca → pareja: nombrá; no pongas ficha en el hueco.`,
      `Si no prende ninguna cerca → sola: seguí el boleto.`,
      "No es ficha nueva.",
    ],
    ejemplo: `Ejemplo: cayó el ${pad(m1)} lejos. Si después cae el ${pad(cerca[1])}, no fichés el medio. Si no cae nada cerca, seguí el boleto.`,
    ejemplosTabla: [
      {
        caso: `Cayó el ${pad(m1)} lejos (primera)`,
        paso: "Empezó la ventana",
        mira: pad(m1),
        hacer: "Esperá: ¿viene otra cerca o no?",
      },
      {
        caso: "Si prende otra luz cerca",
        paso: "Pareja",
        mira: "Las dos",
        hacer: "Nombrá. No agregues ficha en el hueco.",
      },
      {
        caso: "Si no prende ninguna cerca",
        paso: "Sola (~7 de cada 10)",
        mira: pad(m1),
        hacer: "Seguí el boleto. No inventes vecinos.",
      },
    ],
  };
}

export function paqueteTipsCiudad({
  h1 = [],
  oficiales = [],
  T = 0,
  chips = [],
  tiros = [],
  nGClima = 10,
  k = null,
  som02Meta = null,
} = {}) {
  const islas = [...new Set((h1 || []).map((x) => ((x % 60) + 60) % 60))];
  const nisl = islas.length;
  const nG_h1 = nisl;
  const faro = leerFaro(nG_h1, nisl);
  const sombra = leerSombra(h1, chips);
  const orillas = orillasDe(h1);
  const eFill = orillas.length * LLUVIA;
  const cuanto =
    eFill < 0.5
      ? "casi ninguna"
      : eFill < 1.5
        ? "alrededor de 1"
        : `alrededor de ${Math.round(eFill)}`;
  const luces = lucesHasta(oficiales, T);
  const filas = [];

  // ── PRIMERO: recomendación de reloj (no es ficha) ──
  if (sombra.ok) {
    const m = sombra.minuto;
    const salio =
      luces.includes(m) ||
      luces.includes(sombra.antes) ||
      luces.includes(sombra.despues);
    const jugando = enJuego(m, T);
    const pasado = yaPaso(m, T);
    let estado;
    if (salio) estado = "ya hubo luz en la zona";
    else if (jugando) estado = "el reloj está en la zona ahora";
    else if (pasado) estado = "esa zona ya pasó";
    else estado = "aún no llega — mirá esto";

    const prox = sombra.proxima;
    filas.push({
      id: "sombra",
      minuto: m,
      tipo: "Recomendación principal",
      estado,
      anden: andenRango(m),
      destacado: true,
      proxima: prox,
      resumen: sombra.nota,
      mira: sombra.mira,
      siEntonces: sombra.siEntonces,
      detalle: [
        "Qué mirás (solo esto): si prende una luz en ese minuto o en el de al lado.",
        `Zona: ${pad(sombra.antes)} · ${pad(m)} · ${pad(sombra.despues)}.`,
        `De dónde sale: mesa anterior cerca del ${pad(sombra.ultima)} + ~${sombra.paso} min.`,
        ...(sombra.siEntonces || []),
        "No es ficha nueva del boleto. No agregues minutos solo por esta pista.",
      ],
      ejemplo: prox != null
        ? `Ejemplo de esta hora: mirá el ${pad(m)}. Si marca el ${pad(m)}, no vayas por el ${pad(prox)}. Si no marca el ${pad(m)} pero marca el ${pad(sombra.despues)}, mantenete con el ${pad(prox)}.`
        : `Ejemplo de esta hora: mirá el ${pad(m)}. Si marca, no inventes fichas. Si marca el de al lado, seguí el boleto.`,
      ejemplosTabla: [
        {
          caso: `Mirá el ${pad(m)} (recomendado ahora)`,
          paso: `${pad(sombra.ultima)} + ~${sombra.paso} min`,
          mira: `${pad(sombra.antes)} / ${pad(m)} / ${pad(sombra.despues)}`,
          hacer: "Esperá a ver si prende luz en esa zona.",
        },
        {
          caso: `Si prende exactamente el ${pad(m)}`,
          paso: "La pista pegó de lleno",
          mira: pad(m),
          hacer:
            prox != null
              ? `No vayas por el ${pad(prox)}. No persigas ni agregues fichas.`
              : "No agregues fichas nuevas. Seguí el boleto.",
        },
        {
          caso: `Si el ${pad(m)} no prende, pero prende el ${pad(sombra.despues)}`,
          paso: "La mesa viene corrida un minuto",
          mira: pad(sombra.despues),
          hacer:
            prox != null
              ? `Mantenete con el ${pad(prox)} (tu próxima ficha del boleto).`
              : "Mantenete con las fichas del boleto.",
        },
        {
          caso: `Si el ${pad(m)} no prende, pero prende el ${pad(sombra.antes)}`,
          paso: "Corrida al otro lado",
          mira: pad(sombra.antes),
          hacer:
            prox != null
              ? `Igual: mantenete con el ${pad(prox)}. No inventes minutos.`
              : "Seguí el boleto. No inventes minutos.",
        },
        {
          caso: "Si no prende ninguno de los tres",
          paso: "La pista no pegó",
          mira: "Ninguno",
          hacer: "No agregues fichas. El boleto sigue igual.",
        },
      ],
    });
  } else {
    filas.push({
      id: "sombra",
      minuto: null,
      tipo: "Recomendación principal",
      estado: "sin pista de reloj",
      anden: "—",
      destacado: true,
      resumen: sombra.nota,
      mira: "Sin zona de reloj: no hay qué mirar de más.",
      siEntonces: [
        "Sin luces en la mesa anterior: solo el boleto (pleno si hubo, e islas de la foto).",
        "No inventes minutos para llenar la mesa.",
      ],
      detalle: [
        "Sin luces en la mesa anterior no se puede proyectar el reloj.",
        "En ese caso: solo el boleto. No inventes minutos.",
      ],
      ejemplo: "Ejemplo: mesa previa en blanco → no recomendación de minuto.",
      ejemplosTabla: [
        {
          caso: "Mesa anterior sin luces",
          paso: "No hay",
          mira: "Ninguno",
          hacer: "Conservá fichas. No copies inventos.",
        },
      ],
    });
  }

  const som02Tiro = (tiros || []).find((t) => t.rol === "sombra");
  const prodTip = som02ProdTip(som02Tiro, som02Meta || {});
  if (prodTip) {
    const m = prodTip.minuto;
    filas.splice(1, 0, {
      id: "som02-prod",
      minuto: m,
      tipo: "SOM02 · prod",
      estado: "en el boleto",
      anden: andenRango(m),
      destacado: true,
      resumen: prodTip.resumen,
      mira: `Ficha sombra min ${pad(m)} — cableada al motor.`,
      siEntonces: [
        "Cobra como TIBIO (minuto o vecino).",
        "El tip de reloj arriba mira la misma zona.",
      ],
      detalle: prodTip.detalle,
    });
  } else {
    const som02 = proponerSom02Chip({
      chips,
      h1,
      nGClima: nGClima ?? (k != null ? k + 2 : 10),
    });
    const chipLab = som02ChipTip(som02);
    if (chipLab) {
      const m = chipLab.minuto;
      filas.splice(1, 0, {
        id: "som02-chip",
        minuto: m,
        tipo: "SOM02 · aviso",
        estado: "no entró al boleto",
        anden: andenRango(m),
        destacado: true,
        resumen: chipLab.resumen,
        detalle: chipLab.detalle,
      });
    }
  }

  filas.push({
    id: "faro",
    minuto: null,
    tipo: "Cupo de la mesa",
    estado: faro.clima,
    anden: `${faro.banda[0]}–${faro.banda[1]} luces`,
    mira: "Mirá cuántas luces suele traer esta mesa (no qué minutos).",
    siEntonces: [
      `Si el cupo viene ${faro.clima.toLowerCase()} (unas ${faro.banda[0]} a ${faro.banda[1]} luces) → no agregues fichas “para completar”.`,
      "Si caen menos luces de lo esperado → normal; el boleto no se hincha.",
      "Si caen más → seguí el boleto; el cupo no inventa minutos nuevos.",
    ],
    resumen: `Cupo: mesa ${faro.clima.toLowerCase()}. Se esperan unas ${Math.round(faro.nG_esperado)} luces (entre ${faro.banda[0]} y ${faro.banda[1]}). No elige minutos.`,
    detalle: [
      "Qué mirás: cuántas luces suele haber en la hora, no dónde caen.",
      `La mesa anterior tuvo ${nG_h1} luces → clima ${faro.clima}.`,
      `Si el cupo es ${faro.clima.toLowerCase()} → no agregues fichas para completar.`,
      "Si caen de más o de menos → el boleto sigue; no inventes minutos.",
    ],
    ejemplo: `Ejemplo: cupo ${faro.clima} ~${Math.round(faro.nG_esperado)} luces → no agregues fichas por eso.`,
    ejemplosTabla: [
      {
        caso: `Cupo ${faro.clima}`,
        paso: `Esperá ~${Math.round(faro.nG_esperado)} luces`,
        mira: `${faro.banda[0]}–${faro.banda[1]}`,
        hacer: "No agregues fichas para “llegar al número”.",
      },
      {
        caso: "Si caen menos de lo esperado",
        paso: "Mesa más flaca",
        mira: "Conteo",
        hacer: "Normal. Seguí el boleto.",
      },
      {
        caso: "Si caen más de lo esperado",
        paso: "Mesa más rica",
        mira: "Conteo",
        hacer: "Seguí el boleto. No inventes minutos.",
      },
    ],
  });

  filas.push({
    id: "pronostico",
    minuto: null,
    tipo: "Orillas (pronóstico)",
    estado: cuanto,
    anden: "toda la hora",
    mira:
      orillas.length > 0
        ? `Mirá si prende alguna de estas orillas: ${listaMins(orillas)}. No cuál exacta de antemano.`
        : "No hay orillas pronunciadas en esta mesa.",
    siEntonces: [
      orillas.length
        ? `Si prende una orilla de la lista → se nombra; no agregues ficha nueva ahí.`
        : "Sin orillas: no hay esta pista.",
      `Si no prende ninguna → normal (solo ~17% de las orillas suelen prender). Seguí el boleto.`,
      "Nunca uses una orilla como ficha nueva del boleto.",
    ],
    resumen: orillas.length
      ? `Hay ${orillas.length} orillas a dos minutos de la mesa anterior. Probable: ${cuanto} se enciendan. Se nombran; no se fichan.`
      : "No hay orillas a dos minutos de la mesa anterior.",
    detalle: [
      orillas.length
        ? `Qué mirás: si prende luz en ${listaMins(orillas)}.`
        : "Qué mirás: nada en orillas.",
      `Si prende una → nombrá; no agregues ficha.`,
      `Si no prende ninguna → normal. Seguí el boleto.`,
    ],
    ejemplo: orillas.length
      ? `Ejemplo: orillas ${listaMins(orillas)}. Si prende una, no la fichés.`
      : "Ejemplo: sin orillas → solo el boleto.",
    ejemplosTabla: [
      {
        caso: "Hay orillas en la lista",
        paso: `Probable: ${cuanto}`,
        mira: listaMins(orillas) || "—",
        hacer: "Esperá a ver si prende alguna.",
      },
      {
        caso: "Si prende una orilla",
        paso: "Salió luz ahí",
        mira: "Esa orilla",
        hacer: "Nombrá. No agregues ficha nueva.",
      },
      {
        caso: "Si no prende ninguna",
        paso: "Normal (~17% prende)",
        mira: "Ninguna",
        hacer: "Seguí el boleto.",
      },
    ],
  });

  for (const m of orillas) {
    const salio = luces.includes(m);
    const jugando = enJuego(m, T);
    const pasado = yaPaso(m, T);
    const esChip = (chips || []).includes(m);
    const [a, c, b] = cubre(m);
    let estado;
    let mira;
    let siEntonces;
    if (salio) {
      estado = "ya prendió";
      mira = `Ya prendió luz en el ${pad(m)}.`;
      siEntonces = [
        esChip
          ? `Si era tu ficha del ${pad(m)} → cobró (exacto o vecino). No persigas ${pad(a)}, ${pad(c)} y ${pad(b)}.`
          : `Si no tenías ficha ahí → solo nombrá. No agregues ficha tarde.`,
        "Seguí el resto del boleto.",
      ];
    } else if (jugando) {
      estado = "el reloj está ahí";
      mira = `Ahora el reloj pasa por el ${pad(m)} (también ${pad(a)} y ${pad(b)}).`;
      siEntonces = [
        esChip
          ? `Si prende el ${pad(m)} o el de al lado → tu ficha cobra. No persigas los tres.`
          : `Si prende el ${pad(m)} → se nombra; no inventes ficha en la orilla.`,
        `Si no prende → seguí el boleto.`,
      ];
    } else if (pasado) {
      estado = "pasó sin luz";
      mira = `El ${pad(m)} ya pasó y no prendió.`;
      siEntonces = [
        "Normal: pocas orillas prenden. No “recuperes” con una ficha nueva.",
        "Seguí el boleto.",
      ];
    } else {
      estado = "aún no llega";
      mira = `Todavía no llega el ${pad(m)} (vamos por el ${pad(T)}).`;
      siEntonces = [
        `Cuando llegue: mirá si prende el ${pad(m)}.`,
        esChip
          ? `Si prende (o el de al lado) → cobra tu ficha.`
          : `Si prende → nombrá; no agregues ficha.`,
        `Si no prende → seguí el boleto.`,
      ];
    }
    filas.push({
      id: `orilla-${m}`,
      minuto: m,
      tipo: esChip ? "Orilla (en tu boleto)" : "Orilla",
      estado,
      anden: andenRango(m),
      mira,
      siEntonces,
      resumen: `${mira} ${siEntonces[0]}`,
      detalle: ["Qué mirás: " + mira.replace(/^Mirá |^Ya |^Ahora |^El |^Todavía /, ""), ...siEntonces],
      ejemplo: siEntonces[0],
      ejemplosTabla: [
        {
          caso: `Orilla ${pad(m)} — ${estado}`,
          paso: andenFrase(m),
          mira: pad(m),
          hacer: siEntonces[0],
        },
        {
          caso: "Si prende",
          paso: esChip ? "Cobra ficha" : "Solo nombre",
          mira: `${pad(a)}/${pad(c)}/${pad(b)}`,
          hacer: esChip
            ? "No persigas los tres de esa ficha."
            : "No agregues ficha nueva.",
        },
        {
          caso: "Si no prende",
          paso: "Orilla en blanco",
          mira: pad(m),
          hacer: "Seguí el boleto.",
        },
      ],
    });
  }

  const lejos = luces.filter((m) => minDistH1(m, h1) >= 3);
  for (const m1 of lejos) {
    const av = avisoTrasPrimeraLejos(m1, luces, h1, T);
    if (av) filas.push(av);
  }
  for (const g of racimosLejos(lejos, HUECO)) {
    const nom = g.length === 1 ? "Sola" : g.length === 2 ? "Pareja" : "Racimo";
    const mins = listaMins(g);
    const mira =
      nom === "Sola"
        ? `Ya cayó el ${pad(g[0])} lejos de la mesa anterior.`
        : nom === "Pareja"
          ? `Ya cayeron el ${pad(g[0])} y el ${pad(g[1])} lejos, juntas.`
          : `Ya cayeron lejos, en grupo: ${mins}.`;
    const siEntonces =
      nom === "Sola"
        ? [
            "Si esperabas pareja y no vino → no fichés vecinos “por si acaso”.",
            "Seguí el boleto. Se nombra; no se ficha.",
          ]
        : nom === "Pareja"
          ? [
              "Si ves las dos juntas → no pongas ficha en el medio.",
              "Seguí el boleto. Se nombra; no se ficha.",
            ]
          : [
              "Si ves el grupo → no rellenes el hueco con fichas nuevas.",
              "Seguí el boleto. Se nombra; no se ficha.",
            ];
    filas.push({
      id: `lejos-${g.join("-")}`,
      minuto: g[0],
      tipo: `Luz lejos · ${nom.toLowerCase()}`,
      estado: "ya cayó",
      anden: andenRango(g[0]),
      mira,
      siEntonces,
      resumen: `${mira} ${siEntonces[0]}`,
      detalle: ["Qué mirás: " + mira, ...siEntonces],
      ejemplo: siEntonces[0],
      ejemplosTabla: [
        {
          caso: nom,
          paso: "Ya pasó",
          mira: mins,
          hacer: siEntonces[0],
        },
        {
          caso: "Tentación de fichar el hueco",
          paso: "No",
          mira: "—",
          hacer: "No. Seguí el boleto.",
        },
      ],
    });
  }

  return { filas, faro, sombra, orillas, eFill, cuanto, nOrillas: orillas.length };
}
