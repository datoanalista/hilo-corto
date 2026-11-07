/**
 * Modo mesa lite: oculta el stream en cuentas NO-WS (2× Chrome).
 * wsPrimaria mantiene video. Por defecto NO corta WebRTC (Show/bono dependen del stream).
 */
const fs = require('fs');
const path = require('path');
const dom = require('./jokerbets-dom.js');

const CONFIG_FILE = path.join(__dirname, '..', '..', 'jokerbets', 'config.json');

const LITE_CSS = `
        html[data-jokerbets-lite="1"] .nano-player,
        html[data-jokerbets-lite="1"] [class*="nano-player__"]:not([class*="bonus"]):not([class*="game-panel"]) {
          position: absolute !important;
          left: -9999px !important;
          width: 1px !important;
          height: 1px !important;
          overflow: hidden !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
        html[data-jokerbets-lite="1"] video {
          position: absolute !important;
          left: -9999px !important;
          width: 1px !important;
          height: 1px !important;
          opacity: 0 !important;
          pointer-events: none !important;
        }
        html[data-jokerbets-lite="1"] #game-panel,
        html[data-jokerbets-lite="1"] #spots,
        html[data-jokerbets-lite="1"] #game-panel-spots,
        html[data-jokerbets-lite="1"] [data-bet-selector],
        html[data-jokerbets-lite="1"] .game-timeout,
        html[data-jokerbets-lite="1"] .timer,
        html[data-jokerbets-lite="1"] .bonus-action-button,
        html[data-jokerbets-lite="1"] [class*="bonus-action-button"],
        html[data-jokerbets-lite="1"] [class*="icon-wheel-action"],
        html[data-jokerbets-lite="1"] [class*="icon-luck-action"],
        html[data-jokerbets-lite="1"] [class*="icon-dice-action"],
        html[data-jokerbets-lite="1"] [class*="game-panel-actions"] {
          visibility: visible !important;
          pointer-events: auto !important;
        }
      `;

let cache = { at: 0, cfg: null };

function readMesaLiteCfg() {
  const now = Date.now();
  if (cache.cfg && now - cache.at < 30_000) return cache.cfg;
  let cfg = {
    enabled: false,
    excluirWs: true,
    excluirBetano: false,
    excluirIds: [],
    detenerStream: false,
  };
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const root = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      const ml = root.mesaLite;
      if (ml === true || ml?.enabled === true) cfg.enabled = true;
      if (ml?.excluirWs === false) cfg.excluirWs = false;
      if (ml?.excluirBetano === true) cfg.excluirBetano = true;
      if (Array.isArray(ml?.excluirIds)) cfg.excluirIds = ml.excluirIds.map(String);
      if (ml?.detenerStream === true) cfg.detenerStream = true;
      if (root.liteVideo === true) cfg.enabled = true;
    }
  } catch (_) {}
  if (process.env.JOKERBETS_LITE_VIDEO === '1') cfg.enabled = true;
  if (process.env.JOKERBETS_LITE_VIDEO === '0') cfg.enabled = false;
  if (process.env.JOKERBETS_LITE_DETENER_STREAM === '1') cfg.detenerStream = true;
  cache = { at: now, cfg };
  return cfg;
}

function isEnabled() {
  return readMesaLiteCfg().enabled;
}

function detenerStreamActivo() {
  return readMesaLiteCfg().detenerStream;
}

/** @param {{ id?: string, wsPrimaria?: boolean, url?: string }} cuenta */
function shouldApplyLite(cuenta) {
  if (!isEnabled()) return false;
  const cfg = readMesaLiteCfg();
  if (cfg.excluirWs && cuenta?.wsPrimaria) return false;
  if (cfg.excluirBetano && /betano/i.test(String(cuenta?.url || ''))) return false;
  if (cfg.excluirIds?.length && cfg.excluirIds.includes(String(cuenta?.id || ''))) return false;
  return true;
}

