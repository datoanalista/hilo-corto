import { useEffect, useMemo, useRef, useState } from "react";
import { IconHistorico, IconTip } from "./MesaOficialModales.jsx";
import {
  avisoCerca,
  cobraFicha,
  cubre,
  estadoFicha,
  etiquetaMesa,
  pad,
  rolFicha,
  ventanaVista,
  yaPaso,
} from "./mesa.js";

function pct(x) {
  if (x == null) return "—";
  return `${Math.round(x * 100)}%`;
}

function pctClass(x) {
  if (x == null) return "";
  if (x >= 0.5) return "pct-ok";
  if (x >= 0.3) return "pct-mid";
  return "pct-bad";
}

function chipsTxt(xs) {
  return (xs || []).map(pad).join("  ");
}

function IconEstadistica() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <rect x="4" y="12" width="4" height="8" fill="currentColor" />
      <rect x="10" y="7" width="4" height="13" fill="currentColor" />
      <rect x="16" y="3" width="4" height="17" fill="currentColor" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        d="M5 13l4.5 4.5L19 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function veredictoHumano(c) {
  if (c.veredicto === "EXACTO") return "tiro exacto";
  if (c.veredicto === "BORDE") {
    const det = String(c.detalle || "");
    const m = det.match(/oficial\s+(\d+)\s+\(([+-]\d+)/);
    if (m) return `vecino ${m[2]}: ${pad(Number(m[1]))}`;
    return "vecino";
  }
  return "tiro fallido";
}

