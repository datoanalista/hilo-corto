/**
 * Modal Cola G — lectura narrativa con horas reales del día.
 */
export default function ColaModal({ abierto, onCerrar, lectura }) {
  if (!abierto) return null;
  const L = lectura;

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-cola"
        role="dialog"
        aria-label="Cola G"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Cola G</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        {!L ? (
          <p className="hint">Sin lectura de cola aún.</p>
        ) : (
          <>
            <div className={`cola-badge tono-${L.tone || "olor"}`}>
              <strong>{L.pill}</strong>
              <span>
                h{String(L.hod).padStart(2, "0")} · min{" "}
                {String(L.T).padStart(2, "0")}
                {L.diaGeneroso ? " · día generoso" : ""}
                {L.nColaPrev > 0 ? ` · ${L.nColaPrev} cola(s) hoy` : ""}
              </span>
            </div>

            <p className="cola-lead">{L.lead}</p>

            {L.pasadas?.length ? (
              <section className="cola-seccion" aria-label="Horas pasadas hoy">
                <h3 className="cola-seccion-titulo">Hoy ya pasó</h3>
                <ul className="cola-lista-horas">
                  {L.pasadas.map((h) => (
                    <li
                      key={h.tag}
                      className={[
                        h.cola ? "con-cola" : "",
                        h.generosa ? "generosa" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {h.linea}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {L.anterior ? (
              <section className="cola-seccion" aria-label="Hora anterior">
                <h3 className="cola-seccion-titulo">Hora anterior</h3>
                <p className="cola-anterior">{L.anterior.texto}</p>
              </section>
            ) : null}

            <section className="cola-seccion" aria-label="Hora en curso">
              <h3 className="cola-seccion-titulo">En curso</h3>
              <p className="cola-en-curso">{L.enCurso.linea}</p>
            </section>

            {L.espera?.length ? (
              <section className="cola-seccion" aria-label="Qué se espera">
                <h3 className="cola-seccion-titulo">Qué se espera</h3>
                <ul className="cola-espera">
                  {L.espera.map((txt, i) => (
                    <li key={i}>{txt}</li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
