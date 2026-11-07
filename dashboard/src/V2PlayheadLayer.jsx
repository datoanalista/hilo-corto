import { useEffect, useRef } from "react";
import { pad } from "./mesa.js";
import { relojSistema } from "./live.js";
import {
  bloqueDeMinuto,
  computeTPlay,
  minutoAPct,
  tiempoAPct,
} from "./v2Layout.js";

function usePlayheadDom({
  enCursoKey,
  sosteniendoHora,
  ultimoMinuto,
  enHora,
  pesos,
}) {
  const playheadRef = useRef(null);
  const rulerNowRef = useRef(null);
  const rulerMinRef = useRef(null);

  useEffect(() => {
    function apply(tPlay) {
      const tPct = tiempoAPct(tPlay, pesos);
      const T = Math.min(59, Math.floor(tPlay));
      const playSec = Math.min(59, Math.floor((tPlay - T) * 60));
      const left = `${tPct}%`;
      const title = enCursoKey
        ? `${enCursoKey} · min ${pad(T)}:${pad(playSec)}`
        : `Minuto ${pad(T)}`;

      if (playheadRef.current) {
        playheadRef.current.style.left = left;
      }
      if (rulerNowRef.current) {
        rulerNowRef.current.style.left = left;
        rulerNowRef.current.title = title;
      }
      if (rulerMinRef.current) {
        rulerMinRef.current.textContent = pad(T);
      }
    }

    function tick() {
      const reloj = relojSistema();
      const tPlay = computeTPlay({
        enCursoKey,
        sosteniendoHora,
        ultimoMinuto,
        enHora,
        reloj,
      });
      apply(tPlay);
    }

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [enCursoKey, sosteniendoHora, ultimoMinuto, enHora, pesos]);

  return { playheadRef, rulerNowRef, rulerMinRef };
}

/**
 * Playhead + regla: un solo intervalo, actualiza DOM refs (no re-render del tablero).
 */
export default function V2PlayheadLayer({
  enCursoKey = "",
  sosteniendoHora = false,
  ultimoMinuto = null,
  enHora = false,
  pesos,
  verdesLive = [],
  goHitsSet = null,
  hoverG,
  setHoverG,
  setHoverBloque,
  children,
}) {
  const hits = goHitsSet || new Set();
  const { playheadRef, rulerNowRef, rulerMinRef } = usePlayheadDom({
    enCursoKey,
    sosteniendoHora,
    ultimoMinuto,
    enHora,
    pesos,
  });

  const ruler = (
    <div className="v2-ruler" aria-hidden="true">
      <span className="v2-ruler-spacer" />
      <div className="v2-ruler-track">
        {verdesLive.map((v) => {
          const left = minutoAPct(v.minuto, pesos);
          const goHit = hits.has(v.minuto);
          return (
            <span
              key={`tick-${v.minuto}`}
              className={`v2-ruler-tick g${goHit ? " go-hit" : ""}`}
              style={{ left: `${left}%` }}
              title={
                goHit
                  ? `${pad(v.minuto)} · Go! acertó`
                  : `${pad(v.minuto)}`
              }
            >
              <b className="v2-ruler-tick-min">{pad(v.minuto)}</b>
            </span>
          );
        })}
        <span
          ref={rulerNowRef}
          className="v2-ruler-tick now"
          style={{ left: "0%" }}
        >
          <b ref={rulerMinRef} className="v2-ruler-tick-min">
            00
          </b>
        </span>
      </div>
    </div>
  );

  const overlay = (
    <div
      className="v2-playhead-overlay"
      aria-hidden={hoverG ? undefined : true}
    >
      <div className="v2-playhead-band">
        <div className="v2-playhead-head" aria-hidden="true" />
        <div className="v2-playhead-track">
          {enHora ? (
            <i
              ref={playheadRef}
              className="v2-playhead"
              style={{ left: "0%" }}
              aria-hidden="true"
            />
          ) : null}
          {verdesLive.map((v) => {
            const left = minutoAPct(v.minuto, pesos);
            const gLabel = v.tipo != null ? `G${v.tipo}` : "G";
            const res =
              v.vecino != null && v.vecino !== ""
                ? `${v.vecino}x`
                : "—";
            const goHit = hits.has(v.minuto);
            return (
              <button
                type="button"
                key={`g-${v.minuto}`}
                className={`v2-gline${
                  hoverG?.minuto === v.minuto ? " on" : ""
                }${goHit ? " go-hit" : ""}`}
                style={{ left: `${left}%` }}
                aria-label={`${pad(v.minuto)} ${gLabel} ${res}${
                  goHit ? " · Go! acertó" : ""
                }`}
                onMouseEnter={() => {
                  setHoverG({
                    minuto: v.minuto,
                    tipo: v.tipo,
                    vecino: v.vecino,
                    left,
                    gLabel,
                    res,
                  });
                  setHoverBloque(bloqueDeMinuto(v.minuto));
                }}
                onMouseLeave={() => setHoverG(null)}
              />
            );
          })}
          {hoverG ? (
            <div
              className="v2-gline-tip"
              style={{ left: `${hoverG.left}%` }}
              role="tooltip"
            >
              <strong>{pad(hoverG.minuto)}</strong>
              <span>{hoverG.gLabel}</span>
              <span className="res">{hoverG.res}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );

  return children({ ruler, overlay });
}
