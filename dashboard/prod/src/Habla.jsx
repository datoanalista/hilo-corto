import { useEffect, useState } from "react";
import { enJuego, pad, yaPaso } from "./mesa.js";

function BloqueSiEntonces({ fila, ejemplosAbiertos, onToggleEjemplos }) {
  if (!fila) return null;
  const tieneMira = Boolean(fila.mira);
  const tieneSi = Boolean(fila.siEntonces?.length);
  const tieneTabla = Boolean(fila.ejemplosTabla?.length);

  return (
    <div className="tips-detalle">
      {tieneMira ? (
        <p className="reco-que">
          <strong>Qué mirás:</strong> {fila.mira}
        </p>
      ) : (
        <p className="tips-detalle-resumen">{fila.resumen}</p>
      )}
      {tieneSi ? (
        <ul className="reco-si">
          {fila.siEntonces.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : (
        <ul>
          {(fila.detalle || []).map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
      {!tieneMira && fila.ejemplo ? (
        <p className="tips-ejemplo">{fila.ejemplo}</p>
      ) : null}
      {tieneTabla ? (
        <>
          <button
            type="button"
            className="reco-btn"
            onClick={onToggleEjemplos}
          >
            {ejemplosAbiertos ? "Cerrar ejemplos" : "Ver ejemplos con números"}
          </button>
          {ejemplosAbiertos ? (
            <div className="reco-tabla-wrap">
              <table className="reco-tabla">
                <thead>
                  <tr>
                    <th>Si pasa esto…</th>
                    <th>Qué significa</th>
                    <th>Minuto</th>
                    <th>Entonces hacé esto</th>
                  </tr>
                </thead>
                <tbody>
                  {fila.ejemplosTabla.map((ej) => (
                    <tr key={ej.caso}>
                      <td>{ej.caso}</td>
                      <td>{ej.paso}</td>
                      <td className="mono">{ej.mira}</td>
                      <td>{ej.hacer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default function Habla({
  habla,
  T,
  planLectura,
}) {
  const [filaId, setFilaId] = useState(null);
  const [ejemplosAbiertos, setEjemplosAbiertos] = useState(false);
  const [ejemplosFila, setEjemplosFila] = useState(false);
  const filas = habla?.tips?.filas || [];
  const sombra = filas.find((f) => f.id === "sombra") || null;
  const abierta = filas.find((f) => f.id === filaId) || null;

  useEffect(() => {
    setFilaId(null);
    setEjemplosAbiertos(false);
    setEjemplosFila(false);
  }, [habla?.titulo, T]);

  if (!habla) return null;

  const sombraPasada =
    sombra?.minuto != null && yaPaso(sombra.minuto, T);
  const sombraEnCurso =
    sombra?.minuto != null && enJuego(sombra.minuto, T);
  const sombraPrendio = sombra?.estado === "ya hubo luz en la zona";

  return (
    <section className={`habla tono-${habla.tono}`}>
      <h2 className="habla-titulo-modal">{habla.titulo || habla.verbo}</h2>
      <div className="habla-cuerpo">
        {sombra ? (
          <div className="reco-principal">
            <p className="reco-etiqueta">Lo más importante para leer la mesa</p>
            {sombra.minuto == null ? (
              <p className="reco-minuto">Sin minuto recomendado</p>
            ) : sombraPasada ? (
              <>
                <p className="reco-minuto reco-minuto-pasado">
                  Zona {pad((sombra.minuto + 59) % 60)} · {pad(sombra.minuto)} ·{" "}
                  {pad((sombra.minuto + 1) % 60)}
                  <span className="reco-banda"> — ya pasó</span>
                </p>
                <p className="reco-que">
                  <strong>Qué pasó:</strong>{" "}
                  {sombraPrendio
                    ? `Prendió luz en la zona (min ${pad(sombra.minuto)} o vecino). La pista de reloj pegó.`
                    : `No hubo luz en esa zona. Seguí el boleto; ${
                        sombra.proxima != null
                          ? `mantenete con el ${pad(sombra.proxima)}.`
                          : "no agregues fichas por esto."
                      }`}
                </p>
              </>
            ) : sombraEnCurso ? (
              <>
                <p className="reco-minuto">
                  Ahora — zona {pad((sombra.minuto + 59) % 60)} ·{" "}
                  <strong>{pad(sombra.minuto)}</strong> ·{" "}
                  {pad((sombra.minuto + 1) % 60)}
                </p>
                <p className="reco-que">
                  <strong>Qué mirás:</strong>{" "}
                  {sombra.mira ||
                    "si prende una luz en ese minuto o en el de al lado."}
                </p>
              </>
            ) : (
              <>
                <p className="reco-minuto">
                  Mirá el minuto <strong>{pad(sombra.minuto)}</strong>
                  <span className="reco-banda">
                    {" "}
                    — zona {pad((sombra.minuto + 59) % 60)} · {pad(sombra.minuto)}{" "}
                    · {pad((sombra.minuto + 1) % 60)}
                  </span>
                </p>
                <p className="reco-que">
                  <strong>Qué mirás:</strong>{" "}
                  {sombra.mira ||
                    "si prende una luz en ese minuto o en el de al lado. Nada más en esta pista."}
                </p>
              </>
            )}
            {!sombraPasada && sombra.siEntonces?.length ? (
              <ul className="reco-si">
                {sombra.siEntonces.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            ) : null}
            {sombraPasada && sombra.siEntonces?.length ? (
              <ul className="reco-si reco-si-pasado">
                <li>
                  {sombraPrendio && sombra.proxima != null
                    ? `Si marcó el ${pad(sombra.minuto)} → no perseguir el ${pad(sombra.proxima)}.`
                    : sombra.siEntonces[sombra.siEntonces.length - 1]}
                </li>
              </ul>
            ) : null}
            <p className="reco-aviso">
              No es una ficha nueva del boleto. No agregues minutos solo por esta
              pista.
            </p>
            <button
              type="button"
              className="reco-btn"
              onClick={() => setEjemplosAbiertos((v) => !v)}
            >
              {ejemplosAbiertos
                ? "Cerrar ejemplos"
                : "Ver ejemplos con números"}
            </button>
            {ejemplosAbiertos && sombra.ejemplosTabla?.length ? (
              <div className="reco-tabla-wrap">
                <table className="reco-tabla">
                  <thead>
                    <tr>
                      <th>Si pasa esto…</th>
                      <th>Qué significa</th>
                      <th>Minuto</th>
                      <th>Entonces hacé esto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sombra.ejemplosTabla.map((ej) => (
                      <tr key={ej.caso}>
                        <td>{ej.caso}</td>
                        <td>{ej.paso}</td>
                        <td className="mono">{ej.mira}</td>
                        <td>{ej.hacer}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}

        {habla.titulo && habla.verbo ? (
          <p className="habla-verbo">{habla.verbo}</p>
        ) : null}
        {habla.parrafos.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        {habla.avisos?.length ? (
          <ul className="habla-avisos">
            {habla.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        ) : null}

        <details className="plan-fijo">
          <summary>El plan de arranque (no cambia mientras corre)</summary>
          {planLectura ? (
            <pre className="informe">{planLectura}</pre>
          ) : (
            <p className="hint">Sin párrafo.</p>
          )}
        </details>

        {filas.length ? (
          <details className="tips-tabla-wrap" open={Boolean(sombra)}>
            <summary className="tips-tabla-titulo">
              Lectura ordenada · tocá una fila
            </summary>
            <table className="tips-tabla">
              <thead>
                <tr>
                  <th>min</th>
                  <th>qué es</th>
                  <th>estado</th>
                  <th>andén</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => {
                  const sel = f.id === filaId;
                  return (
                    <tr
                      key={f.id}
                      className={`${sel ? "sel" : ""}${
                        f.id === "sombra" ? " tip-sombra" : ""
                      }${f.id === "som02-chip" ? " tip-som02" : ""}${
                        f.id === "som02-prod" ? " tip-som02" : ""
                      }${f.id === "faro" ? " tip-faro" : ""}${
                        f.id === "pronostico" ? " tip-pronostico" : ""
                      }${
                        f.id?.startsWith("aviso-primera") ? " tip-aviso" : ""
                      }${f.capa === "piso" || f.id === "urna" ? " tip-piso" : ""}${
                        f.id?.startsWith("pintor-") ? " tip-pintor" : ""
                      }${f.id?.startsWith("extra-") ? " tip-extra" : ""}`}
                      onClick={() => {
                        setFilaId(sel ? null : f.id);
                        setEjemplosFila(false);
                      }}
                    >
                      <td className="mono">
                        {f.minuto == null ? "—" : pad(f.minuto)}
                      </td>
                      <td>{f.tipo}</td>
                      <td>{f.estado}</td>
                      <td className="mono">{f.anden}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {abierta ? (
              <BloqueSiEntonces
                fila={abierta}
                ejemplosAbiertos={ejemplosFila}
                onToggleEjemplos={() => setEjemplosFila((v) => !v)}
              />
            ) : (
              <p className="hint tips-hint">
                Tocá una fila: qué mirás y qué hacer si-entonces (cupo, orillas,
                piso, luces lejos).
              </p>
            )}
          </details>
        ) : null}
      </div>
    </section>
  );
}
