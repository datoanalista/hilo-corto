/**
 * Playwright — frame Skywind + gestos mesa (Ronda C).
 * Selectores heurísticos; refinar con DOM_CABLE.txt si cambia el build.
 */

/** Triada genérica legacy (sin icon-*-action); preferir BONO_ACTION. */
const COLOR_INDEX = { rojo: 0, azul: 1, verde: 2 };

/** Capturas bono-scan 2026-10 — índice Skywind por modo y bonoColor. */
const BONO_ACTION = {
  wheel: {
    prefix: 'icon-wheel-action',
    byColor: { azul: 0, verde: 1, rojo: 2 },
  },
  luck: {
    prefix: 'icon-luck-action',
    byColor: { verde: 0, azul: 1, rojo: 2 },
  },
  dice: {
    prefix: 'icon-dice-action',
    byColor: { verde: 0, azul: 1, rojo: 2 },
  },
};

function bonoActionIndex(modo, color) {
  const m = BONO_ACTION[modo];
  if (!m) return null;
  const c = String(color || '').toLowerCase();
  return Object.prototype.hasOwnProperty.call(m.byColor, c) ? m.byColor[c] : null;
}

async function detectBonoModoFrame(frame) {
  try {
    return await frame.evaluate(() => {
      const lite = document.documentElement?.dataset?.jokerbetsLite === '1';
      const area = document.getElementById('game-area');
      const ar = area?.getBoundingClientRect();
      const inArea = el => {
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8) return false;
        if (lite || !ar || ar.height < 40) return true;
        const cy = (r.top + r.bottom) / 2;
        return (
          cy >= ar.top + ar.height * 0.12 &&
          cy <= ar.top + ar.height * 0.96 &&
          r.left >= ar.left - 48 &&
          r.right <= ar.right + 48
        );
      };
      const modes = [
        ['dice', 'icon-dice-action'],
        ['luck', 'icon-luck-action'],
        ['wheel', 'icon-wheel-action'],
      ];
      for (const [modo, prefix] of modes) {
        let nArea = 0;
        let nDoc = 0;
        for (let i = 0; i < 3; i += 1) {
          const re = new RegExp(prefix + '_' + i + '(\\s|$)');
          const nodes = Array.from(document.querySelectorAll('[class*="' + prefix + '"]')).filter(el =>
            re.test((el.className || '').toString())
          );
          if (nodes.some(inArea)) nArea += 1;
          if (nodes.length) nDoc += 1;
        }
        if (nArea >= 3 || nDoc >= 3) return { modo, prefix };
      }
      return { modo: null, prefix: null };
    });
  } catch (_) {
    return { modo: null, prefix: null };
  }
}

/** Cierra panel PREMIOS / reglas si tapa la mesa (clics bot lo abrían). */
async function cerrarOverlaysJuego(frame) {
  try {
    await frame.evaluate(() => {
      const txt = document.body?.innerText || '';
      if (/toma tu decisi|make your decision/i.test(txt)) return;
      const premiosAbierto =
        /PREMIOS/i.test(txt) &&
        (/PAGA\s*\d|MEJORA DE COLOR|COMBINACI/i.test(txt) || /paytable|prize-table/i.test(
          document.documentElement.innerHTML.slice(0, 120000)
        ));
      if (!premiosAbierto) return;
      const closeCandidates = Array.from(
        document.querySelectorAll(
          'button, [role="button"], [class*="close"], [class*="Close"], [class*="modal"] button'
        )
      );
      for (const el of closeCandidates) {
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8) continue;
        const cls = (el.className || '').toString().toLowerCase();
        const label = (el.getAttribute('aria-label') || '').toLowerCase();
        const t = (el.textContent || '').trim();
        if (
          cls.includes('close') ||
          label.includes('close') ||
          label.includes('cerrar') ||
          t === '×' ||
          t === 'X' ||
          t === '✕'
        ) {
          el.click();
          return;
        }
      }
    });
    await frame.waitForTimeout(120);
  } catch (_) {}
}

/** Clic vía DOM (Betano/lite: Playwright a veces no ve el icono blinked). */
async function clickBonoActionDom(frame, prefix, idx) {
  try {
    return await frame.evaluate(
      ({ prefix: pfx, idx: i }) => {
        const token = pfx + '_' + i;
        const tryRoot = root => {
          const sels = [
            '[class*="' + token + '"][class*="_blinked"]',
            '.bonus-action-button:has([class*="' + token + '"][class*="_blinked"])',
            '.bonus-action-button [class*="' + token + '"]',
            '[class*="' + token + '"]:not([class*="_disabled"])',
          ];
          for (const sel of sels) {
            let el = null;
            try {
              el = root.querySelector(sel);
            } catch (_) {}
            if (!el) continue;
            const btn = el.closest('.bonus-action-button') || el.closest('button') || el;
            try {
              btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            } catch (_) {}
            try {
              btn.click();
            } catch (_) {}
            return { ok: true, metodo: 'dom:' + sel.slice(0, 56) };
          }
          return { ok: false };
        };
        const area = document.getElementById('game-area');
        if (area) {
          const a = tryRoot(area);
          if (a.ok) return a;
        }
        return tryRoot(document);
      },
      { prefix, idx }
    );
  } catch (e) {
    return { ok: false, reason: String(e.message || e).slice(0, 60) };
  }
}

/** Clic Playwright solo en #game-area (nunca mouse.page — abre PREMIOS). */
async function clickBonoActionIcon(frame, _page, prefix, idx) {
  const token = prefix + '_' + idx;
  let lite = false;
  try {
    lite =
      (await frame
        .evaluate(() => document.documentElement?.dataset?.jokerbetsLite === '1')
        .catch(() => false)) === true;
  } catch (_) {}
  const scope = lite ? '' : '#game-area ';
  const selectors = [
    scope + '[class*="' + token + '"][class*="_blinked"]',
    scope + '.bonus-action-button:has([class*="' + token + '"][class*="_blinked"])',
    scope +
      '.bonus-action-button:has([class*="' +
      token +
      '"]):not(:has([class*="_disabled"]))',
    scope + '[class*="' + token + '"]:not([class*="_disabled"])',
    '[class*="' + token + '"][class*="_blinked"]',
    '.bonus-action-button:has([class*="' + token + '"])',
  ];

  for (const sel of selectors) {
    try {
      const loc = frame.locator(sel).first();
      const vis = await loc.isVisible({ timeout: 500 }).catch(() => false);
      if (!vis && !lite) continue;
      await loc.click({ timeout: 5000, force: lite || !vis });
      await frame.waitForTimeout(120);
      await loc.click({ timeout: 2500, force: true }).catch(() => {});
      return { ok: true, metodo: 'pw:' + sel.slice(0, 72) };
    } catch (_) {}
  }
  const domHit = await clickBonoActionDom(frame, prefix, idx);
  if (domHit.ok) return domHit;
  return { ok: false, reason: 'sin-clic-pw' };
}

