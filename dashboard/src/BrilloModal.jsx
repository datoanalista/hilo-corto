import { useMemo } from "react";
import { ESCALA_TOTAL } from "./brilloInfo.js";
import { buildMapaLectura } from "./mapaInfo.js";
import MapaPanel from "./MapaPanel.jsx";

export function IconBrillo({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="4.25"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <g stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
        <line x1="12" y1="2.5" x2="12" y2="5.5" />
        <line x1="12" y1="18.5" x2="12" y2="21.5" />
        <line x1="2.5" y1="12" x2="5.5" y2="12" />
        <line x1="18.5" y1="12" x2="21.5" y2="12" />
        <line x1="5.04" y1="5.04" x2="7.22" y2="7.22" />
        <line x1="16.78" y1="16.78" x2="18.96" y2="18.96" />
        <line x1="5.04" y1="18.96" x2="7.22" y2="16.78" />
        <line x1="16.78" y1="7.22" x2="18.96" y2="5.04" />
      </g>
    </svg>
  );
}

export default function BrilloModal({ abierto, onCerrar, lectura }) {
  if (!abierto) return null;
  const L = lectura;
  const mapa = useMemo(
    () =>
      L
        ? buildMapaLectura({
            hod: L.hod,
            acum: L.acum,
            T: L.T,
            bandaTotal: L.bandaTotal,
          })
        : null,
    [L?.hod, L?.acum, L?.T, L?.bandaTotal]
  );

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-brillo-mapa"
        role="dialog"
        aria-label="Brillo de la hora"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Brillo</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        {!L ? (
          <p className="hint">Sin lectura aún.</p>
        ) : (
          <>
            <div className={`brillo-badge tono-${L.tone || "mute"}`}>
              <strong>{L.pill}</strong>
              <span>
                h{String(L.hod).padStart(2, "0")} · min {String(L.T).padStart(2, "0")}
              </span>
            </div>

            {(L.costuras?.length ? L.costuras : L.costura ? [L.costura] : []).map(
              (c) => (
                <div
                  key={c.pairId || c.titulo}
                  className={[
                    "brillo-costura",
                    `tono-${c.tono || "mute"}`,
                    c.ok ? " vive" : "",
                    c.alerta ? " alerta" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  aria-label={c.titulo}
                  role={c.alerta ? "alert" : undefined}
                >
                  <div className="brillo-costura-head">
                    <strong>{c.titulo}</strong>
                    {c.expectativa?.titulo ? (
                      <span className="brillo-costura-veredicto">
                        {c.expectativa.titulo}
                      </span>
                    ) : null}
                  </div>
                  {c.origen || c.h14 ? (
                    <div className="brillo-costura-h14">
                      <em>{`h${String(c.fromHod ?? c.origen?.hod ?? 14).padStart(2, "0")}`}</em>
                      <b>{(c.origen || c.h14)?.bandaLabel || "—"}</b>
                      {(c.origen || c.h14)?.sumG != null ? (
                        <span>{(c.origen || c.h14).sumG} lumen</span>
                      ) : (c.origen || c.h14)?.meanG != null ? (
                        <span>
                          ~{Math.round((c.origen || c.h14).meanG)} lumen/G
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {(c.lineas || []).map((ln, i) => (
                    <p key={i} className={i === 1 ? "brillo-costura-decision" : ""}>
                      {ln}
                    </p>
                  ))}
                  {c.detalle ? (
                    <p className="brillo-costura-detalle">{c.detalle}</p>
                  ) : null}
                </div>
              )
            )}

            <div className="brillo-lineas">
              {(L.lineas || []).map((ln, i) => (
                <p key={i}>{ln}</p>
              ))}
            </div>

            {L.tipsOpacidad?.length ? (
              <div className="brillo-tips-opaco" aria-label="Lecturas opacidad">
                <h3 className="proy-seccion-titulo">Opacidad · lab</h3>
                <ul>
                  {L.tipsOpacidad.map((tip) => (
                    <li
                      key={tip.id}
                      className={
                        tip.tono === "olor"
                          ? "flaca-olor"
                          : tip.alerta
                            ? "flaca-alerta"
                            : undefined
                      }
                    >
                      {tip.texto}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {L.tipsIntraHora?.length ? (
              <div className="brillo-tips-opaco" aria-label="Apertura intra-hora">
                <h3 className="proy-seccion-titulo">Apertura · lab</h3>
                <ul>
                  {L.tipsIntraHora.map((tip) => (
                    <li
                      key={tip.id}
                      className={tip.tono === "olor" ? "flaca-olor" : undefined}
                    >
                      {tip.texto}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {L.tipsColaG?.length ? (
              <div
                className="brillo-tips-cola"
                aria-label="Cola G — lab"
                role={L.tipsColaG.some((t) => t.alerta) ? "alert" : undefined}
              >
                <h3 className="proy-seccion-titulo">Cola G · lab</h3>
                <ul>
                  {L.tipsColaG.map((tip) => (
                    <li
                      key={tip.id}
                      className={
                        tip.alerta
                          ? "cola-alerta"
                          : tip.tono === "confirmada"
                            ? "cola-confirmada"
                            : undefined
                      }
                    >
                      {tip.texto}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="brillo-kpis" aria-label="Números de la hora">
              <div className="brillo-kpi">
                <em>Luz sumada</em>
                <b>{L.acum ?? "—"}</b>
                <small>lumen hasta ahora</small>
              </div>
              <div className="brillo-kpi">
                <em>Por cada G</em>
                <b>{L.meanG != null ? Math.round(L.meanG) : "—"}</b>
                <small>
                  {L.nG >= 2
                    ? `${L.nG} G · ${L.bandaMean || "—"}`
                    : L.nG === 1
                      ? "1 G · poca muestra"
                      : "sin G aún"}
                </small>
              </div>
              <div className="brillo-kpi">
                <em>Cierre estimado</em>
                <b>
                  {L.predLo != null ? `${L.predLo}–${L.predHi}` : "—"}
                </b>
                <small>
                  {L.predLo != null
                    ? L.bandaTotal || "—"
                    : L.fase === "apertura" || L.fase === "esperando"
                      ? "cuando haya lectura"
                      : "—"}
                </small>
              </div>
            </div>

            {mapa ? (
              <MapaPanel
                mapa={mapa}
                costuras={(L.costuras || []).filter((c) => c.ok)}
              />
            ) : null}

            <details className="brillo-escalas">
              <summary>Escala de luz (hora completa)</summary>
              <ul>
                {ESCALA_TOTAL.map((b) => (
                  <li
                    key={b.id}
                    className={
                      L.bandaTotal === b.label ? "on" : undefined
                    }
                  >
                    <span>{b.label}</span>
                    <span>
                      {b.max >= 90000
                        ? `≥ ${b.min}`
                        : b.min === 0
                          ? `< ${b.max + 1}`
                          : `${b.min}–${b.max}`}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="hint">Por G: muy apagado &lt;42 · opaco 42–50 · normal 50–68 · fuerte 68–85 · muy fuerte 85–110 · supernova ≥110</p>
            </details>
          </>
        )}
      </div>
    </div>
  );
}