async function patchLiteInContext(evaluate, detenerStream) {
  return evaluate(
    ({ css, kill }) => {
      document.documentElement.dataset.jokerbetsLite = '1';
      let st = document.getElementById('jokerbets-lite-video-css');
      if (!st) {
        st = document.createElement('style');
        st.id = 'jokerbets-lite-video-css';
        (document.head || document.documentElement).appendChild(st);
      }
      st.textContent = '/* jokerbets-lite */' + css;
      if (!kill) {
        for (const v of document.querySelectorAll('video')) {
          try {
            v.muted = true;
            v.defaultMuted = true;
            v.playsInline = true;
            if (v.paused) v.play().catch(() => {});
          } catch (_) {}
        }
        return { videos: document.querySelectorAll('video').length, kill: false };
      }
      for (const v of document.querySelectorAll('video')) {
        try {
          v.pause();
          v.muted = true;
          const so = v.srcObject;
          if (so && typeof so.getTracks === 'function') {
            for (const t of so.getTracks()) {
              try {
                t.stop();
              } catch (_) {}
            }
          }
          v.removeAttribute('src');
          v.srcObject = null;
          v.load();
        } catch (_) {}
      }
      return { videos: document.querySelectorAll('video').length, kill: true };
    },
    { css: LITE_CSS, kill: !!detenerStream }
  );
}

async function applyLiteVideoFrame(frame, detenerStream) {
  if (!frame) return { ok: false, why: 'sin-frame' };
  try {
    const r = await patchLiteInContext((fn, arg) => frame.evaluate(fn, arg), detenerStream);
    return { ok: true, ...r };
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 80) };
  }
}

async function removeLiteVideoFrame(frame) {
  if (!frame) return { ok: false };
  try {
    await frame.evaluate(() => {
      delete document.documentElement.dataset.jokerbetsLite;
      const st = document.getElementById('jokerbets-lite-video-css');
      if (st) st.remove();
    });
    return { ok: true };
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 80) };
  }
}

async function applyLiteVideoPage(page, cuenta) {
  if (!page || page.isClosed()) return { ok: false, why: 'sin-page' };
  if (!shouldApplyLite(cuenta)) {
    try {
      const frame = await dom.findGameFrame(page);
      if (frame) await removeLiteVideoFrame(frame);
    } catch (_) {}
    try {
      await page.evaluate(() => {
        delete document.documentElement.dataset.jokerbetsLite;
        const st = document.getElementById('jokerbets-lite-video-css');
        if (st) st.remove();
      });
    } catch (_) {}
    return { ok: true, skipped: true, why: 'video-completo-ws' };
  }
  const kill = detenerStreamActivo();
  let iframeOk = false;
  try {
    const frame = await dom.findGameFrame(page);
    if (frame) {
      const r = await applyLiteVideoFrame(frame, kill);
      iframeOk = !!r.ok;
    }
  } catch (_) {}
  let pageOk = false;
  try {
    await patchLiteInContext((fn, arg) => page.evaluate(fn, arg), kill);
    pageOk = true;
  } catch (_) {}
  return { ok: iframeOk || pageOk, iframeOk, pageOk, kill };
}

async function applyLiteAll(contextsMulti) {
  if (!isEnabled() || !contextsMulti?.length) return { ok: false, skipped: true };
  const out = [];
  for (const { cuenta, context } of contextsMulti) {
    let page;
    try {
      page = context.pages().find(p => !p.isClosed()) || null;
    } catch (_) {
      page = null;
    }
    if (!page) {
      out.push({ color: cuenta.color, ok: false, why: 'sin-pestaña' });
      continue;
    }
    const r = await applyLiteVideoPage(page, cuenta);
    out.push({ color: cuenta.color, ws: !!cuenta.wsPrimaria, ...r });
  }
  return { ok: true, cuentas: out };
}

module.exports = {
  isEnabled,
  detenerStreamActivo,
  shouldApplyLite,
  applyLiteVideoFrame,
  applyLiteVideoPage,
  applyLiteAll,
  removeLiteVideoFrame,
};
