import { DOW_LABEL, TRAMOS } from "./calendarioInfo.js";

export function IconCalendario({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <rect
        x="3"
        y="5"
        width="18"
        height="16"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <line x1="3" y1="9" x2="21" y2="9" stroke="currentColor" strokeWidth="1.75" />
      <line x1="8" y1="3" x2="8" y2="7" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <line x1="16" y1="3" x2="16" y2="7" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <circle cx="8" cy="14" r="1.1" fill="currentColor" />
      <circle cx="12" cy="14" r="1.1" fill="currentColor" />
      <circle cx="16" cy="14" r="1.1" fill="currentColor" />
      <circle cx="8" cy="17.5" r="1.1" fill="currentColor" opacity="0.5" />
    </svg>
  );
}

function CeldaGrid({ cel }) {
  const cls = [
    "cal-grid-cel",
    cel.activo ? " activo" : "",
    cel.tone !== "vacio" ? ` tono-${cel.tone}` : "",
  ].join("");
  return (
    <div className={cls} title={cel.titulo || ""}>
      <span className="cal-grid-dow">{cel.dowLabel}</span>
      {cel.lift != null ? (
        <span className="cal-grid-lift">
          {cel.lift > 0 ? "+" : ""}
          {cel.lift}%
        </span>
      ) : (
        <span className="cal-grid-lift mute">—</span>
      )}
    </div>
  );
}

export default function CalendarioModal({ abierto, onCerrar, lectura }) {
  if (!abierto) return null;
  const L = lectura;

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-calendario"
        role="dialog"
        aria-label="Calendario INFO"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Calendario</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        {!L ? (
          <p className="hint">Sin lectura aún.</p>
        ) : (
          <>
            <div className={`cal-badge tono-${L.tone || "mute"}`}>
              <strong>{L.pill}</strong>
              <span>
                h{String(L.hod).padStart(2, "0")} ·{" "}
                {L.dow != null ? DOW_LABEL[L.dow] : "—"} ·{" "}
                {TRAMOS.find((t) => t.id === L.tramo)?.label || L.tramo}
              </span>
            </div>

            <section className="cal-seccion cal-ahora" aria-label="Ahora">
              <h3 className="cal-seccion-titulo">Ahora</h3>
              <ul className="cal-lista">
                {(L.ahoraLineas || []).map((txt, i) => (
                  <li key={i}>{txt}</li>
                ))}
              </ul>
            </section>

            <section className="cal-seccion" aria-label="Grilla DOW por tramo">
              <h3 className="cal-seccion-titulo">Día × tramo (mean_G vs base · 38d)</h3>
              <p className="cal-hint">
                Celda resaltada = ahora. Verde/opaco = menos luz; dorado = más. ~
                = holdout inestable.
              </p>
              {L.grid.map((fila) => (
                <div key={fila.tramo} className="cal-grid-fila">
                  <div className="cal-grid-tramo">
                    <strong>{fila.label}</strong>
                    <span>{fila.hod}</span>
                  </div>
                  <div className="cal-grid-celdas">
                    {fila.celdas.map((cel) => (
                      <CeldaGrid key={`${cel.dow}-${cel.tramo}`} cel={cel} />
                    ))}
                  </div>
                </div>
              ))}
            </section>

            <section className="cal-seccion" aria-label="Costuras calendario">
              <h3 className="cal-seccion-titulo">Costuras (mismo día)</h3>
              <ul className="cal-lista cal-costuras">
                {L.costuras.map((c) => (
                  <li
                    key={c.id}
                    className={c.activo ? " activo" : ""}
                  >
                    <strong>{c.titulo}</strong>
                    {c.activo ? " · ahora" : ""}
                    {c.extra || ""}
                    <br />
                    <span className="cal-sub">{c.texto}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="cal-seccion" aria-label="Eco calendario">
              <h3 className="cal-seccion-titulo">Eco (hora → hora)</h3>
              <ul className="cal-lista cal-ecos">
                {L.ecos.map((e) => (
                  <li key={e.titulo} className={e.activo ? " activo" : ""}>
                    <strong>{e.titulo}</strong>
                    {e.activo
                      ? e.rol === "origen" || e.rol === "origen_hoy"
                        ? " · tu hora es origen"
                        : " · tu hora es destino"
                      : ""}
                    <br />
                    <span className="cal-sub">{e.texto}</span>
                  </li>
                ))}
              </ul>
            </section>

            <p className="cal-disclaimer">
              INFO de cinta larga (lab calendario R3). No es boleto ni chip.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