async function verificarBonoAction(frame, prefix, idx) {
  try {
    return await frame.evaluate(
      ({ prefix: pfx, idx: i }) => {
        const lite = document.documentElement?.dataset?.jokerbetsLite === '1';
        const txt = document.body?.innerText || '';
        const enDecision = /toma tu decisi|make your decision/i.test(txt);
        const panel = document.getElementById('game-panel');
        const enBonus = panel?.classList.contains('game-panel-desktop_hidden');
        const area = document.getElementById('game-area');
        const ar = area?.getBoundingClientRect();
        const els = Array.from(document.querySelectorAll('[class*="' + pfx + '"]')).filter(el =>
          new RegExp(pfx + '_' + i + '(\\s|$)').test((el.className || '').toString())
        );
        const inPanel = el => {
          if (lite || !ar) return true;
          const r = el.getBoundingClientRect();
          return r.width > 4 && r.left >= ar.left + ar.width * 0.05;
        };
        const mine = els.filter(inPanel);
        const locked = mine.some(el => {
          const cls = (el.className || '').toString();
          return /highlighted/i.test(cls) && !/disabled/i.test(cls) && !/blinked/i.test(cls);
        });
        if (locked) {
          return { ok: true, detalle: pfx + '_' + i + ' highlighted' };
        }
        const siblings = Array.from(document.querySelectorAll('[class*="' + pfx + '"]')).filter(el =>
          new RegExp(pfx + '_([012])(\\s|$)').test((el.className || '').toString())
        );
        const stillBlink = siblings.filter(el => /blinked/i.test((el.className || '').toString())).length;
        const mineHighlighted = mine.some(el => {
          const cls = (el.className || '').toString();
          return /highlighted/i.test(cls);
        });
        if (stillBlink >= 1 && mineHighlighted) {
          return { ok: true, detalle: pfx + '_' + i + ' highlighted+blink-sibling' };
        }
        if (!enDecision && !enBonus) {
          return { ok: true, detalle: 'decision-cerrada' };
        }
        return { ok: false, detalle: pfx + '_' + i + ' sin-marca' };
      },
      { prefix, idx }
    );
  } catch (e) {
    return { ok: false, detalle: String(e.message || e).slice(0, 80) };
  }
}

function logBot(msg) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  console.log(
    '[' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + '] [bot] ' + msg
  );
}

async function findGameFrame(page) {
  if (!page || page.isClosed()) return null;
  const frames = page.frames();
  /** Mesa de apuestas vive en Skywind; no usar un frame que solo tenga SALDO en texto. */
  let best = null;
  let bestScore = -1;
  for (const f of frames) {
    try {
      const nCentro = await f.locator('[data-bet-selector="bonusType"]').count();
      if (nCentro <= 0) continue;
      let score = frameScore(f.url()) + 20;
      const nIcon = await f
        .locator(
          '[class*="icon-luck-action"], [class*="icon-wheel-action"], [class*="icon-dice-action"]'
        )
        .count();
      if (nIcon >= 3) score += 25;
      if (score > bestScore) {
        bestScore = score;
        best = f;
      }
    } catch (_) {}
  }
  if (best) return best;
  for (const f of frames) {
    try {
      if ((await f.locator('[data-bet-selector="bonusType"]').count()) > 0) return f;
    } catch (_) {}
  }
  for (const f of frames) {
    const u = (f.url() || '').toLowerCase();
    if (!u.includes('sw420101') && !u.includes('live-client-jokers')) continue;
    try {
      if ((await f.locator('#spots, [data-bet-selector="1"]').count()) > 0) return f;
    } catch (_) {}
  }
  for (const f of frames) {
    const u = (f.url() || '').toLowerCase();
    if (u.includes('socket') || u.includes('cookie') || u.length < 12) continue;
    if (u.includes('sw420101') || u.includes('skywind') || /joker|wheel/.test(u)) {
      return f;
    }
  }
  for (const f of frames) {
    const u = (f.url() || '').toLowerCase();
    try {
      const snippet = await f.locator('body').innerText({ timeout: 800 });
      if (
        /SALDO|APUESTA|PREMIO/i.test(snippet) &&
        (u.includes('sw420101') || u.includes('live-client-jokers'))
      ) {
        return f;
      }
    } catch (_) {}
  }
  return page.mainFrame();
}

async function textoVisible(frame, re, timeoutMs = 800) {
  try {
    const loc = frame.locator('body').getByText(re, { exact: false }).first();
    await loc.waitFor({ state: 'visible', timeout: timeoutMs });
    return true;
  } catch (_) {
    return false;
  }
}

function parseBarraTexto(body) {
  const out = { saldo: null, apuesta: null, premio: null };
  if (!body) return out;
  const norm = String(body).replace(/\u00a0/g, ' ');

  function pick(re) {
    const m = re.exec(norm);
    if (!m) return null;
    const n = m[1];
    const suf = (m[2] || '').toUpperCase();
    return n + suf;
  }

  if (!out.saldo) {
    const lines = norm.split(/\n/);
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i].trim();
      if (!/^SALDO\b/i.test(line) && !/^Saldo\b/i.test(line)) continue;
      let m = /\$?\s*([\d.,]+)\s*(K|M)?/i.exec(line);
      if (!m && lines[i + 1]) {
        m = /\$?\s*([\d.,]+)\s*(K|M)?/i.exec(lines[i + 1].trim());
      }
      if (m) {
        out.saldo = m[1] + (m[2] || '').toUpperCase();
        break;
      }
    }
  }

  out.saldo =
    out.saldo ||
    pick(/SALDO[\s\S]{0,120}?\$\s*([\d.,]+)\s*(K|M)?/i) ||
    pick(/(?:Balance|Saldo)[\s\S]{0,48}?\$\s*([\d.,]+)\s*(K|M)?/i);
  out.apuesta =
    pick(/APUESTA[\s\S]{0,32}?\$?\s*([\d.,]+)\s*(K|M)?/i) ||
    pick(/(?:Bet|Aposta)[\s\S]{0,24}?\$?\s*([\d.,]+)\s*(K|M)?/i);
  out.premio =
    pick(/PREMIO[\s\S]{0,32}?\$?\s*([\d.,]+)\s*(K|M)?/i) ||
    pick(/(?:Win|Prize)[\s\S]{0,24}?\$?\s*([\d.,]+)\s*(K|M)?/i);
  return out;
}

async function readBarraSaldo(frame) {
  const out = { saldo: null, apuesta: null, premio: null, raw: '', frameUrl: '' };
  try {
    const body = await frame.locator('body').innerText({ timeout: 3000 });
    out.raw = body.slice(0, 4000);
    out.frameUrl = frame.url() || '';
    Object.assign(out, parseBarraTexto(body));
  } catch (_) {}
  return out;
}

function scoreFrameUrl(url) {
  const u = (url || '').toLowerCase();
  if (u.includes('sw420101') || u.includes('skywind')) return 40;
  if (u.includes('joker') || u.includes('live-casino') || u.includes('live/games')) return 30;
  if (u.includes('betano')) return 25;
  if (u.includes('jugabet')) return 20;
  if (u.startsWith('http')) return 10;
  return 0;
}

/** Recorre página + todos los iframes (SALDO suele estar en el frame del juego). */
async function readBarraSaldoFromPage(page) {
  const vacio = { saldo: null, apuesta: null, premio: null, frameUrl: null };
  if (!page || page.isClosed()) return vacio;
  const candidatos = [];
  try {
    candidatos.push({ url: page.url(), frame: page.mainFrame() });
  } catch (_) {}
  for (const f of page.frames()) {
    try {
      if (!candidatos.some(c => c.frame === f)) candidatos.push({ url: f.url(), frame: f });
    } catch (_) {}
  }
  candidatos.sort((a, b) => scoreFrameUrl(b.url) - scoreFrameUrl(a.url));

  let mejorApuesta = null;
  for (const { url, frame } of candidatos) {
    try {
      const body = await frame.locator('body').innerText({ timeout: 2500 });
      const p = parseBarraTexto(body);
      // No cortar en APUESTA $0 del wrapper (Betano): hace falta seguir al iframe del juego.
      if (p.saldo) {
        return { ...p, frameUrl: url || '' };
      }
      if (p.apuesta && !mejorApuesta) {
        mejorApuesta = { ...p, frameUrl: url || '' };
      }
    } catch (_) {}
  }
  return mejorApuesta || vacio;
}

