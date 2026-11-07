/** Alarma Go! — MP3 desde 3:45 · 38 s. Fade-out gradual. */

const LS_KEY = "hilo-corto:alarma-go";
/** Duración de la alarma (3:45 → ~4:23). */
export const ALARMA_GO_MS = 38_000;
/** Corte del MP3: minuto 3:45 (igual que antes). */
export const ALARMA_GO_START_SEC = 3 * 60 + 45;
/** Ventana de fade-out al final (ms). */
const FADE_OUT_MS = 8_000;
const ALARMA_SRC = "/alarma-go.mp3";

export function loadAlarmaGoPrefs() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { on: false, vol: 0.55 };
    const j = JSON.parse(raw);
    return {
      on: j.on === true,
      vol: Math.max(0, Math.min(1, Number(j.vol) || 0.55)),
    };
  } catch {
    return { on: false, vol: 0.55 };
  }
}

export function saveAlarmaGoPrefs(prefs) {
  try {
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({ on: !!prefs.on, vol: prefs.vol })
    );
  } catch {
    /* ignore */
  }
}

function bag() {
  const g = typeof window !== "undefined" ? window : globalThis;
  if (!g.__hiloAlarmaGo) {
    g.__hiloAlarmaGo = {
      audio: null,
      enabled: false,
      stopTimer: null,
      fadeTimer: null,
      fadeRaf: null,
      pendingReady: null,
      pendingSeeked: null,
    };
  }
  return g.__hiloAlarmaGo;
}

export function setAlarmaGoEnabled(on) {
  const b = bag();
  b.enabled = !!on;
  if (!on) stopAlarmaGo();
}

function getAudio() {
  const b = bag();
  if (!b.audio) {
    b.audio = new Audio(ALARMA_SRC);
    b.audio.preload = "auto";
  }
  return b.audio;
}

function clearPending() {
  const b = bag();
  if (!b.audio) return;
  if (b.pendingReady) {
    b.audio.removeEventListener("canplay", b.pendingReady);
    b.audio.removeEventListener("loadedmetadata", b.pendingReady);
    b.pendingReady = null;
  }
  if (b.pendingSeeked) {
    b.audio.removeEventListener("seeked", b.pendingSeeked);
    b.pendingSeeked = null;
  }
}

function clearFade() {
  const b = bag();
  if (b.fadeTimer) {
    clearTimeout(b.fadeTimer);
    b.fadeTimer = null;
  }
  if (b.fadeRaf) {
    cancelAnimationFrame(b.fadeRaf);
    b.fadeRaf = null;
  }
}

export function stopAlarmaGo() {
  const b = bag();
  if (b.stopTimer) {
    clearTimeout(b.stopTimer);
    b.stopTimer = null;
  }
  clearFade();
  clearPending();
  const kill = (a) => {
    if (!a) return;
    try {
      a.pause();
      a.volume = 0;
    } catch {
      /* ignore */
    }
  };
  kill(b.audio);
  if (typeof document !== "undefined") {
    for (const a of document.querySelectorAll("audio")) {
      if (String(a.src || "").includes("alarma-go")) kill(a);
    }
  }
}

/** Reserva el canal de audio. No reproduce el MP3. */
export function unlockAlarmaGo() {
  if (!bag().enabled) return;
  const a = getAudio();
  const prev = a.volume;
  a.volume = 0;
  const p = a.play();
  const hush = () => {
    try {
      a.pause();
      a.volume = prev;
      a.currentTime = ALARMA_GO_START_SEC;
    } catch {
      /* ignore */
    }
  };
  if (p && typeof p.then === "function") {
    p.then(hush).catch(() => {});
  } else {
    hush();
  }
}

/**
 * Baja el volumen de forma lineal hasta 0 en `fadeMs`.
 */
function startFadeOut(a, peakVol, fadeMs) {
  clearFade();
  const b = bag();
  const t0 = performance.now();
  const peak = Math.max(0.001, Math.min(1, peakVol));

  function tick(now) {
    const elapsed = now - t0;
    const t = Math.min(1, elapsed / fadeMs);
    const gain = peak * (1 - t) * (1 - t);
    a.volume = Math.max(0, gain);
    if (t < 1) {
      b.fadeRaf = requestAnimationFrame(tick);
    } else {
      b.fadeRaf = null;
      a.volume = 0;
    }
  }

  b.fadeRaf = requestAnimationFrame(tick);
}

/**
 * Reproduce el MP3 desde 3:45 durante `ms` (default 38 s).
 * Fade-out gradual al final. Reiniciable.
 * @param {number} vol 0..1
 * @param {number} [ms]
 */
export function playAlarmaGo(vol = 0.55, ms = ALARMA_GO_MS) {
  const b = bag();
  if (!b.enabled) return;
  stopAlarmaGo();
  const a = getAudio();
  const peak = Math.max(0, Math.min(1, vol));
  a.volume = peak;

  const fadeMs = Math.min(FADE_OUT_MS, Math.max(1000, ms * 0.25));
  const holdMs = Math.max(0, ms - fadeMs);

  const armTimers = () => {
    if (b.stopTimer) clearTimeout(b.stopTimer);
    clearFade();
    b.fadeTimer = setTimeout(() => {
      b.fadeTimer = null;
      startFadeOut(a, peak, fadeMs);
    }, holdMs);
    b.stopTimer = setTimeout(() => {
      stopAlarmaGo();
    }, ms);
  };

  const startPlayback = () => {
    if (!bag().enabled) {
      stopAlarmaGo();
      return;
    }
    clearPending();
    a.volume = peak;
    const p = a.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => {
        /* autoplay bloqueado hasta gesto */
      });
    }
    armTimers();
  };

  const seekAndPlay = () => {
    clearPending();
    b.pendingSeeked = () => {
      b.pendingSeeked = null;
      startPlayback();
    };
    a.addEventListener("seeked", b.pendingSeeked, { once: true });
    try {
      a.currentTime = ALARMA_GO_START_SEC;
    } catch {
      startPlayback();
      return;
    }
    window.setTimeout(() => {
      if (!b.pendingSeeked) return;
      clearPending();
      startPlayback();
    }, 120);
  };

  const whenReady = () => {
    b.pendingReady = null;
    seekAndPlay();
  };

  if (a.readyState >= 2) {
    seekAndPlay();
  } else {
    b.pendingReady = whenReady;
    a.addEventListener("canplay", b.pendingReady, { once: true });
    a.load();
  }
}
