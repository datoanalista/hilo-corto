import { FRANJAS, MAPA_TRAIN_H } from "./mapaInfo.js";

/** Intensidad 0–1 desde med sum histórico. */
function medT(med, lo = 480, hi = 760) {
  return Math.max(0, Math.min(1, (med - lo) / (hi - lo)));
}

function celdaStyle(med) {
  const t = medT(med);
  const r = Math.round(38 + t * 158);
  const g = Math.round(72 + t * 91);
  const b = Math.round(64 + t * 26);
  const a = 0.22 + t * 0.58;
  return {
    background: `rgba(${r}, ${g}, ${b}, ${a})`,
    borderColor: `rgba(${r}, ${g}, ${b}, ${0.35 + t * 0.45})`,
  };
}

function modaClass(moda) {
  if (moda === "muy_apag") return "mapa-moda-apag";
  if (moda === "opaco") return "mapa-moda-opaco";
  if (moda === "fuerte" || moda === "muy_fuerte") return "mapa-moda-brill";
  if (moda === "sn") return "mapa-moda-sn";
  return "mapa-moda-norm";
}

export default function MapaPanel({ mapa, costuras = null, costura = null }) {
  if (!mapa) return null;

  const { franja, celda, celdas, comparacion, hod } = mapa;
  const lista = costuras?.length
    ? costuras
    : costura?.ok
      ? [costura]
      : [];
  const costuraVisible = lista.filter(
    (c) => c.ok && (hod === c.fromHod || hod === c.toHod)
  );

  return (
    <section className="mapa-panel" aria-label="Mapa hod franja">
      {costuraVisible.map((c) => (
        <div
          key={c.pairId}
          className={`mapa-costura tono-${c.tono || "mute"}${c.alerta ? " alerta" : ""}`}
          role={c.alerta ? "alert" : undefined}
          aria-label={`Costura h${c.fromHod} h${c.toHod}`}
        >
          <strong>{c.expectativa?.titulo || c.titulo}</strong>
          <span>
            h{String(c.fromHod).padStart(2, "0")}{" "}
            {(c.origen || c.h14)?.enCurso ? "va" : "cerró"}{" "}
            {(c.origen || c.h14)?.bandaLabel}
            {(c.origen || c.h14)?.sumG != null
              ? ` · ${(c.origen || c.h14).sumG} lm`
              : ""}
          </span>
        </div>
      ))}
      <header className="mapa-head">
        <div>
          <h3 className="proy-seccion-titulo">Mapa · cinta</h3>
          <p className="mapa-sub">
            {MAPA_TRAIN_H} h train · med sum por hod
          </p>
        </div>
        <div className="mapa-leyenda" aria-hidden="true">
          <span className="mapa-leyenda-lo">480</span>
          <span className="mapa-leyenda-bar" />
          <span className="mapa-leyenda-hi">760+</span>
        </div>
      </header>

      <div className="mapa-grid-wrap">
        <div className="mapa-grid" role="grid" aria-label="Horas del día">
          {FRANJAS.map((f) => (
            <div key={f.id} className="mapa-fila" role="row">
              <div
                className={`mapa-fila-label${franja.id === f.id ? " on" : ""}`}
                role="rowheader"
              >
                <span>{f.label}</span>
                <small>{mapa.franja.id === f.id ? `${franja.pGen}% gen` : ""}</small>
              </div>
              <div className="mapa-fila-celdas" role="presentation">
                {f.hrs.map((hr) => {
                  const c = celdas.find((x) => x.hod === hr);
                  if (!c) return null;
                  const sty = celdaStyle(c.med);
                  const esActual = c.actual;
                  return (
                    <div
                      key={hr}
                      className={[
                        "mapa-celda",
                        esActual ? "actual" : "",
                        c.olor ? "olor" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      style={sty}
                      title={`h${String(hr).padStart(2, "0")} · med ${c.med} · ${c.pGen}% gen · ${c.pOp}% op · moda ${c.modaLabel || c.moda}`}
                      role="gridcell"
                      aria-current={esActual ? "true" : undefined}
                    >
                      <span className="mapa-celda-hod">
                        {String(hr).padStart(2, "0")}
                      </span>
                      <span className="mapa-celda-med">{c.med}</span>
                      <span
                        className={`mapa-celda-moda ${modaClass(c.moda)}`}
                        aria-hidden="true"
                      />
                      {c.pGen >= 25 ? (
                        <span className="mapa-celda-gen" aria-hidden="true">
                          {c.pGen}
                        </span>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mapa-ahora">
        <div className="mapa-ahora-main">
          <strong>
            h{String(hod).padStart(2, "0")} · {franja.label}
          </strong>
          <span>
            Hist med {celda.med} · moda {celda.moda}
            {celda.olor ? " · olor" : ""}
          </span>
        </div>
        {comparacion ? (
          <div
            className={`mapa-ahora-delta${
              comparacion.delta >= 40
                ? " arriba"
                : comparacion.delta <= -40
                  ? " abajo"
                  : ""
            }`}
          >
            <em>Luz ahora</em>
            <b>{comparacion.acum}</b>
            <small>{comparacion.texto || "—"}</small>
          </div>
        ) : null}
      </div>

      <div className="mapa-franja-perfil">
        <div className="mapa-franja-titulo">
          <span>Perfil {franja.label.toLowerCase()}</span>
          <span className="mapa-franja-meta">
            med {franja.med} · +{franja.deltaBrill} en días brill.
          </span>
        </div>
        <div
          className="mapa-stack"
          role="img"
          aria-label={`Distribución de bandas en ${franja.label}`}
        >
          {franja.stack.map((seg) =>
            seg.pct > 0 ? (
              <span
                key={seg.id}
                className={seg.cls}
                style={{ flexGrow: seg.pct }}
                title={`${seg.id.replace("_", " ")} ${seg.pct}%`}
              />
            ) : null
          )}
        </div>
        <div className="mapa-stack-leyenda">
          <span>apag</span>
          <span>opaco</span>
          <span>normal</span>
          <span>fuerte+</span>
        </div>
      </div>
    </section>
  );
}
