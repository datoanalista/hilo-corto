import { andenDe, andenFrase, andenRango, pad } from "./mesa.js";

const TAG_RE = /^h\d{1,2}-\d{6}$/i;
const TIRO_RE =
  /^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})(?:\s+(R|G\d?))?(?:\s+(\d+))?$/i;

export const ETAPAS = [
  { id: "temprano", rango: "00–19", a: 0, b: 19, nombre: "primeros 20" },
  { id: "medio", rango: "20–39", a: 20, b: 39, nombre: "el medio" },
  { id: "tarde", rango: "40–59", a: 40, b: 59, nombre: "el final" },
];

export function relojSistema(date = new Date()) {
  const dd = pad(date.getDate());
  const mm = pad(date.getMonth() + 1);
  const yy = String(date.getFullYear()).slice(-2);
  const hora = date.getHours();
  const minuto = date.getMinutes();
  const segundo = date.getSeconds();
  return {
    tag: `h${hora}-${dd}${mm}${yy}`,
    fecha: `${dd}/${mm}/${yy}`,
    hora,
    minuto,
    segundo,
    tramo: andenDe(minuto),
    frase: andenFrase(minuto),
    rango: andenRango(minuto),
  };
}

export function parseTag(tag) {
  const m = /^h(\d{1,2})-(\d{2})(\d{2})(\d{2})$/i.exec((tag || "").trim());
  if (!m) return null;
  const hora = Number(m[1]);
  return {
    hora,
    dia: Number(m[2]),
    mes: Number(m[3]),
    anio: 2000 + Number(m[4]),
    tag: `h${hora}-${m[2]}${m[3]}${m[4]}`,
  };
}

export function siguienteTag(tag) {
  const t = parseTag(tag);
  if (!t) return null;
  const d = new Date(t.anio, t.mes - 1, t.dia, t.hora);
  d.setHours(d.getHours() + 1);
  return `h${d.getHours()}-${pad(d.getDate())}${pad(d.getMonth() + 1)}${String(
    d.getFullYear()
  ).slice(-2)}`;
}

export function anteriorTag(tag) {
  const t = parseTag(tag);
  if (!t) return null;
  const d = new Date(t.anio, t.mes - 1, t.dia, t.hora);
  d.setHours(d.getHours() - 1);
  return `h${d.getHours()}-${pad(d.getDate())}${pad(d.getMonth() + 1)}${String(
    d.getFullYear()
  ).slice(-2)}`;
}

export function liveDisponible(ahora, ultimaIngerida) {
  return liveEstado(ahora, ultimaIngerida).disponible;
}

export function liveEstado(ahora, ultimaIngerida) {
  const n = parseTag(ahora?.tag);
  const u = parseTag(ultimaIngerida);
  if (!n || !u) return { disponible: false, razon: "espera" };
  if (u.tag === n.tag) return { disponible: false, razon: "ya" };
  if (siguienteTag(u.tag) === n.tag) return { disponible: true, razon: "curso" };
  return { disponible: false, razon: "espera" };
}

export function parseTiro(line) {
  const m = TIRO_RE.exec(line);
  if (!m) return null;
  const m0 = Number(m[1]);
  const s0 = Number(m[2]);
  const m1 = Number(m[3]);
  const s1 = Number(m[4]);
  if ([m0, m1].some((x) => x > 59) || [s0, s1].some((x) => x > 59)) return null;
  const tok = (m[5] || "R").toUpperCase();
  const color = tok.startsWith("G") ? "G" : "R";
  const tipo = color === "G" && tok.length > 1 ? Number(tok[1]) : null;
  const vecino = m[6] ? Number(m[6]) : null;
  return {
    m0,
    s0,
    m1,
    s1,
    color,
    tipo,
    vecino,
    lumen: vecino,
    wrap: m1 < m0,
    cruda: line.trim(),
  };
}

function mismasLineas(a, b) {
  if (a.length !== b.length) return false;
  return a.every((ln, i) => ln === b[i]);
}

export function lucesDe(tiros) {
  const out = [];
  const vistos = new Set();
  for (const t of tiros || []) {
    if (t.color !== "G") continue;
    if (vistos.has(t.m0)) continue;
    vistos.add(t.m0);
    out.push(t.m0);
  }
  out.sort((x, y) => x - y);
  return out;
}

export function analizarEtapa({
  texto,
  tagHora,
  etapa,
  locked = [],
  minutoAhora = 59,
}) {
  const meta = ETAPAS[etapa];
  if (!meta) {
    return { ok: false, error: "Esta hora ya está completa." };
  }

  const lines = (texto || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) {
    return { ok: false, error: `Pegá los tiros de ${meta.rango}.` };
  }

  const tiros = [];
  for (const line of lines) {
    if (TAG_RE.test(line)) {
      const t = parseTag(line);
      if (!t || t.tag !== tagHora) {
        return {
          ok: false,
          error: `La hora la pone el live: ${tagHora}. No pegues otra.`,
        };
      }
      continue;
    }
    const tiro = parseTiro(line);
    if (!tiro) {
      return {
        ok: false,
        error: `No es un tiro de cinta: ${line}. No se aceptan minutos sueltos.`,
      };
    }
    tiros.push(tiro);
  }

  if (!tiros.length) {
    return { ok: false, error: `No hay tiros de ${meta.rango}.` };
  }

  const lockedCrudas = locked.map((t) => t.cruda);
  let cuerpo = tiros;
  if (locked.length && mismasLineas(
    tiros.slice(0, locked.length).map((t) => t.cruda),
    lockedCrudas
  )) {
    cuerpo = tiros.slice(locked.length);
  } else if (locked.length) {
    const tocaLocked = tiros.some((t) => t.m0 < meta.a);
    if (tocaLocked) {
      return {
        ok: false,
        error:
          "Los minutos que ya se confirmaron no coinciden. Rectificá o volvé a ingresar esa parte.",
      };
    }
  }

  if (!cuerpo.length) {
    return {
      ok: false,
      error: `Falta el tramo ${meta.rango}. Lo anterior ya estaba.`,
    };
  }

  for (const t of cuerpo) {
    if (t.wrap) {
      return {
        ok: false,
        error:
          "Ese tiro ya cruzó a la hora siguiente. Esta hora se cierra en Agregar a la cinta.",
      };
    }
    if (t.m0 > minutoAhora) {
      return {
        ok: false,
        error: `El minuto ${pad(t.m0)} todavía no llegó en el reloj.`,
      };
    }
    if (t.m0 < meta.a || t.m0 > meta.b) {
      return {
        ok: false,
        error: `En este paso solo entra ${meta.rango} (${meta.nombre}).`,
      };
    }
  }

  for (let i = 0; i < cuerpo.length; i++) {
    const t = cuerpo[i];
    const prev = i === 0 ? locked[locked.length - 1] : cuerpo[i - 1];
    if (prev && t.m0 < prev.m0) {
      return {
        ok: false,
        error: `El minuto ${pad(t.m0)} viene antes que ${pad(prev.m0)}. La hora se llena hacia adelante.`,
      };
    }
  }

  const last = cuerpo[cuerpo.length - 1];
  return {
    ok: true,
    tag: tagHora,
    etapa,
    meta,
    nuevos: cuerpo,
    todos: [...locked, ...cuerpo],
    luces: lucesDe([...locked, ...cuerpo]),
    ultimoMinuto: last.m1,
    nNuevos: cuerpo.length,
  };
}
