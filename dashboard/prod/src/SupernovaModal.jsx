import { BLOQUES, SN_UMBRAL } from "./supernovaInfo.js";

/** Icono supernova — estrella (live). */
export function IconSupernova({ className = "" } = {}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="18"
      height="18"
      aria-hidden="true"
    >
      <path
        d="M12 2.2l2.65 5.37 5.93.86-4.29 4.18 1.01 5.9L12 15.77l-5.3 2.74 1.01-5.9-4.29-4.18 5.93-.86L12 2.2z"
        fill="currentColor"
      />
    </svg>
  );
}

/** Alias — toolbar live usa estrella */
export const IconProyeccion = IconSupernova;

function olorLabel(olor) {
  if (olor === "confirmada") return "confirmada";
  if (olor === "alerta") return "alerta SN";
  if (olor === "olor") return "olor";
  if (olor === "baja") return "baja";
  return "—";
}

function olorClass(olor) {
  if (olor === "confirmada" || olor === "alerta") return "sn-alerta";
  if (olor === "olor") return "sn-olor";
  return "";
}

function EscalaLadder({ indicadores }) {
  const niveles = indicadores?.niveles || [];
  return (
    <div className="proy-escala" aria-label="Escala de proyección">
      <h3 className="proy-seccion-titulo">Escala de cierre</h3>
      <ul className="proy-escala-lista">
        {niveles.map((nv) => (
          <li
            key={nv.id}
            className={[
              "proy-escala-item",
              nv.estado !== "off" ? `on-${nv.estado}` : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="proy-escala-bar" aria-hidden="true" />
            <span className="proy-escala-nombre">{nv.label}</span>
            <span className="proy-escala-rango">
              {nv.max >= 90000 ? `≥ ${nv.min}` : `${nv.min}–${nv.max}`}
            </span>
          </li>
        ))}
      </ul>
      <p className="hint proy-escala-leyenda">
        <span className="leyenda actual" /> acumulado ·{" "}
        <span className="leyenda proy" /> proyección · confianza{" "}
        {indicadores?.confianza || "—"} ({indicadores?.fase || "—"})
      </p>
    </div>
  );
}

function PanelGenerosidad({ gen }) {
  if (!gen?.ok) return null;
  const { hoy, ola, hod, ventana, secciones, confianza } = gen;
  const conf = ola?.confianza || confianza;

  return (
    <section className="proy-gen-panel" aria-label="Calendario generosidad">
      <div className="proy-gen-head">
        <h3 className="proy-seccion-titulo">Días generosos</h3>
        {conf ? (
          <span
            className={`proy-gen-conf conf-${conf.nivel}`}
            title={conf.nota}
          >
            olor {conf.label}
          </span>
        ) : null}
      </div>

      {hoy ? (
        <div className="proy-gen-hoy">
          <div className="proy-gen-hoy-fecha">
            <strong>{hoy.label}</strong>
            {hoy.etiqueta ? (
              <span
                className={`proy-gen-etiq etiq-${hoy.etiqueta.id}`}
                title={hoy.etiqueta.hint}
              >
                {hoy.etiqueta.label}
              </span>
            ) : (
              <span className={`proy-gen-perfil perfil-${hoy.perfil}`}>
                perfil {hoy.perfil}
              </span>
            )}
          </div>
          <div className="proy-gen-stats">
            <span>
              <em>Fuertes</em> {hoy.pGen}% ({hoy.nGen}/{hoy.nHoras} h)
            </span>
            <span>
              <em>Opacas</em> {hoy.pOp}%
            </span>
            <span>
              <em>Med/h</em> {hoy.medH}
            </span>
          </div>
          {hoy.falsoGen ? (
            <p className="proy-gen-alerta">
              Día partido: picos ≥850 lumen pero mediana &lt;600 — no es generoso
              limpio.
            </p>
          ) : null}
          {hoy.genDia && !hoy.falsoGen ? (
            <p className="proy-gen-vive">Día generoso en curso</p>
          ) : null}
        </div>
      ) : null}

      {ola?.ultimo ? (
        <div className="proy-gen-ola">
          <p className="proy-gen-fila">
            <span className="proy-gen-k">Última ola</span>
            <span>
              {ola.ultimo.label} · {ola.ultimo.pGen}%
              {ola.diasDesdeUltimo != null
                ? ` · hace ${ola.diasDesdeUltimo} d`
                : ""}
            </span>
          </p>
          {ola.olorCentro ? (
            <p className="proy-gen-fila olor">
              <span className="proy-gen-k">Olor centro</span>
              <span>{ola.olorCentro.label}</span>
            </p>
          ) : null}
          {ola.olorRango ? (
            <p className="proy-gen-fila">
              <span className="proy-gen-k">Ventana</span>
              <span>
                {ola.olorRango.desde} – {ola.olorRango.hasta}
                {ola.diasHastaOlor != null && ola.diasHastaOlor > 0
                  ? ` · ~${ola.diasHastaOlor} d`
                  : ola.diasHastaOlor === 0
                    ? " · hoy en centro"
                    : ""}
              </span>
            </p>
          ) : null}
        </div>
      ) : null}

      {ventana?.length ? (
        <div className="proy-gen-ventana">
          <h4>Próximos días</h4>
          <ul className="proy-gen-dias">
            {ventana.map((d) => (
              <li
                key={d.offset}
                className={[
                  d.esHoy ? "es-hoy" : "",
                  d.esOlorCentro ? "es-olor" : "",
                  d.enRangoOla ? "en-rango" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className="proy-gen-dia-fecha">
                  {d.offset === 0 ? "Hoy" : `+${d.offset}d`} · {d.label}
                </span>
                <span className="proy-gen-dia-meta">
                  hist ~{d.pGenHist}% fuertes · {d.pDiaGenHist}% olor día gen
                  {d.confianzaDow ? ` · ${d.confianzaDow}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hod ? (
        <p className="proy-gen-hod hint">
          h{String(hod.actual).padStart(2, "0")} · {hod.franja}
          {hod.olorHora && hod.pGenHist
            ? ` · olor hora (~${hod.pGenHist}% hist)`
            : hod.proximos?.length
              ? ` · mirar ${hod.proximos.map((x) => x.label).join(", ")}`
              : ""}
        </p>
      ) : null}

      {secciones?.length ? (
        <ul className="proy-gen-secciones">
          {secciones.map((s) => (
            <li key={s.id} className={`proy-gen-tip proy-gen-tip-${s.tipo}`}>
              {s.titulo !== "Nota" ? (
                <strong>{s.titulo}: </strong>
              ) : null}
              {s.texto}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function TipsLab({ tips }) {
  if (!tips?.length) return null;
  return (
    <section className="proy-tips-lab" aria-label="Lecturas del lab supernova">
      <h3 className="proy-seccion-titulo">Esta hora · supernova</h3>
      <ul>
        {tips.map((tip) => (
          <li key={tip.id} className={`proy-tip proy-tip-${tip.id}`}>
            {tip.texto}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SupernovaModal({ abierto, onCerrar, lectura }) {
  if (!abierto) return null;
  const L = lectura;
  const bloques = L?.registroBloques || [];
  const enCurso = L?.bloqueEnCurso;
  const ind = L?.indicadores;

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-supernova modal-proy-grande"
        role="dialog"
        aria-label="Proyección de luz"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Proyección</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        {!L ? (
          <p className="hint">Sin lectura aún.</p>
        ) : (
          <>
            <div
              className={`supernova-badge tono-${L.alerta?.estado === "confirmada" ? "confirmada" : L.tone || "reposo"}`}
            >
              <strong>{L.pill}</strong>
              <span>
                h{String(L.hod).padStart(2, "0")} · min {String(L.T).padStart(2, "0")}
                {L.parpadea
                  ? " · alerta activa"
                  : L.alerta?.estado === "confirmada"
                    ? " · SN confirmada"
                    : ""}
                {ind?.projRangoLabel ? ` · ${ind.projRangoLabel}` : ""}
              </span>
            </div>

            <div className="proy-layout">
              <div className="proy-col proy-col-principal">
                <div className="proy-kpis" aria-label="Números proyección">
                  <div className="brillo-kpi">
                    <em>Luz acumulada</em>
                    <b>{L.acum ?? "—"}</b>
                    <small>{ind?.actualLabel || "ahora"}</small>
                  </div>
                  <div className="brillo-kpi">
                    <em>Proyección cierre</em>
                    <b>
                      {L.predLo != null ? `${L.predLo}–${L.predHi}` : "—"}
                    </b>
                    <small>{ind?.projLabel || "—"}</small>
                  </div>
                  <div className="brillo-kpi">
                    <em>Cola G&gt;500</em>
                    <b>{L.n500 ?? 0}</b>
                    <small>{L.n500 > 0 ? "presente" : "ausente"}</small>
                  </div>
                  <div className="brillo-kpi">
                    <em>Supernova</em>
                    <b>{L.pillAlerta ?? L.alerta?.estado ?? "—"}</b>
                    <small>umbral {SN_UMBRAL} lumen</small>
                  </div>
                </div>

                <section className="proy-lectura-hora">
                  <h3 className="proy-seccion-titulo">Lectura de la hora</h3>
                  <div className="brillo-lineas">
                    {(L.lineas || []).map((ln, i) => (
                      <p key={i}>{ln}</p>
                    ))}
                  </div>
                </section>

                <TipsLab tips={L.tipsLab} />

                <div className="supernova-bloques">
                  <h3 className="proy-seccion-titulo">Registro por bloques</h3>
                  <div className="supernova-tabla-wrap">
                    <table className="supernova-tabla">
                      <thead>
                        <tr>
                          <th>Bloque</th>
                          <th>Min</th>
                          <th>Acum</th>
                          <th>G</th>
                          <th>mean</th>
                          <th>Proyección</th>
                          <th>Cierre est.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {BLOQUES.map((b) => {
                          const row = bloques.find((x) => x.id === b.id);
                          const cur = enCurso?.id === b.id ? enCurso : null;
                          const r = row || cur;
                          return (
                            <tr
                              key={b.id}
                              className={[
                                cur ? "en-curso" : "",
                                row ? "cerrado" : "",
                                r ? olorClass(r.olor) : "",
                              ]
                                .filter(Boolean)
                                .join(" ")}
                            >
                              <td>{b.label}</td>
                              <td>{r ? r.minuto : "—"}</td>
                              <td>{r ? r.acum : "—"}</td>
                              <td>{r ? r.nG : "—"}</td>
                              <td>{r?.meanG ?? "—"}</td>
                              <td>
                                {r?.predLo != null
                                  ? `${r.predLo}–${r.predHi}`
                                  : "—"}
                              </td>
                              <td>
                                {r?.cierreEst ??
                                  (r ? olorLabel(r.olor) : "pendiente")}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="hint supernova-nota">
                    Confianza: baja &lt;20 · media 20–39 · alta ≥40. INFO · no
                    boleto.
                  </p>
                </div>
              </div>

              <div className="proy-col proy-col-lateral">
                {ind ? <EscalaLadder indicadores={ind} /> : null}
                <PanelGenerosidad gen={L.generosidad} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