export default function Panel({
  id,
  panel,
  sel,
  onSel,
  live = null,
  statsAbierto,
  onCerrarStats,
  onAbrirStats,
  tipsAbierto,
  onCerrarTips,
  onAbrirTips,
  historicoAbierto,
  onCerrarHistorico,
  onAbrirHistorico,
}) {
  const pred = panel?.prediccion;
  const hist = panel?.historico || [];
  const res = panel?.resumen || {};
  const [histExtra, setHistExtra] = useState(null);

  const histTags = useMemo(
    () => new Set(hist.map((h) => h.for)),
    [hist]
  );
  const selEnPreview = Boolean(sel && histTags.has(sel));

  useEffect(() => {
    if (!sel || selEnPreview) {
      setHistExtra(null);
      return;
    }
    let vivo = true;
    fetch(`/api/tablero/historico?mesa=oficial`, { credentials: "include" })
      .then((r) => r.json())
      .then((j) => {
        if (!vivo || j.ok === false) return;
        setHistExtra(j.historico || []);
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [sel, selEnPreview]);

  const histLookup = histExtra || hist;
  const replay = sel ? histLookup.find((h) => h.for === sel) : null;

  const chips = replay?.chips || pred?.chips || [];
  const tiros = replay
    ? (replay.chips_log || []).map((c) => ({
        minuto: c.minuto,
        flag: c.flag,
        cubre: c.cubre || cubre(c.minuto),
      }))
    : pred?.tiros || [];

  const [T, setT] = useState(0);
  const [foco, setFoco] = useState(null);
  const [marcas, setMarcas] = useState({});
  const [segundoTick, setSegundoTick] = useState(() => new Date().getSeconds());
  const popoverRef = useRef(null);

  useEffect(() => {
    const tick = setInterval(() => setSegundoTick(new Date().getSeconds()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    if (foco == null) return;
    function onFuera(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setFoco(null);
      }
    }
    function onTecla(e) {
      if (e.key === "Escape") setFoco(null);
    }
    document.addEventListener("mousedown", onFuera);
    document.addEventListener("keydown", onTecla);
    return () => {
      document.removeEventListener("mousedown", onFuera);
      document.removeEventListener("keydown", onTecla);
    };
  }, [foco]);

  const lucesMarca = useMemo(
    () =>
      Object.values(marcas)
        .filter((x) => x.acerto && x.minuto != null)
        .map((x) => x.minuto),
    [marcas]
  );

  const oficiales = useMemo(() => {
    if (replay) return replay.oficiales || [];
    return [...new Set([...(live?.luces || []), ...lucesMarca])];
  }, [replay, live?.luces, lucesMarca]);

  const verdesPorMinuto = useMemo(() => {
    const map = new Map();
    for (const v of live?.verdes || []) map.set(v.minuto, v);
    return map;
  }, [live?.verdes]);

  const enHora = Boolean(live && !live.fuera && live.reloj);
  const bloqueado = !replay && live?.habilitado === false;
  const sosteniendoHora = Boolean(live?.sosteniendoHora);
  const ahora = replay
    ? null
    : sosteniendoHora
      ? live?.ultimoMinuto != null
        ? live.ultimoMinuto
        : 59
      : enHora
        ? live.reloj.minuto
        : live?.ultimoMinuto != null
          ? live.ultimoMinuto
          : null;

  useEffect(() => {
    setT(ahora ?? 0);
    setFoco(null);
    setMarcas({});
  }, [sel, pred?.for]);

  useEffect(() => {
    if (replay) return;
    if (ahora != null) setT(ahora);
  }, [ahora, replay]);

  const esPleno = (m) =>
    (tiros || []).some((t) => t.minuto === m && t.flag === "SEGURO");

  useEffect(() => {
    if (replay) return;
    const luces = live?.luces || [];
    const hasta = live?.confirmadoHasta ?? -1;
    setMarcas((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const m of chips || []) {
        if (next[m]) continue;
        if (!yaPaso(m, T)) continue;
        if (cobraFicha(m, luces).length) continue;
        if (!ventanaVista(m, hasta, esPleno(m))) continue;
        next[m] = { acerto: false, minuto: null };
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [replay, live?.luces, live?.confirmadoHasta, T, chips, tiros]);

  if (!panel) {
    return (
      <section className={`pane pane-${id}`}>
        <p className="hint">Sin datos todavía.</p>
      </section>
    );
  }

  const tirosOrden =
    tiros && tiros.length
      ? tiros
      : (chips || []).map((m) => ({
          minuto: m,
          flag: "TIBIO",
          cubre: cubre(m),
        }));

  return (
    <section className={`pane pane-${id}`}>
      <div className="mesa-grid mesa-grid-solo">
        <div className="card">
          <div className="card-titulo-fila">
            <div className="card-titulo-texto">
              <h2>{`Predicciones para ${pred?.for || replay?.for || ""}`}</h2>
              {panel?.nombre ? (
                <p
                  className={`mesa-badge${panel.beta ? " mesa-badge-beta" : ""}`}
                >
                  {etiquetaMesa(panel)}
                  {panel.beta ? " · sombra" : ""}
                </p>
              ) : null}
            </div>
            <div className="card-titulo-acciones">
              <button
                type="button"
                className="live-stats-btn"
                title="Tips de la hora"
                aria-label="Tips de la hora"
                onClick={() => onAbrirTips?.()}
              >
                <IconTip />
              </button>
              <button
                type="button"
                className="live-stats-btn"
                title="Mesas anteriores"
                aria-label="Mesas anteriores"
                onClick={() => onAbrirHistorico?.()}
              >
                <IconHistorico />
              </button>
              <button
                type="button"
                className="live-stats-btn"
                title="Ver estadísticas"
                aria-label="Ver estadísticas"
                onClick={() => onAbrirStats?.()}
              >
                <IconEstadistica />
              </button>
            </div>
          </div>
          {pred ? (
            <>
              <div className="anden-pista" aria-hidden="true">
                <i style={{ width: `${(T / 59) * 100}%` }} />
                <b className="m20" />
                <b className="m40" />
              </div>
              <div className="anden-cortes">
                <span>00</span>
                <span>20</span>
                <span>40</span>
                <span>59</span>
              </div>
              <div className={`chips${bloqueado ? " card-bloqueada" : ""}`}>
                {tirosOrden.map((t) => {
                  const est = estadoFicha(t.minuto, {
                    T,
                    oficiales,
                    tiro: t,
                    marca: marcas[t.minuto],
                  });
                  const [a, c, b] = cubre(t.minuto);
                  const activo = foco === t.minuto;
                  const segundoActual = T === ahora ? segundoTick : 0;
                  const cerca =
                    !bloqueado &&
                    !replay &&
                    avisoCerca(t.minuto, T, segundoActual);
                  const acerto = est.clave === "cobro";
                  const exacto = acerto && est.etiqueta === "exacto";
                  const vecino = acerto && !exacto;
                  const vecinoSigno = vecino
                    ? String(est.etiqueta).trim().startsWith("-")
                      ? "-"
                      : "+"
                    : null;
                  const fallo = est.etiqueta === "tiro fallido";
                  return (
                    <div
                      className={`chip-wrap${activo ? " chip-wrap-activo" : ""}`}
                      key={t.minuto}
                      ref={activo ? popoverRef : null}
                    >
                      <button
                        type="button"
                        disabled={bloqueado}
                        className={`chip ${t.flag} ${est.clave}${activo ? " foco" : ""}${
                          acerto ? " acerto" : ""
                        }${fallo ? " fallo" : ""}${cerca ? " aviso-cerca" : ""}`}
                        onClick={() => {
                          if (bloqueado) return;
                          setFoco((actual) =>
                            actual === t.minuto ? null : t.minuto
                          );
                          if (!replay && yaPaso(t.minuto, T)) return;
                          setT(t.minuto);
                        }}
                      >
                        <span className="chip-circulo">
                          {exacto ? (
                            <i className="chip-marca ok">
                              <IconCheck />
                            </i>
                          ) : null}
                          {vecino ? (
                            <i className="chip-marca vecino">{vecinoSigno}</i>
                          ) : null}
                          {fallo ? <i className="chip-marca no">✕</i> : null}
                          <b className="chip-minuto">
                            {rolFicha(t) === "ficha"
                              ? `-${pad(t.minuto)}+`
                              : pad(t.minuto)}
                          </b>
                          {rolFicha(t) === "pleno" || rolFicha(t) === "ficha" ? null : (
                            <small className="chip-sub">{`${rolFicha(t)} ${pad(a)}–${pad(c)}–${pad(b)}`}</small>
                          )}
                          <em className="chip-estado">
                            {exacto || vecino || fallo ? null : est.etiqueta}
                          </em>
                        </span>
                      </button>
                      {activo ? (
                        <div
                          className="ficha-popover"
                          role="dialog"
                          aria-label={`Detalle del minuto ${pad(t.minuto)}`}
                        >
                          {fallo ? (
                            <span className="ficha-popover-fallo">Tiro fallido</span>
                          ) : est.hits.length ? (
                            <div className="verdes-lista">
                              {est.hits.map((g) => {
                                const info = verdesPorMinuto.get(g);
                                return (
                                  <span key={g} className="verde-item acerto">
                                    {pad(g)}:<b>G{info?.tipo ?? ""}</b>
                                    {info?.vecino != null ? ` ${info.vecino}x` : ""}
                                  </span>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="ficha-popover-vacio">Sin resultado aún</span>
                          )}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <p className="hint">Sin boleto.</p>
          )}
        </div>
      </div>

      {replay ? (
        <div className="card">
          <h2>Qué pasó en {replay.for}</h2>
          <p className="meta">
            Luces {chipsTxt(replay.oficiales)} · tus fichas cobraron{" "}
            {replay.g_ok}/{replay.g_of} en el blanco, {replay.pm1} de vecino ·
            banda {pct(replay.pct)}
          </p>
          <div className="log">
            {(replay.chips_log || []).map((c) => (
              <div key={`${c.minuto}-${c.flag}`} className={c.veredicto}>
                {veredictoHumano(c)}
              </div>
            ))}
          </div>
          <button type="button" className="ghost" onClick={() => onSel(null)}>
            Volver a la mesa viva
          </button>
        </div>
      ) : null}

      {statsAbierto ? (
        <div className="modal-back" onClick={() => onCerrarStats?.()} role="presentation">
          <div className="modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h2>Estadísticas</h2>
            <div className="kpis kpis-pane">
              <div className="kpi">
                <b>{res.n ?? "—"}</b>
                <span>horas leídas</span>
              </div>
              <div className="kpi">
                <b>{pct(res.banda)}</b>
                <span>luces en tus fichas</span>
              </div>
              <div className="kpi">
                <b>
                  {res.horas_con_banda ?? "—"}/{res.n ?? "—"}
                </b>
                <span>horas que cobraron</span>
              </div>
              <div className="kpi">
                <b>
                  {res.seguro_n
                    ? `${res.seguro_ok}/${res.seguro_n}`
                    : "—"}
                </b>
                <span>plenos que pagaron</span>
              </div>
            </div>
            <div className="row">
              <button className="ghost" type="button" onClick={() => onCerrarStats?.()}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
