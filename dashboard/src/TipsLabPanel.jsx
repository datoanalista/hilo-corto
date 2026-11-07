/** Cola G · lab + opacidad flaca — INFO extracción/brillo. */
export default function TipsLabPanel({
  colaTips = [],
  flacaTips = [],
  horaTag = "",
} = {}) {
  if (!colaTips.length && !flacaTips.length) return null;

  return (
    <div className="tips-lab-panel" aria-label="Tips lab cinta">
      {horaTag ? (
        <p className="hint tips-lab-hora">{horaTag.toUpperCase()}</p>
      ) : null}
      {colaTips.length ? (
        <div
          className={`ex-cola-tips en-modal${
            colaTips.some((t) => t.alerta) ? " alerta" : ""
          }`}
        >
          <strong>Cola G · lab</strong>
          <ul>
            {colaTips.map((tip) => (
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
      {flacaTips.length ? (
        <div
          className={`ex-flaca-tips en-modal${
            flacaTips.some((t) => t.alerta) ? " alerta" : ""
          }`}
        >
          <strong>Opacidad · flaca</strong>
          <ul>
            {flacaTips.map((tip) => (
              <li
                key={tip.id}
                className={
                  tip.alerta
                    ? "flaca-alerta"
                    : tip.tono === "olor"
                      ? "flaca-olor"
                      : undefined
                }
              >
                {tip.texto}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
