/**
 * Global-pool INFO — SI/NO @40 · H4-quorum-6 (lab holdout OK).
 * No boleto · no pool · agrega todos los pools cerca del tip LC.
 */
import { dist, pad } from "./mesa.js";
import { tipSiguienteG } from "./tipProxima.js";

export const GLOBAL_POOL_CUT = 40;
export const GLOBAL_POOL_NEED = 6;
const DELTA = 2;

function nextChip(chips, T) {
  const fut = (chips || []).filter((m) => m > T);
  return fut.length ? Math.min(...fut) : null;
}

function lcTip(luces) {
  const r = tipSiguienteG({ luces: luces || [], minutoAhora: null, modo: "reloj" });
  return r.tip ?? r.target ?? null;
}

function countQuorum(chipsByPool, p10Chips, lc, T, clockT = null) {
  if (lc == null) return 0;
  const Tq =
    clockT != null && !Number.isNaN(clockT)
      ? Math.max(T, Math.floor(clockT))
      : T;
  let n = 0;
  for (const chips of Object.values(chipsByPool || {})) {
    const nc = nextChip(chips, Tq);
    if (nc != null && dist(nc, lc) <= DELTA) n += 1;
  }
  if ((p10Chips || []).length > 0) n += 1;
  return n;
}

/**
 * @returns {null | {
 *   visible: boolean,
 *   waiting?: boolean,
 *   cut: number,
 *   go: boolean,
 *   quorum: number,
 *   need: number,
 *   lc: number | null,
 *   pill: string,
 *   title: string,
 *   lockable: boolean,
 * }}
 */
export function buildGlobalPoolSignal({
  luces = [],
  chipsByPool = {},
  p10Chips = [],
  clockT = 0,
  cut = GLOBAL_POOL_CUT,
  need = GLOBAL_POOL_NEED,
} = {}) {
  const sorted = [...new Set(luces)].sort((a, b) => a - b);
  const poolN = Object.keys(chipsByPool).length;
  const infoReady = poolN >= 4 && sorted.length >= 1;
  const atCut = clockT >= cut;
  const visible = infoReady && atCut;

  if (!visible) return null;

  const prefix = sorted;
  const T = prefix.length ? prefix[prefix.length - 1] : -1;
  const lc = lcTip(prefix);

  if (lc == null && T < 0) {
    return {
      visible: true,
      waiting: true,
      cut,
      go: false,
      quorum: 0,
      need,
      lc: null,
      pill: `@${cut}: …`,
      title: `Global-pool · esperando luces antes de @${cut}`,
      lockable: false,
    };
  }

  const quorum = countQuorum(chipsByPool, p10Chips, lc, T, clockT);
  const go = quorum >= need;
  const relojTxt = `${pad(Math.floor(clockT))}:${pad(Math.round((clockT % 1) * 60))}`;

  return {
    visible: true,
    waiting: false,
    cut,
    go,
    quorum,
    need,
    lc,
    pill: `@${cut}: ${go ? "👍" : "👎"}`,
    title: [
      `Global-pool @${cut} · H4-quorum-${need}`,
      `reloj ${relojTxt} · quorum ${quorum}/${need} · tip LC ${lc != null ? pad(lc) : "—"}`,
      go ? "Seguir" : "Plantate",
    ].join(" · "),
    lockable: false,
  };
}
