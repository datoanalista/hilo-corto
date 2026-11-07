/**
 * Modal Eco (guía de puentes brillo) + icono guía.
 */
export function IconGuia({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      {/* guía / libro abierto — legible a 14px */}
      <path
        d="M3 4.5h7.5c1.2 0 2 .7 2 1.8V20c-1.3-.7-2.7-1-4.2-1H3V4.5z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M21 4.5h-7.5c-1.2 0-2 .7-2 1.8V20c1.3-.7 2.7-1 4.2-1H21V4.5z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M12 6.3V19"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function EcoTipsPanel({ eco } = {}) {
  if (!eco?.lineas?.length) return null;
  const lineas = eco.lineas.filter(
    (l) => l && !/no es boleto/i.test(l) && !/^Eco:\s*sin/i.test(l)
  );
  if (!lineas.length) return null;
  return (
    <section className="tips-eco-panel" aria-label="Eco de brillo">
      <h3 className="proy-seccion-titulo">Eco · {eco.pill}</h3>
      <div className="tips-eco-lineas">
        {lineas.map((ln, i) => (
          <p key={i}>{ln.replace(/^Eco:\s*/i, "")}</p>
        ))}
      </div>
    </section>
  );
}

export default function EcoModal({ abierto, onCerrar, lectura }) {
  if (!abierto) return null;
  const L = lectura;

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-eco"
        role="dialog"
        aria-label="Eco de brillo"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Eco</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        {!L ? (
          <p className="hint">Sin lectura aún.</p>
        ) : (
          <>
            <div className={`brillo-badge tono-${L.tone || "mute"}`}>
              <strong>Eco · {L.pill}</strong>
              <span>guía de brillo entre horas · INFO</span>
            </div>

            <div className="brillo-lineas">
              {(L.lineas || []).map((ln, i) => (
                <p key={i}>{ln}</p>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
