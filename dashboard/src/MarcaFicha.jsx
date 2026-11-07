import { useState } from "react";
import { cubre, pad, rolFicha } from "./mesa.js";

export default function MarcaFicha({ ficha, tiro, hora, onMarcar, onCerrar }) {
  const [a, c, b] = cubre(ficha);
  const mins = [a, c, b];
  const rol = rolFicha(tiro);
  const [acerto, setAcerto] = useState(null);
  const [minuto, setMinuto] = useState(null);

  const listo =
    acerto === false || (acerto === true && minuto != null);

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-marca"
        role="dialog"
        aria-labelledby="marca-titulo"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="marca-titulo">
          {rol === "pleno" ? "Pleno" : "Ficha"} {pad(ficha)}
          {hora ? ` · ${hora}` : ""}
        </h2>
        <p className="hint">
          {rol === "pleno"
            ? `Cobra solo el ${pad(ficha)}. Ya jugó: ¿acertó?`
            : `Cobra ${pad(a)}, ${pad(c)} y ${pad(b)}. Ya jugó: ¿acertó?`}
        </p>

        <div className="marca-si-no">
          <button
            type="button"
            className={`marca-si${acerto === true ? " on" : ""}`}
            onClick={() => {
              setAcerto(true);
            }}
          >
            ✓ Acertó
          </button>
          <button
            type="button"
            className={`marca-no${acerto === false ? " on" : ""}`}
            onClick={() => {
              setAcerto(false);
              setMinuto(null);
            }}
          >
            ✕ No hubo nada
          </button>
        </div>

        {acerto === true ? (
          <fieldset className="marca-mins">
            <legend>¿En qué minuto?</legend>
            {mins.map((m) => (
              <label key={m} className={minuto === m ? "on" : ""}>
                <input
                  type="radio"
                  name="minuto-marca"
                  checked={minuto === m}
                  onChange={() => setMinuto(m)}
                />
                <span>
                  {pad(m)}
                  {m === ficha ? " · blanco" : " · vecino"}
                </span>
              </label>
            ))}
          </fieldset>
        ) : null}

        {acerto === false ? (
          <p className="hint">Tiro fallido. No persigas esos tres.</p>
        ) : null}

        <div className="row">
          <button
            type="button"
            disabled={!listo}
            onClick={() =>
              onMarcar({
                ficha,
                acerto: Boolean(acerto),
                minuto: acerto ? minuto : null,
              })
            }
          >
            Guardar
          </button>
          <button className="ghost" type="button" onClick={onCerrar}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
