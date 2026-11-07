/**
 * Pegar en DevTools → Console (contexto del iframe del juego Skywind).
 * Igual lógica que jokerbets-dom probeInactividadMesa + mesa lista.
 *
 * 1) F12 en la ventana de la casa (Jugabet / Betano / …)
 * 2) Arriba del console: elegir iframe sw420101 / live-client-jokers / skywind
 * 3) Pegar TODO este archivo (o el bloque JB_MESA_CAPTURA del chat)
 * 4) Copiar JSON → pegar en un .json o en REGISTRO manual
 *
 * Helpers: JB_MESA_F5()  copy(JSON.stringify(window.__JB_MESA_CAPTURA__))
 * Prod: nunca clic SALIR — solo F5.
 */
(function JB_MESA_CAPTURA() {
  function probeDoc(doc, meta) {
    const txtRaw = doc.body?.innerText || '';
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
      /99501/.test(txt);
    const juegoNoDisponible =
      /no est[aá] disponible temporalmente|temporarily unavailable|select another game/i.test(
        txtL
      );

    const salirNodes = Array.from(
      doc.querySelectorAll('button, [role="button"], a, div')
    )
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
          x: Math.round(r.x),
          y: Math.round(r.y),
        };
      })
      .filter(Boolean);

    const pantallaDisculpe = /disculpe las molestias/i.test(txtL);
    const errorSalir = pantallaDisculpe;

    const spotsRoot =
      doc.getElementById('spots') || doc.getElementById('game-panel-spots');
    const center = doc.querySelector('[data-bet-selector="bonusType"]');
    const blurOverlay = Array.from(
      doc.querySelectorAll('canvas, video, img, div, section')
    ).some(el => {
      const st = doc.defaultView.getComputedStyle(el);
      const bf = `${st.filter || ''} ${st.backdropFilter || ''}`;
      if (!/blur\(\s*(?:[1-9]|[1-9]\d)/i.test(bf)) return false;
      const r = el.getBoundingClientRect();
      return r.width >= 160 && r.height >= 100;
    });

    const videos = Array.from(doc.querySelectorAll('video')).map(v => ({
      paused: v.paused,
      readyState: v.readyState,
      w: v.videoWidth,
      h: v.videoHeight,
    }));

    const nanoPaused = !!doc.querySelector(
      '.nano-player_paused, .nano-player.nano-player_paused'
    );

    const mesaColgada = false;

    let mesaBot = { ok: false, why: 'sin-eval' };
    if (/espere[\s\S]{0,24}siguiente|wait[\s\S]{0,16}next/i.test(txt)) {
      mesaBot = { ok: false, why: 'espera-ronda' };
    } else if (!spotsRoot) {
      mesaBot = { ok: false, why: 'sin-spots-dom' };
    } else if (center?.classList.contains('spots-part-button_disabled')) {
      mesaBot = { ok: false, why: 'centro-disabled' };
    } else {
      mesaBot = { ok: true, why: center ? 'ok-centro' : 'ok-spots' };
    }

    const prodF5 = pantallaDisculpe;

    return {
      ...meta,
      url: (doc.defaultView?.location?.href || meta.url || '').slice(0, 240),
      snippet: txt.slice(0, 900),
      codigoError,
      errorSalir,
      error506,
      error99501,
      juegoNoDisponible,
      salirNodes,
      mesaColgada,
      blurOverlay,
      sinSpots: !spotsRoot,
      mesaBot,
      nanoPaused,
      nVideos: videos.length,
      videos: videos.slice(0, 4),
      prodF5,
      prodPlay: nanoPaused,
    };
  }

  const probes = [];
  probes.push(
    probeDoc(document, {
      contexto: 'documento-actual',
      host: location.hostname,
    })
  );

  for (const iframe of document.querySelectorAll('iframe')) {
    try {
      const d = iframe.contentDocument;
      if (d?.body) {
        probes.push(
          probeDoc(d, {
            contexto: 'iframe-hijo',
            iframeSrc: (iframe.src || '').slice(0, 200),
          })
        );
      }
    } catch (e) {
      probes.push({
        contexto: 'iframe-hijo',
        crossOrigin: true,
        iframeSrc: (iframe.src || '').slice(0, 200),
        error: String(e.message || e),
      });
    }
  }

  const out = {
    ts: new Date().toISOString(),
    topUrl: location.href.slice(0, 240),
    host: location.hostname,
    probes,
    resumen: {
      prodF5: probes.some(p => p.prodF5),
      errorSalir: probes.some(p => p.errorSalir),
      mesaColgada: probes.some(p => p.mesaColgada),
      mesaOk: probes.some(p => p.mesaBot?.ok),
    },
  };

  window.__JB_MESA_CAPTURA__ = out;
  window.JB_MESA_F5 = () => location.reload();
  console.log('=== JB mesa rota / mantenimiento ===');
  console.log(JSON.stringify(out, null, 2));
  console.log(
    'Guardado en window.__JB_MESA_CAPTURA__ · JB_MESA_F5() · prod no usa SALIR'
  );
  return out;
})();