const CHIP_LABELS = ['50', '250', '500', '2.5K', '10K', '50K'];

async function chipStripState(frame) {
  try {
    return await frame.evaluate((LABELS) => {
      const spots = document.getElementById('spots');
      const looksSelected = (el) => {
        let p = el;
        for (let d = 0; d < 5 && p; d += 1) {
          const cls = (p.className || '').toString().toLowerCase();
          if (/selected|active|current|picked|highlight|chosen|_on\b|-on\b/.test(cls)) {
            return true;
          }
          const aria =
            p.getAttribute('aria-selected') ||
            p.getAttribute('aria-pressed') ||
            p.getAttribute('aria-checked');
          if (aria === 'true') return true;
          p = p.parentElement;
        }
        try {
          const st = getComputedStyle(el);
          const ow = parseFloat(st.outlineWidth || '0');
          if (ow >= 2.5) return true;
          const bs = st.boxShadow || '';
          if (bs !== 'none' && /rgb\(255|gold|yellow/i.test(bs)) return true;
        } catch (_) {}
        return false;
      };
      const labelOf = (el) => {
        const dv = el.getAttribute('data-value') || el.getAttribute('data-denom');
        if (dv && LABELS.includes(String(dv))) return String(dv);
        const aria = el.getAttribute('aria-label') || el.getAttribute('title') || '';
        for (const L of LABELS) {
          if (aria === L || new RegExp(`\\b${L}\\b`).test(aria)) return L;
        }
        if (el.children.length > 4) return null;
        const raw = (el.textContent || '').replace(/\u00a0/g, ' ').trim();
        if (LABELS.includes(raw)) return raw;
        return null;
      };
      const vh = window.innerHeight;
      const items = [];
      for (const el of document.querySelectorAll(
        '[class*="chip" i], [class*="Chip"], [class*="denom" i], [class*="stake" i], [data-value], [data-denom], button, [role="button"], div, span'
      )) {
        if (spots && spots.contains(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 16 || r.height < 16 || r.top < vh * 0.52) continue;
        const lab = labelOf(el);
        if (!lab) continue;
        items.push({
          lab,
          selected: looksSelected(el),
          x: r.left + r.width / 2,
          y: r.top + r.height / 2,
          parentKey: el.parentElement ? el.parentElement.className : '',
        });
      }
      const groups = new Map();
      for (const it of items) {
        const k = it.parentKey;
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(it);
      }
      let strip = null;
      for (const arr of groups.values()) {
        const labs = new Set(arr.map(a => a.lab));
        if (labs.has('50') && labs.has('250')) {
          strip = arr;
          break;
        }
      }
      if (!strip && items.length >= 3) {
        const byX = [...items].sort((a, b) => a.x - b.x);
        for (let i = 0; i <= byX.length - 3; i += 1) {
          const slice = byX.slice(i, i + 6);
          const labs = new Set(slice.map(s => s.lab));
          if (labs.has('50') && labs.has('250')) {
            strip = slice;
            break;
          }
        }
      }
      if (!strip) {
        return { ok: false, valor: null, detalle: 'sin-tira', click50: null };
      }
      const sel = strip.filter(c => c.selected);
      let valor = null;
      if (sel.length >= 1) valor = sel[0].lab;
      const c50 = strip.find(c => c.lab === '50');
      return {
        ok: valor === '50',
        valor,
        detalle: valor ? 'marcada-' + valor : 'ninguna-marcada',
        click50: c50 ? { x: c50.x, y: c50.y } : null,
      };
    }, CHIP_LABELS);
  } catch (e) {
    return { ok: false, valor: null, detalle: String(e.message || e).slice(0, 48), click50: null };
  }
}

async function chipSeleccionado(frame) {
  const sw = await chipSkywindState(frame);
  if (sw.found) return { valor: sw.valor, detalle: sw.detalle };
  const s = await chipStripState(frame);
  return { valor: s.valor, detalle: s.detalle };
}

/** Skywind: chip-1 = $50, chip-2 = $250 (Jugabet + Betano). */
async function chipSkywindState(frame) {
  try {
    return await frame.evaluate(() => {
      const pick = (n) =>
        document.querySelector(`use.chip-image.chip-${n}, .chip-image.chip-${n}`);
      const c1 = pick(1);
      const c2 = pick(2);
      if (!c1) return { found: false, ok: false, valor: null, detalle: 'no-skywind-chips', click50: null };

      const clsOf = (el) => {
        if (!el) return '';
        const raw = el.className;
        return (typeof raw === 'string' ? raw : raw?.baseVal || '').toString();
      };

      const looksSelected = (start) => {
        let p = start;
        for (let d = 0; d < 10 && p; d += 1) {
          const cls = clsOf(p).toLowerCase();
          if (/selected|active|current|pressed|picked|highlight|is-active/.test(cls)) {
            return true;
          }
          const aria =
            p.getAttribute?.('aria-selected') ||
            p.getAttribute?.('aria-pressed') ||
            p.getAttribute?.('aria-checked');
          if (aria === 'true') return true;
          p = p.parentElement;
        }
        try {
          const host =
            start.closest?.('svg.chip-svg, button, [role="button"], [class*="chip"]') ||
            start.parentElement;
          if (host) {
            const st = getComputedStyle(host);
            if (parseFloat(st.outlineWidth || '0') >= 2.5) return true;
            const bs = st.boxShadow || '';
            if (bs !== 'none' && /rgb\(255|gold|yellow/i.test(bs)) return true;
          }
        } catch (_) {}
        return false;
      };

      const s1 = looksSelected(c1);
      const s2 = c2 ? looksSelected(c2) : false;
      let valor = null;
      if (s1 && !s2) valor = '50';
      else if (s2) valor = '250';
      else if (s1) valor = '50';

      const click50 = (() => {
        let el = c1.closest?.('svg.chip-svg, button, [role="button"]') || c1.parentElement || c1;
        for (let i = 0; i < 8 && el; i += 1) {
          const r = el.getBoundingClientRect();
          if (r.width >= 22 && r.height >= 22) {
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
          }
          el = el.parentElement;
        }
        const r = c1.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      })();

      return {
        found: true,
        ok: valor === '50',
        valor,
        detalle: `skywind chip-1${s1 ? '*' : ''} chip-2${s2 ? '*' : ''}`,
        click50,
      };
    });
  } catch (e) {
    return {
      found: false,
      ok: false,
      valor: null,
      detalle: String(e.message || e).slice(0, 40),
      click50: null,
    };
  }
}

async function clickSkywindChip50(frame) {
  const tries = [
    () => frame.locator('use.chip-image.chip-1').first(),
    () => frame.locator('.chip-image.chip-1').first(),
    () =>
      frame.locator('svg.chip-svg').filter({ has: frame.locator('use.chip-image.chip-1') }).first(),
  ];
  for (const fn of tries) {
    try {
      const loc = fn();
      if ((await loc.count()) > 0 && (await loc.isVisible({ timeout: 500 }))) {
        await loc.click({ timeout: 5000, force: true });
        return { ok: true, metodo: 'skywind-chip-1' };
      }
    } catch (_) {}
  }
  const st = await chipSkywindState(frame);
  if (st.click50) {
    await clickChip50At(frame, st.click50);
    return { ok: true, metodo: 'skywind-coords' };
  }
  return { ok: false, metodo: '' };
}

/** Respaldo: texto “50” en banda inferior. */
async function clickChip50Playwright(frame) {
  try {
    const sky = await clickSkywindChip50(frame);
    if (sky.ok) return sky;
    const minY = await frame.evaluate(() => window.innerHeight * 0.58);
    const candidatos = [
      frame.locator('[class*="chip" i]').filter({ hasText: /^50$/ }),
      frame.getByText('50', { exact: true }),
      frame.locator('[aria-label="50"], [title="50"], [data-value="50"], [data-denom="50"]'),
    ];
    for (const loc of candidatos) {
      const n = await loc.count();
      for (let i = 0; i < n; i += 1) {
        const el = loc.nth(i);
        const box = await el.boundingBox();
        if (!box || box.y < minY || box.width > 120 || box.height > 120) continue;
        await el.click({ timeout: 4000 });
        return { ok: true, metodo: 'pw-50' };
      }
    }
  } catch (_) {}
  return { ok: false, metodo: '' };
}

async function frameEsMesaJuego(frame) {
  try {
    const u = (frame.url() || '').toLowerCase();
    if (u.includes('sw420101') || u.includes('live-client-jokers')) return true;
    return (await frame.locator('#spots, [data-bet-selector="bonusType"]').count()) > 0;
  } catch (_) {
    return false;
  }
}

async function clickChip50At(frame, point) {
  if (!point) return false;
  try {
    await frame.mouse.click(point.x, point.y);
    return true;
  } catch (_) {
    try {
      return await frame.evaluate(({ x, y }) => {
        const el = document.elementFromPoint(x, y);
        if (!el) return false;
        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
        return true;
      }, point);
    } catch (_) {
      return false;
    }
  }
}

async function leerChip50Ok(frame) {
  const sw = await chipSkywindState(frame);
  if (sw.found) return sw;
  return chipStripState(frame);
}

/** Ficha $50 = `.chip-image.chip-1` (Skywind). No apostar si sigue chip-2 ($250). */
async function ensureChip50(frame) {
  let st = await leerChip50Ok(frame);
  const antesVal = st.valor;
  if (st.ok && st.valor === '50') {
    return { ok: true, antes: '50', despues: '50', detalle: st.detalle, frameUrl: '' };
  }

  for (let intento = 0; intento < 5; intento += 1) {
    await clickSkywindChip50(frame);
    await frame.waitForTimeout(320);
    st = await leerChip50Ok(frame);
    if (st.ok && st.valor === '50') {
      return {
        ok: true,
        antes: antesVal,
        despues: '50',
        detalle: 'clic-' + (intento + 1) + '·' + (st.detalle || ''),
        frameUrl: '',
      };
    }
    if (st.valor === '250') {
      await clickSkywindChip50(frame);
      await frame.waitForTimeout(280);
      st = await leerChip50Ok(frame);
      if (st.ok) {
        return {
          ok: true,
          antes: antesVal,
          despues: '50',
          detalle: 'clic-250→50·' + (st.detalle || ''),
          frameUrl: '',
        };
      }
    }
  }

  const swFin = await chipSkywindState(frame);
  if (swFin.found && swFin.valor !== '250') {
    return {
      ok: true,
      antes: antesVal,
      despues: swFin.valor || '50?',
      detalle: 'skywind-tras-clic·' + (swFin.detalle || ''),
      frameUrl: '',
    };
  }

  st = await leerChip50Ok(frame);
  return {
    ok: false,
    antes: antesVal,
    despues: st.valor,
    detalle: st.detalle || 'sin-50',
    frameUrl: '',
  };
}

function frameUrlOk(u) {
  const s = (u || '').toLowerCase();
  if (!s || s.startsWith('about:') || s === 'about:blank') return false;
  if (
    s.includes('socket') ||
    s.includes('cookie') ||
    s.includes('regtel') ||
    s.includes('uuidksinc') ||
    s.includes('matchx')
  ) {
    return false;
  }
  return true;
}

function frameScore(u) {
  const s = (u || '').toLowerCase();
  if (s.includes('sw420101') || s.includes('live-client-jokers')) return 100;
  if (s.includes('skywind') || s.includes('joker')) return 80;
  if (s.includes('betano')) return 70;
  if (s.includes('jugabet')) return 40;
  return 10;
}

function framesParaFicha(page, gameFrame) {
  const out = [];
  const push = (f) => {
    if (!f || out.includes(f)) return;
    try {
      if (!frameUrlOk(f.url())) return;
    } catch (_) {
      return;
    }
    out.push(f);
  };
  push(gameFrame);
  if (page && !page.isClosed()) {
    for (const f of page.frames()) push(f);
  }
  out.sort((a, b) => frameScore(b.url()) - frameScore(a.url()));
  return out;
}

async function ensureChip50ForPage(page, gameFrame) {
  const raw = framesParaFicha(page, gameFrame);
  const frames = [];
  for (const f of raw) {
    if (await frameEsMesaJuego(f)) frames.push(f);
  }
  if (!frames.length && gameFrame) frames.push(gameFrame);
  let last = { ok: false, detalle: 'sin-frame', antes: null, despues: null };
  for (const f of frames) {
    const r = await ensureChip50(f);
    r.frameUrl = (f.url() || '').slice(0, 90);
    last = r;
    if (r.ok) return r;
  }
  return last;
}

async function clickChip50(frame) {
  const r = await ensureChip50(frame);
  return r.ok;
}

async function clickCenterCircle(page, gameFrame, veces = 3) {
  const nClics = Math.max(1, Math.min(Number(veces) || 1, 3));
  const chipOk = await ensureChip50ForPage(page, gameFrame);
  if (!chipOk.ok) return 0;
  let ok = 0;
  for (let i = 0; i < nClics; i += 1) {
    let clicked = false;
    try {
      const loc = gameFrame
        .locator('[data-bet-selector="bonusType"]:not(.spots-part-button_disabled)')
        .first();
      if (await loc.isVisible({ timeout: 700 })) {
        await loc.click({ timeout: 4000 });
        clicked = true;
      }
    } catch (_) {}
    if (!clicked) break;
    ok += 1;
    if (i + 1 < nClics) await gameFrame.waitForTimeout(280);
  }
  return ok;
}

/** Manual ×3: un toque a chip 50 sin comprobar DOM; no bloquea. */
async function prepChip50Manual(page, gameFrame) {
  const raw = framesParaFicha(page, gameFrame);
  let frame = gameFrame;
  for (const f of raw) {
    if (await frameEsMesaJuego(f)) {
      frame = f;
      break;
    }
  }
  try {
    await clickSkywindChip50(frame);
  } catch (_) {}
}

/**
 * Manual ×3: sin validar chip ni ventana; un intento de centro (force).
 * El humano dispara en cuenta regresiva — no hay reintentos ni lectura “ok chip”.
 */
async function clickCenterCircleManual(page, gameFrame, veces = 1) {
  const nClics = Math.max(1, Math.min(Number(veces) || 1, 3));
  await prepChip50Manual(page, gameFrame);
  let ok = 0;
  for (let i = 0; i < nClics; i += 1) {
    let clicked = false;
    try {
      const loc = gameFrame
        .locator('[data-bet-selector="bonusType"]:not(.spots-part-button_disabled)')
        .first();
      if ((await loc.count()) > 0) {
        await loc.click({ timeout: 2200, force: true });
        clicked = true;
      }
    } catch (_) {}
    if (!clicked) {
      try {
        const loc2 = gameFrame.locator('[data-bet-selector="bonusType"]').first();
        if ((await loc2.count()) > 0) {
          await loc2.click({ timeout: 1200, force: true });
          clicked = true;
        }
      } catch (_) {}
    }
    if (!clicked) break;
    ok += 1;
    if (i + 1 < nClics) {
      try {
        await gameFrame.waitForTimeout(100);
      } catch (_) {}
    }
  }
  return ok;
}

async function pantallaDecision(frame) {
  try {
    return await frame.evaluate(() => {
      const lite = document.documentElement?.dataset?.jokerbetsLite === '1';
      const triadaTemprana = (() => {
        const prefixes = ['icon-wheel-action', 'icon-luck-action', 'icon-dice-action'];
        for (const pfx of prefixes) {
          let n = 0;
          let blink = 0;
          for (let i = 0; i < 3; i += 1) {
            const re = new RegExp(pfx + '_' + i + '(\\s|$)');
            const el = Array.from(document.querySelectorAll('[class*="' + pfx + '"]')).find(x =>
              re.test((x.className || '').toString())
            );
            if (el) {
              n += 1;
              if (/blinked/i.test((el.className || '').toString())) blink += 1;
            }
          }
          if (blink >= 2 || (n >= 3 && blink >= 1)) return true;
        }
        return false;
      })();
      if (triadaTemprana) return true;

      const txt = document.body?.innerText || '';
      const decisionText = /toma tu decisi|make your decision|choose your (color|bonus)/i.test(
        txt
      );
      const premiosSolo =
        /PREMIOS/i.test(txt) &&
        /PAGA|MEJORA DE COLOR|COMBINACI/i.test(txt) &&
        !decisionText;
      if (premiosSolo) return false;

      const panel = document.getElementById('game-panel');
      const panelBonus = panel?.classList.contains('game-panel-desktop_hidden');
      const area = document.getElementById('game-area');
      const ar = area?.getBoundingClientRect();
      const inGameArea = el => {
        if (lite) return true;
        if (!ar || ar.height < 40) return true;
        const r = el.getBoundingClientRect();
        if (r.width < 8 || r.height < 8) return false;
        const cy = (r.top + r.bottom) / 2;
        return (
          cy >= ar.top + ar.height * 0.12 &&
          cy <= ar.top + ar.height * 0.96 &&
          r.left >= ar.left - 32 &&
          r.right <= ar.right + 32
        );
      };
      const prefixes = ['icon-wheel-action', 'icon-luck-action', 'icon-dice-action'];
      const stats = pfx => {
        let n = 0;
        let blink = 0;
        for (let i = 0; i < 3; i += 1) {
          const el = Array.from(document.querySelectorAll('[class*="' + pfx + '_' + i + '"]')).find(
            inGameArea
          );
          if (el) n += 1;
          if (el && /blinked/i.test((el.className || '').toString())) blink += 1;
        }
        return { n, blink };
      };
      const triadaEnMesa = prefixes.some(pfx => stats(pfx).n >= 3);
      const triadaBlink = prefixes.some(pfx => stats(pfx).blink >= 2);
      const botonesColor = Array.from(
        document.querySelectorAll('#game-area [class*="bonus-action-button"]')
      ).filter(el => {
        const r = el.getBoundingClientRect();
        return r.width > 20 && r.height > 20;
      }).length;

      if (panelBonus && (triadaEnMesa || triadaBlink || decisionText)) return true;
      if (decisionText && (triadaEnMesa || triadaBlink || botonesColor >= 3)) return true;
      if (decisionText && lite) return true;
      if (!decisionText) return false;
      return triadaEnMesa || triadaBlink || botonesColor >= 3;
    });
  } catch (_) {
    return false;
  }
}

/**
 * Manual ×3 (usuario en contador): no exige Hagan juego ni centro habilitado.
 * Solo evita clic en pantalla TOMA TU DECISIÓN (bono color).
 * @returns {Promise<string|null>} motivo de bloqueo o null si puede disparar
 */
async function bloqueoApuestaManual(frame) {
  try {
    return await frame.evaluate(() => {
      const txt = document.body?.innerText || '';
      if (/toma tu decisi|make your decision|choose your (color|bonus)/i.test(txt)) {
        return 'bono-decision';
      }
      return null;
    });
  } catch (e) {
    return String(e.message || e).slice(0, 40);
  }
}

/** Ventana ~12s: mesa abierta, sin ESPERE ni bono decisión (apuesta-scan). */
async function ventanaApuestaAbierta(frame) {
  try {
    return await frame.evaluate(() => {
      const txt = document.body?.innerText || '';
      if (/espere[\s\S]{0,24}siguiente|espera[\s\S]{0,24}siguiente|wait[\s\S]{0,16}next/i.test(txt)) {
        return { ok: false, why: 'espere-ronda' };
      }
      if (/toma tu decisi|make your decision/i.test(txt)) {
        return { ok: false, why: 'bono-decision' };
      }
      const panel = document.getElementById('game-panel');
      if (panel?.classList.contains('game-panel-desktop_hidden')) {
        return { ok: false, why: 'panel-bonus' };
      }
      const spotsRoot = document.getElementById('spots') || document.getElementById('game-panel-spots');
      if (!spotsRoot) return { ok: false, why: 'sin-spots-dom' };
      const center = document.querySelector('[data-bet-selector="bonusType"]');
      if (center?.classList.contains('spots-part-button_disabled')) {
        return { ok: false, why: 'centro-disabled' };
      }
      const hagan = /hagan\s+juego|place your bets/i.test(txt);
      return { ok: true, why: hagan ? 'hagan-juego' : 'mesa-abierta', haganJuego: hagan };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 40) };
  }
}

/** Mientras gira / entre rondas — no clicar apuesta aún. */
async function esperaSiguienteRonda(frame, waitMs = 350) {
  const w = Math.max(50, Number(waitMs) || 350);
  return (
    (await textoVisible(frame, /espere.*siguiente/i, w)) ||
    (await textoVisible(frame, /espera.*siguiente/i, w)) ||
    (await textoVisible(frame, /wait.*next/i, w)) ||
    (await textoVisible(frame, /next round/i, w))
  );
}

/** Panel de apuestas visible y centro no deshabilitado. */
async function mesaListaParaApostar(frame) {
  try {
    return await frame.evaluate(() => {
      const txt = document.body?.innerText || '';
      if (/espere[\s\S]{0,24}siguiente|espera[\s\S]{0,24}siguiente|wait[\s\S]{0,16}next/i.test(txt)) {
        return { ok: false, why: 'espera-ronda' };
      }
      const panel = document.getElementById('game-panel');
      if (panel?.classList.contains('game-panel-desktop_hidden')) {
        return { ok: false, why: 'panel-oculto-bonus' };
      }
      const spotsRoot = document.getElementById('spots') || document.getElementById('game-panel-spots');
      if (!spotsRoot) {
        return { ok: false, why: 'sin-spots-dom' };
      }
      const center = document.querySelector('[data-bet-selector="bonusType"]');
      if (center?.classList.contains('spots-part-button_disabled')) {
        return { ok: false, why: 'centro-disabled' };
      }
      const anySpotOn = document.querySelector(
        '[data-bet-selector="1"]:not(.spots-item_disabled), [data-bet-selector="bonusType"]:not(.spots-part-button_disabled)'
      );
      if (!center && !anySpotOn) {
        return { ok: false, why: 'spots-disabled' };
      }
      return { ok: true, why: center ? 'ok-centro' : 'ok-spots' };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 40) };
  }
}

async function verificarBotonIndice(frame, idx) {
  try {
    return await frame.evaluate(i => {
      const tri = (function () {
        const sel =
          '[class*="bonus-action-button"], [class*="decision-color"], [class*="decision"] button, [class*="decision"] [role="button"]';
        const raw = Array.from(document.querySelectorAll(sel)).filter(el => {
          const cls = (el.className || '').toString();
          if (/icon-dice|dice-action/i.test(cls)) return false;
          const r = el.getBoundingClientRect();
          return r.width > 24 && r.height > 24 && r.bottom > 0 && r.right > 0;
        });
        const area = document.getElementById('game-area');
        const ar = area?.getBoundingClientRect();
        let nodes = raw;
        if (ar) {
          nodes = raw.filter(el => {
            const r = el.getBoundingClientRect();
            const cy = (r.top + r.bottom) / 2;
            return (
              cy >= ar.top + ar.height * 0.28 &&
              cy <= ar.top + ar.height * 0.85 &&
              r.left >= ar.left - 12 &&
              r.right <= ar.right + 12
            );
          });
        }
        const groups = new Map();
        for (const el of nodes) {
          const r = el.getBoundingClientRect();
          const cy = Math.round((r.top + r.bottom) / 2 / 16) * 16;
          if (!groups.has(cy)) groups.set(cy, []);
          groups.get(cy).push(el);
        }
        let row = [];
        for (const g of groups.values()) {
          if (g.length === 3) {
            row = g;
            break;
          }
        }
        if (row.length < 3) {
          const sorted = [...nodes].sort(
            (a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left
          );
          for (let s = 0; s <= sorted.length - 3; s++) {
            const slice = sorted.slice(s, s + 3);
            const r0 = slice[0].getBoundingClientRect();
            const r2 = slice[2].getBoundingClientRect();
            const cy0 = (r0.top + r0.bottom) / 2;
            const cy2 = (r2.top + r2.bottom) / 2;
            if (Math.abs(cy0 - cy2) < 48) {
              row = slice;
              break;
            }
          }
        }
        row.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
        return { row, nTotal: raw.length };
      })();
      const pick = tri.row;
      const txt = document.body?.innerText || '';
      const panel = document.getElementById('game-panel');
      const enDecision =
        /toma tu decisi|make your decision/i.test(txt) ||
        panel?.classList.contains('game-panel-desktop_hidden');

      if (pick.length === 3 && i >= 0 && i < pick.length) {
        const el = pick[i];
        const cls = (el.className || '').toString().toLowerCase();
        const aria =
          el.getAttribute('aria-pressed') ||
          el.getAttribute('aria-selected') ||
          el.getAttribute('aria-checked') ||
          '';
        const marcado =
          /active|selected|chosen|picked|on|blink/.test(cls) ||
          aria === 'true' ||
          el.matches('[class*="active"], [class*="selected"]');
        if (marcado) {
          return {
            ok: true,
            detalle:
              'triada=' +
              pick.length +
              ' total=' +
              tri.nTotal +
              ' idx=' +
              i +
              ' marcado',
          };
        }
      }

      if (!enDecision) {
        return { ok: true, detalle: 'overlay-cerrado (sin pantalla decisión)' };
      }

      return {
        ok: false,
        detalle:
          'triada=' +
          pick.length +
          ' total=' +
          tri.nTotal +
          ' idx=' +
          i +
          ' aun-decision=1',
      };
    }, idx);
  } catch (e) {
    return { ok: false, detalle: String(e.message || e).slice(0, 80) };
  }
}

/** Bono TOMA TU DECISIÓN — Show/Luck/Deluxe/Dice vía icon-*-action_N; fallback triada DOM. */
async function clickColorCuenta(frame, color, page) {
  const c = String(color || '').toLowerCase();
  await cerrarOverlaysJuego(frame);
  const modoInfo = await detectBonoModoFrame(frame);
  let idx = null;
  let metodo = '';
  let clicked = false;
  let verify = { ok: false, detalle: 'sin-intento' };

  if (modoInfo.modo) {
    idx = bonoActionIndex(modoInfo.modo, c);
    if (idx == null) {
      return {
        ok: false,
        idx: null,
        color: c,
        modo: modoInfo.modo,
        verify: { ok: false, detalle: 'color inválido' },
        detalle: modoInfo.modo + ' · color inválido: ' + c,
      };
    }
    for (let paso = 0; paso < 4 && !clicked; paso += 1) {
      try {
        const hit = await clickBonoActionIcon(frame, page, modoInfo.prefix, idx);
        if (hit.ok) {
          clicked = true;
          metodo = modoInfo.modo + '-' + (hit.metodo || modoInfo.prefix + '_' + idx);
          break;
        }
      } catch (_) {}
      if (paso < 3) await frame.waitForTimeout(220);
    }
    await frame.waitForTimeout(400);
    verify = await verificarBonoAction(frame, modoInfo.prefix, idx);
    if (clicked && !verify.ok) {
      try {
        const aun = await frame.evaluate(() =>
          /toma tu decisi|make your decision/i.test(document.body?.innerText || '')
        );
        if (!aun) {
          verify = { ok: true, detalle: modoInfo.modo + '-decision-cerrada' };
        }
      } catch (_) {}
    }
    return {
      ok: clicked,
      idx,
      color: c,
      modo: modoInfo.modo,
      metodo,
      verify,
      detalle:
        modoInfo.modo +
        ' ' +
        modoInfo.prefix +
        '_' +
        idx +
        ' · ' +
        (metodo || '?') +
        ' · ' +
        (clicked ? 'clic-ok' : 'clic-falló') +
        ' · ' +
        (verify?.detalle || ''),
    };
  }

  idx = COLOR_INDEX[c];
  if (idx == null) {
    return { ok: false, idx: null, verify: { ok: false, detalle: 'color inválido' } };
  }

  try {
    const hit = await frame.evaluate(i => {
      const lite = document.documentElement?.dataset?.jokerbetsLite === '1';
      const sel =
        '[class*="bonus-action-button"], [class*="decision-color"], [class*="decision"] button, [class*="decision"] [role="button"]';
      const raw = Array.from(document.querySelectorAll(sel)).filter(el => {
        const cls = (el.className || '').toString();
        if (/icon-dice|dice-action/i.test(cls)) return false;
        const r = el.getBoundingClientRect();
        return r.width > 16 && r.height > 16 && r.bottom > 0;
      });
      const area = document.getElementById('game-area');
      const ar = area?.getBoundingClientRect();
      let nodes = raw;
      if (ar && !lite && ar.height >= 40) {
        nodes = raw.filter(el => {
          const r = el.getBoundingClientRect();
          const cy = (r.top + r.bottom) / 2;
          return (
            cy >= ar.top + ar.height * 0.2 &&
            cy <= ar.top + ar.height * 0.9 &&
            r.left >= ar.left - 24 &&
            r.right <= ar.right + 24
          );
        });
      }
      const groups = new Map();
      for (const el of nodes) {
        const r = el.getBoundingClientRect();
        const cy = Math.round((r.top + r.bottom) / 2 / 16) * 16;
        if (!groups.has(cy)) groups.set(cy, []);
        groups.get(cy).push(el);
      }
      let row = [];
      for (const g of groups.values()) {
        if (g.length === 3) {
          row = g;
          break;
        }
      }
      if (row.length < 3) {
        const sorted = [...nodes].sort(
          (a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left
        );
        for (let s = 0; s <= sorted.length - 3; s++) {
          const slice = sorted.slice(s, s + 3);
          const r0 = slice[0].getBoundingClientRect();
          const r2 = slice[2].getBoundingClientRect();
          const cy0 = (r0.top + r0.bottom) / 2;
          const cy2 = (r2.top + r2.bottom) / 2;
          if (Math.abs(cy0 - cy2) < 48) {
            row = slice;
            break;
          }
        }
      }
      row.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
      if (row.length === 3 && row[i]) {
        row[i].click();
        return { ok: true, triada: row.length, total: raw.length };
      }
      return { ok: false, triada: row.length, total: raw.length };
    }, idx);
    if (hit.ok) {
      clicked = true;
      metodo = 'triada-' + hit.triada + '-t' + hit.total;
    }
  } catch (_) {}

  await frame.waitForTimeout(400);
  verify = await verificarBotonIndice(frame, idx);
  return {
    ok: clicked,
    idx,
    color: c,
    modo: 'legacy-triada',
    metodo,
    verify,
    detalle:
      'legacy ' +
      c +
      ' idx=' +
      idx +
      ' · ' +
      (metodo || '?') +
      ' · ' +
      (clicked ? 'clic-ok' : 'clic-falló') +
      ' · ' +
      (verify?.detalle || ''),
  };
}

/** Snap inactividad / play / error SALIR (lab + bot). */
async function probeInactividadMesa(frame) {
  if (!frame) return { ok: false, why: 'sin-frame' };
  try {
    return await frame.evaluate(() => {
      const txtRaw = document.body?.innerText || '';
      const txt = txtRaw.replace(/\s+/g, ' ').trim();
      const txtL = txt.toLowerCase();

      const codigoMatch = txt.match(
        /c[oó]digo de error:\s*(\d+)|error code:\s*(\d+)/i
      );
      const codigoError = codigoMatch
        ? codigoMatch[1] || codigoMatch[2] || null
        : null;
      const error506 =
        /c[oó]digo de error:\s*506|error code:\s*506/i.test(txt) ||
        codigoError === '506';
      const error99501 =
        codigoError === '99501' ||
        /c[oó]digo de error:\s*99501|error code:\s*99501/i.test(txt);
      const juegoNoDisponible =
        /no est[aá] disponible temporalmente|temporarily unavailable|select another game/i.test(txtL);
      const traceId = (txt.match(/trace id:\s*([a-f0-9-]{8,})/i) || [])[1] || null;

      const salirNodes = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
        .map(el => {
          const label = (el.textContent || '').replace(/\s+/g, ' ').trim();
          if (!/^salir$/i.test(label) && !/^exit$/i.test(label)) return null;
          const r = el.getBoundingClientRect();
          if (r.width < 40 || r.height < 20) return null;
          return {
            tag: el.tagName,
            cls: (el.className || '').toString().slice(0, 120),
            label,
            w: Math.round(r.width),
            h: Math.round(r.height),
            x: Math.round(r.left),
            y: Math.round(r.top),
          };
        })
        .filter(Boolean);

      /** Vista mantenimiento Skywind — prod solo F5; nunca clic en SALIR (desloguea). */
      const pantallaDisculpe = /disculpe las molestias/i.test(txtL);
      const errorSalir = pantallaDisculpe;

      const spotsRoot =
        document.getElementById('spots') ||
        document.getElementById('game-panel-spots');
      const blurOverlay = Array.from(
        document.querySelectorAll('canvas, video, img, div, section')
      ).some(el => {
        const st = getComputedStyle(el);
        const bf = `${st.filter || ''} ${st.backdropFilter || ''}`;
        if (!/blur\(\s*(?:[1-9]|[1-9]\d)/i.test(bf)) return false;
        const r = el.getBoundingClientRect();
        return r.width >= 160 && r.height >= 100;
      });

      const inactivityText =
        /inactiv|sesi[oó]n.*paus|stream.*paus|video.*paus|congel|frozen|click.*continu|pulse.*continu|haz clic.*reproduc|click to play|tap to play|press play|reanud/i.test(
          txtL
        );

      const playCandidates = [];
      const sel =
        'button, [role="button"], a, [class*="play" i], [class*="Play"], [data-testid*="play" i]';
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.width < 24 || r.height < 24 || r.bottom < 0) continue;
        const label = (el.textContent || el.getAttribute('aria-label') || '')
          .replace(/\s+/g, ' ')
          .trim()
          .slice(0, 80);
        const cls = (el.className || '').toString();
        const clsL = cls.toLowerCase();
        const labelPlay = /^play$/i.test(label) || /^reproducir$/i.test(label);
        const clsPlay = /nano-player|play-button|video-play|btn-play|icon-play|play_icon|play-overlay|stream-play/.test(
          clsL
        );
        const hasSvg = !!el.querySelector('svg, [class*="triangle"], [class*="play"]');
        if (!labelPlay && !clsPlay && !(hasSvg && /play|overlay|video|stream|pause/.test(clsL))) continue;
        playCandidates.push({
          tag: el.tagName,
          cls: cls.slice(0, 120),
          label: label || null,
          aria: el.getAttribute('aria-label') || null,
          w: Math.round(r.width),
          h: Math.round(r.height),
          x: Math.round(r.left),
          y: Math.round(r.top),
        });
      }
      playCandidates.sort((a, b) => b.w * b.h - a.w * a.h);

      const videos = Array.from(document.querySelectorAll('video')).map(v => ({
        paused: v.paused,
        readyState: v.readyState,
        w: v.videoWidth,
        h: v.videoHeight,
        muted: v.muted,
      }));
      const lite = document.documentElement?.dataset?.jokerbetsLite === '1';
      const videoPausedLive =
        !lite && videos.some(v => v.paused && v.readyState >= 2 && v.w > 0);

      const nanoPaused =
        !lite &&
        !!document.querySelector('.nano-player_paused, .nano-player.nano-player_paused');
      const bigPlay = playCandidates.find(c => c.w >= 48 && c.h >= 48);
      /** Lab inactividad-scan: pausa real = nano-player_paused + video paused (no solo nano-player en mesa viva). */
      const playOverlay = lite
        ? false
        : !!(
            nanoPaused ||
            (videoPausedLive && bigPlay) ||
            (inactivityText && videoPausedLive)
          );

      const mesaColgada = false;

      return {
        url: location.href.slice(0, 220),
        snippet: txt.slice(0, 700),
        playOverlay: {
          detected: playOverlay,
          nanoPaused,
          inactivityText,
          videoPausedLive,
          nCandidates: playCandidates.length,
          topCandidate: playCandidates[0] || null,
          candidates: playCandidates.slice(0, 15),
          videos,
        },
        pantallaDisculpe: {
          detected: pantallaDisculpe,
          error506,
          error99501,
          codigoError,
          juegoNoDisponible,
          traceId,
        },
        errorSalir: {
          detected: pantallaDisculpe,
          error506,
          error99501,
          codigoError,
          juegoNoDisponible,
          traceId,
          salirNodes,
        },
        mesaColgada: {
          detected: mesaColgada,
          blurOverlay,
          sinSpots: !spotsRoot,
        },
      };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 120) };
  }
}

async function detectPantallaInactividadPlay(frame) {
  const snap = await probeInactividadMesa(frame);
  if (snap.why) return { ok: false, why: snap.why };
  return {
    ok: !!snap.playOverlay?.detected,
    ...snap.playOverlay,
    url: snap.url,
  };
}

/** Solo texto — evita escanear play/blur en cada tick (mantenimiento ligero). */
async function detectDisculpeRapido(frame) {
  if (!frame) return { ok: false, why: 'sin-frame' };
  try {
    return await frame.evaluate(() => {
      const txt = (document.body?.innerText || '').replace(/\s+/g, ' ');
      const txtL = txt.toLowerCase();
      if (!/disculpe las molestias/i.test(txtL)) {
        return { ok: false };
      }
      const codigoMatch = txt.match(
        /c[oó]digo de error:\s*(\d+)|error code:\s*(\d+)/i
      );
      const codigoError = codigoMatch
        ? codigoMatch[1] || codigoMatch[2] || null
        : null;
      return {
        ok: true,
        codigoError,
        error99501: codigoError === '99501' || /99501/.test(txt),
        error506: codigoError === '506' || /\b506\b/.test(txt),
      };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 80) };
  }
}

/** Solo nano-player / video pausado — sin recorrer candidatos play. */
async function detectPlayOverlayLigero(frame) {
  if (!frame) return { ok: false, why: 'sin-frame' };
  try {
    return await frame.evaluate(() => {
      if (document.documentElement?.dataset?.jokerbetsLite === '1') {
        return { ok: false, lite: true };
      }
      const nanoPaused = !!document.querySelector(
        '.nano-player_paused, .nano-player.nano-player_paused'
      );
      if (nanoPaused) return { ok: true, detalle: 'nano-player_paused' };
      const videos = Array.from(document.querySelectorAll('video'));
      const videoPausedLive = videos.some(
        v => v.paused && v.readyState >= 2 && v.videoWidth > 0
      );
      if (videoPausedLive && document.querySelector('.nano-player, [class*="nano-player"]')) {
        return { ok: true, detalle: 'video+nano' };
      }
      return { ok: false };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 80) };
  }
}

async function detectPantallaDisculpeMolestias(frame) {
  const snap = await probeInactividadMesa(frame);
  if (snap.why) return { ok: false, why: snap.why };
  const d = snap.pantallaDisculpe || snap.errorSalir || {};
  return {
    ok: !!d.detected,
    ...d,
    url: snap.url,
  };
}

/** @deprecated alias lab — misma regla: Disculpe → F5, sin clic SALIR. */
async function detectPantallaErrorSalir(frame) {
  return detectPantallaDisculpeMolestias(frame);
}

async function detectPantallaMesaColgada(frame) {
  const snap = await probeInactividadMesa(frame);
  if (snap.why) return { ok: false, why: snap.why };
  return {
    ok: !!snap.mesaColgada?.detected,
    ...snap.mesaColgada,
    url: snap.url,
  };
}

/** Clic overlay inactividad (captura lab: .nano-player). */
async function clickInactividadPlay(page, frame) {
  if (!frame) return { ok: false, why: 'sin-frame' };
  const tries = [
    () => frame.locator('.nano-player_paused, .nano-player.nano-player_paused').first(),
    () => frame.locator('.nano-player, [class*="nano-player"]').first(),
    () => frame.locator('[class*="play-overlay"] button, [class*="play-overlay"]').first(),
    () => frame.locator('button:has-text("PLAY"), button:has-text("Play")').first(),
  ];
  for (const mk of tries) {
    try {
      const loc = mk();
      if ((await loc.count()) < 1) continue;
      if (!(await loc.isVisible({ timeout: 400 }).catch(() => false))) continue;
      await loc.click({ timeout: 5000 });
      await frame.waitForTimeout(400);
      const after = await detectPantallaInactividadPlay(frame);
      return {
        ok: true,
        metodo: 'locator',
        playAun: after.ok,
        detalle: after.topCandidate?.cls || 'nano-player',
      };
    } catch (_) {}
  }
  try {
    const det = await detectPantallaInactividadPlay(frame);
    const c = det.topCandidate;
    if (c && c.w >= 40 && page) {
      await page.mouse.click(c.x + c.w / 2, c.y + c.h / 2);
      await frame.waitForTimeout(400);
      return { ok: true, metodo: 'coords', detalle: c.cls || 'play' };
    }
  } catch (_) {}
  return { ok: false, why: 'sin-clic-play' };
}

async function recargarMesaJuego(page, motivo) {
  if (!page || page.isClosed()) return { ok: false, why: 'sin-page' };
  try {
    await page.reload({ waitUntil: 'commit', timeout: 45000 });
    return { ok: true, motivo: motivo || 'f5' };
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 100) };
  }
}

/** Tras clic centro ($50): luck/dice/deluxe/wheel muestran "Bonus Game50" (apuesta-scan). */
async function verificarApuestaCentroBonos(frame, montoPorBono = 50) {
  const raw = Number(montoPorBono);
  const m = raw === 150 || raw === 200 ? raw : 50;
  try {
    return await frame.evaluate(expected => {
      const ids = ['luck', 'dice', 'deluxe', 'wheel'];
      const reConcat = new RegExp('Bonus Game\\s*' + expected + '\\b', 'i');
      const reSolo = new RegExp('(^|\\s)' + expected + '(\\s|$)');
      const reMal = new RegExp('Bonus Game\\s*250\\b', 'i');
      const partes = [];
      let nOk = 0;
      for (const sel of ids) {
        const el = document.querySelector('[data-bet-selector="' + sel + '"]');
        const txt = (el?.textContent || '').replace(/\s+/g, ' ').trim();
        const chipTxt = Array.from(el?.querySelectorAll('[class*="chip" i], [class*="fiche" i]') || [])
          .map(n => (n.textContent || '').trim())
          .join(' ');
        const ok =
          reConcat.test(txt) ||
          (reSolo.test(chipTxt) && !reMal.test(txt)) ||
          (reSolo.test(txt) && /bonus game/i.test(txt) && !reMal.test(txt));
        if (ok) nOk += 1;
        partes.push(sel + ':' + (ok ? String(expected) : txt.slice(0, 20) || '?'));
      }
      return {
        ok: nOk >= 4,
        nOk,
        esperado: expected,
        detalle: partes.join(' · '),
      };
    }, m);
  } catch (e) {
    return { ok: false, nOk: 0, detalle: String(e.message || e).slice(0, 48) };
  }
}

/** Centro dorado con ficha / monto visible (validar apuesta real, no solo texto APUESTA). */
async function centroApuestaMarcada(frame) {
  try {
    return await frame.evaluate(() => {
      const center = document.querySelector('[data-bet-selector="bonusType"]');
      if (!center) return { ok: false, why: 'no-centro' };
      const cls = (center.className || '').toString();
      if (/selected|_on\b|-on\b|active|has-bet|placed|highlight/i.test(cls)) {
        return { ok: true, why: 'cls-centro' };
      }
      const inner = center.querySelector(
        '[class*="chip"], [class*="fiche"], [class*="value"], [class*="amount"]'
      );
      if (inner && (inner.textContent || '').trim()) {
        return { ok: true, why: 'chip-dom' };
      }
      const txt = (center.textContent || '').replace(/\s/g, '');
      if (/[\d]/.test(txt) && !/^0+$/.test(txt)) return { ok: true, why: 'txt-centro' };
      return { ok: false, why: 'centro-vacio' };
    });
  } catch (e) {
    return { ok: false, why: String(e.message || e).slice(0, 40) };
  }
}

module.exports = {
  logBot,
  findGameFrame,
  readBarraSaldo,
  readBarraSaldoFromPage,
  parseBarraTexto,
  clickChip50,
  ensureChip50,
  ensureChip50ForPage,
  chipSeleccionado,
  clickCenterCircle,
  clickCenterCircleManual,
  prepChip50Manual,
  pantallaDecision,
  bloqueoApuestaManual,
  esperaSiguienteRonda,
  clickColorCuenta,
  cerrarOverlaysJuego,
  detectBonoModoFrame,
  verificarBotonIndice,
  mesaListaParaApostar,
  ventanaApuestaAbierta,
  verificarApuestaCentroBonos,
  centroApuestaMarcada,
  probeInactividadMesa,
  detectPantallaInactividadPlay,
  detectDisculpeRapido,
  detectPlayOverlayLigero,
  detectPantallaDisculpeMolestias,
  detectPantallaErrorSalir,
  detectPantallaMesaColgada,
  clickInactividadPlay,
  recargarMesaJuego,
};
