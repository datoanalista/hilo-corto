export const NOMBRES_G = {
  1: "Deluxe",
  2: "Luck",
  3: "Dice",
  4: "Show",
};

export const TIPOS_G = [1, 2, 3, 4];

export function esTodos(tipos) {
  const n = tipos instanceof Set ? tipos.size : (tipos || []).length;
  return n === 0 || n === 4;
}

/** Todos, uno, dos o tres. El cuarto tipo vuelve a todos. */
export function toggleTipo(tipos, tipo) {
  const s = new Set(tipos || []);
  if (esTodos(s)) return [tipo];
  if (s.has(tipo)) {
    s.delete(tipo);
    return [...s].sort((a, b) => a - b);
  }
  if (s.size >= 3) return [];
  s.add(tipo);
  return [...s].sort((a, b) => a - b);
}

export function horaBono(row) {
  return row?.hora || "—";
}

export function etiquetaHora(tag) {
  const m = /^h(\d{1,2})-(\d{2})(\d{2})(\d{2})$/i.exec(String(tag || "").trim());
  if (!m) return tag || "—";
  return `${m[2]}/${m[3]} · h${m[1]}`;
}

export function claveTag(tag) {
  const m = /^h(\d{1,2})-(\d{2})(\d{2})(\d{2})$/i.exec(String(tag || "").trim());
  if (!m) return 0;
  const hod = Number(m[1]);
  const dd = Number(m[2]);
  const mm = Number(m[3]);
  const yy = Number(m[4]);
  return yy * 1e7 + mm * 1e5 + dd * 1e3 + hod;
}

export function ordenarRecords(items, col = "x", dir = "desc") {
  const sign = dir === "asc" ? 1 : -1;
  const out = [...(items || [])];
  out.sort((a, b) => {
    let c = 0;
    if (col === "fecha") {
      c =
        claveTag(a.tag) - claveTag(b.tag) ||
        (a.m0 || 0) - (b.m0 || 0) ||
        (a.s0 || 0) - (b.s0 || 0);
    } else if (col === "hora") {
      c =
        claveTag(a.tag) - claveTag(b.tag) ||
        (a.m0 || 0) - (b.m0 || 0) ||
        (a.s0 || 0) - (b.s0 || 0);
    } else if (col === "tipo") {
      c = (a.tipo || 0) - (b.tipo || 0) || (a.x || 0) - (b.x || 0);
    } else {
      c = (a.x || 0) - (b.x || 0) || claveTag(a.tag) - claveTag(b.tag);
    }
    return c * sign;
  });
  return out;
}

export function filtrarRecords(items, { tipos, minX, maxX } = {}) {
  const todos = esTodos(tipos);
  const set = new Set(tipos || []);
  const lo = Number(minX);
  const hi = Number(maxX);
  const loOk = Number.isFinite(lo);
  const hiOk = Number.isFinite(hi);
  return (items || []).filter((r) => {
    if (!todos && !set.has(r.tipo)) return false;
    if (loOk && r.x < lo) return false;
    if (hiOk && r.x > hi) return false;
    return true;
  });
}
