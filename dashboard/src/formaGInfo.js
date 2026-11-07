/**
 * Forma intra-hora de tamaños G (lumen) — segunda vía de apuesta junto a Puerta A.
 * Heurística alineada al depurar-all-4G-detail (reset 40→≤22, oleada, piso).
 */

const RESET_G_MIN = 40;
const RESET_NEXT_MAX = 22;
const RESET_DROP_MIN = 18;

const FORMA_LABEL = {
  sin_datos: "Sin datos (menos de 2 G)",
  reset_reciente: "Reset brusco reciente",
  oleada_subiendo: "Oleada — G subiendo",
  piso_escalera: "Piso escalera (18–36)",
  meseta: "Meseta (G medios estables)",
  pico_aislado: "Pico aislado",
  mixta: "Mixta — sin patrón claro",
};

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

/** Secuencia de lumen solo en tiros G cerrados hasta minuto T. */
export function secuenciaGLumen(tiros, minuto) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const cerrados = (tiros || []).filter((t) => t && t.m0 <= T);
  const out = [];
  for (const t of cerrados) {
    if (String(t.color || "").toUpperCase() !== "G") continue;
    const lm = lumenOf(t);
    if (lm != null) out.push(lm);
  }
  return out;
}

export function esParResetBrusco(prev, next) {
  if (prev == null || next == null) return false;
  return (
    prev >= RESET_G_MIN &&
    (next <= RESET_NEXT_MAX || prev - next >= RESET_DROP_MIN)
  );
}

function resetReciente(seq) {
  if (seq.length < 2) return false;
  const n = seq.length;
  return esParResetBrusco(seq[n - 2], seq[n - 1]);
}

function oleadaSubiendo(seq) {
  if (seq.length < 3) return false;
  const tail = seq.slice(-3);
  for (let i = 1; i < tail.length; i += 1) {
    if (tail[i] < tail[i - 1] - 2) return false;
  }
  return tail[tail.length - 1] > tail[0] + 4;
}

function pisoEscalera(seq) {
  if (seq.length < 3) return false;
  const tail = seq.slice(-3);
  if (tail.some((x) => x > 36 || x < 14)) return false;
  return tail[2] >= tail[1] && tail[1] >= tail[0] && tail[2] > tail[0];
}

function picoAislado(seq) {
  if (seq.length < 2) return false;
  const last = seq[seq.length - 1];
  const prev = seq.slice(0, -1);
  const prevMax = Math.max(...prev);
  const prevMean = prev.reduce((a, b) => a + b, 0) / prev.length;
  return last >= 45 && prevMax <= 32 && last > prevMean + 12;
}

function mesetaMedia(seq) {
  if (seq.length < 2) return false;
  const a = seq[seq.length - 2];
  const b = seq[seq.length - 1];
  if (esParResetBrusco(a, b)) return false;
  return (
    a >= 24 &&
    a <= 42 &&
    b >= 24 &&
    b <= 42 &&
    Math.abs(a - b) <= 10
  );
}

/**
 * Clasifica forma sin filtros de Brillo / interruptor.
 * @returns {{ id: string, label: string, fertil: boolean, seq: number[] }}
 */
export function clasificarFormaG(tiros, minuto) {
  const seq = secuenciaGLumen(tiros, minuto);
  if (seq.length < 2) {
    return {
      id: "sin_datos",
      label: FORMA_LABEL.sin_datos,
      fertil: false,
      seq,
    };
  }
  if (resetReciente(seq)) {
    return {
      id: "reset_reciente",
      label: FORMA_LABEL.reset_reciente,
      fertil: false,
      seq,
    };
  }
  if (picoAislado(seq)) {
    return {
      id: "pico_aislado",
      label: FORMA_LABEL.pico_aislado,
      fertil: false,
      seq,
    };
  }
  if (oleadaSubiendo(seq)) {
    return {
      id: "oleada_subiendo",
      label: FORMA_LABEL.oleada_subiendo,
      fertil: true,
      seq,
    };
  }
  if (pisoEscalera(seq)) {
    return {
      id: "piso_escalera",
      label: FORMA_LABEL.piso_escalera,
      fertil: true,
      seq,
    };
  }
  if (mesetaMedia(seq)) {
    return {
      id: "meseta",
      label: FORMA_LABEL.meseta,
      fertil: true,
      seq,
    };
  }
  return {
    id: "mixta",
    label: FORMA_LABEL.mixta,
    fertil: false,
    seq,
  };
}

/**
 * Rama Puerta A en hora normal (media 40–67): forma intra-hora; no sustituye techo/cola/zona.
 * @param {object} live
 * @param {ReturnType<import('./interruptorPuertaA.js').detallePuertaA>} detPuerta
 */
export function detalleFormaG(live, detPuerta) {
  const T = live?.reloj?.minuto ?? detPuerta?.checks?.minuto ?? 0;
  const base = clasificarFormaG(live?.tiros, T);
  const motivos = [];
  let apuestaOk = base.fertil;

  if (!live?.habilitado || !detPuerta) {
    return { ...base, apuestaOk: false, motivos: ["Sin live"] };
  }

  const c = detPuerta.checks || {};
  const unSoloGordo =
    c.nG === 1 && (live.brillo?.maxG ?? c.meanG ?? 0) >= 85;

  if (!base.fertil) {
    apuestaOk = false;
    if (base.id !== "sin_datos") motivos.push(base.label);
  }

  if (detPuerta.interruptor === "OFF") {
    apuestaOk = false;
    motivos.push("Interruptor OFF");
  }
  if (c.techo) {
    apuestaOk = false;
    motivos.push("Techo Brillo");
  }
  if (c.cola) {
    apuestaOk = false;
    motivos.push("Cola ≥850 / min≥40");
  }
  if (c.nG != null && c.nG < 2) {
    apuestaOk = false;
    motivos.push("Menos de 2 G");
  }
  if (c.meanG != null && c.meanG < 40) {
    apuestaOk = false;
    motivos.push("Media G <40");
  }
  if (c.minuto != null && c.minuto >= 40) {
    apuestaOk = false;
    motivos.push("Minuto ≥40");
  }
  if (unSoloGordo) {
    apuestaOk = false;
    motivos.push("Un solo G gordo");
  }
  if (c.apagada && c.nG < 2) {
    apuestaOk = false;
    motivos.push("Hora apagada");
  }

  if (apuestaOk) {
    motivos.unshift(
      `Puerta A (forma) · ${base.label} · media ${c.meanG != null ? Math.round(c.meanG) : "?"}`
    );
  }

  return {
    ...base,
    apuestaOk,
    motivos,
    ultimosG: base.seq.slice(-4),
  };
}
