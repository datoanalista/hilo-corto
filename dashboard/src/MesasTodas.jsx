import { useEffect, useMemo, useState } from "react";
import {
  avisoCerca,
  chipsPorBloque,
  cobraFicha,
  estadoFicha,
  etiquetaMesa,
  pad,
  ventanaVista,
  yaPaso,
} from "./mesa.js";
import { tipSiguienteG } from "./tipProxima.js";

function estadoChip(m, tiros, oficiales, marcas, T) {
  const tiro =
    (tiros || []).find((t) => t.minuto === m) || {
      minuto: m,
      flag: "TIBIO",
    };
  return estadoFicha(m, { T, oficiales, tiro, marca: marcas?.[m] });
}

function useMarcasFallo(chips, tiros, live, T) {
  const [marcas, setMarcas] = useState({});
  useEffect(() => {
    setMarcas({});
  }, [chips?.join(","), live?.tag]);

  useEffect(() => {
    const luces = live?.luces || [];
    const hasta = live?.confirmadoHasta ?? -1;
    const esPleno = (m) =>
      (tiros || []).some((t) => t.minuto === m && t.flag === "SEGURO");
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
  }, [live?.luces, live?.confirmadoHasta, T, chips, tiros]);

  return marcas;
}

function liveStats(chips, tiros, oficiales, marcas, T) {
  let exacto = 0;
  let vecino = 0;
  let fallo = 0;
  let pendiente = 0;
  for (const m of chips || []) {
    const est = estadoChip(m, tiros, oficiales, marcas, T);
    if (est.clave === "cobro" && est.etiqueta === "exacto") exacto += 1;
    else if (est.clave === "cobro") vecino += 1;
    else if (est.etiqueta === "tiro fallido") fallo += 1;
    else pendiente += 1;
  }
  return { exacto, vecino, fallo, pendiente, scoreLive: exacto + vecino };
}

function tieId(a, b) {
  if (a.id === "oficial") return -1;
  if (b.id === "oficial") return 1;
  return a.id.localeCompare(b.id);
}

/** G = solo exactos (acertadas). */
function cmpG(a, b) {
  const la = a.liveSt;
  const lb = b.liveSt;
  if (lb.exacto !== la.exacto) return lb.exacto - la.exacto;
  if (lb.scoreLive !== la.scoreLive) return lb.scoreLive - la.scoreLive;
  if (la.fallo !== lb.fallo) return la.fallo - lb.fallo;
  return tieId(a, b);
}

/** Score = G exacto + ±1. */
function cmpScore(a, b) {
  const la = a.liveSt;
  const lb = b.liveSt;
  if (lb.scoreLive !== la.scoreLive) return lb.scoreLive - la.scoreLive;
  if (lb.exacto !== la.exacto) return lb.exacto - la.exacto;
  if (lb.vecino !== la.vecino) return lb.vecino - la.vecino;
  if (la.fallo !== lb.fallo) return la.fallo - lb.fallo;
  return tieId(a, b);
}

export default function MesasTodas({
  mesas,
  catalogo,
  live,
  onAbrirMesa,
}) {
  const orden = catalogo?.length
    ? catalogo.map((c) => c.id)
    : ["oficial", "beta-v1", "beta-v2", "beta-v3", "beta-v4", "beta-v5"];

  const enHora = Boolean(live && !live.fuera && live.reloj);
  const bloqueado = live?.habilitado === false;
  const sosteniendoHora = Boolean(live?.sosteniendoHora);
  const T = sosteniendoHora
    ? live?.ultimoMinuto != null
      ? live.ultimoMinuto
      : 59
    : enHora
      ? live.reloj.minuto
      : live?.ultimoMinuto != null
        ? live.ultimoMinuto
        : 0;
  const ahora = sosteniendoHora
    ? live?.ultimoMinuto != null
      ? live.ultimoMinuto
      : 59
    : live && !live.fuera && live.reloj
      ? live.reloj.minuto
      : live?.ultimoMinuto != null
        ? live.ultimoMinuto
        : null;
  const [segundoTick, setSegundoTick] = useState(() => new Date().getSeconds());
  const [focoMin, setFocoMin] = useState(null);
  const [hoverMin, setHoverMin] = useState(null);
  const [modoOrden, setModoOrden] = useState("g"); // g | score
  const [filaActiva, setFilaActiva] = useState(null);

  useEffect(() => {
    const id = setInterval(() => setSegundoTick(new Date().getSeconds()), 1000);
    return () => clearInterval(id);
  }, []);

  const oficiales = useMemo(
    () => [...new Set(live?.luces || [])],
    [live?.luces]
  );

  const oficialChips = useMemo(
    () => new Set(mesas?.oficial?.prediccion?.chips || []),
    [mesas]
  );

  const scoreOficial = mesas?.oficial?.resumen?.score_hora;

  const filasBase = useMemo(() => {
    return orden
      .map((id) => {
        const panel = mesas?.[id];
        if (!panel) return null;
        const pred = panel.prediccion || {};
        const chips = pred.chips || [];
        const tiros = pred.tiros || [];
        const score = panel.resumen?.score_hora;
        const delta =
          scoreOficial != null && score != null ? score - scoreOficial : null;
        return {
          id,
          panel,
          pred,
          chips,
          tiros,
          score,
          delta,
          banda: panel.resumen?.banda,
        };
      })
      .filter(Boolean);
  }, [orden, mesas, scoreOficial]);

  /** Chips Mesa-7 = tips LC-01 de la hora (pasados + tip vivo). */
  const chipsLC = useMemo(() => {
    const luces = [...oficiales].sort((a, b) => a - b);
    const tips = [];
    for (let i = 0; i < luces.length; i += 1) {
      const prev = tipSiguienteG({
        luces: luces.slice(0, i),
        minutoAhora: null,
      });
      if (prev.tip != null) tips.push(prev.tip);
    }
    const cur = tipSiguienteG({ luces, minutoAhora: null });
    if (cur.tip != null) tips.push(cur.tip);
    return [...new Set(tips)].sort((a, b) => a - b);
  }, [oficiales]);

  // marcas por mesa (hooks fijos: 6 betas + LC)
  const m0 = useMarcasFallo(
    filasBase[0]?.chips,
    filasBase[0]?.tiros,
    live,
    T
  );
  const m1 = useMarcasFallo(
    filasBase[1]?.chips,
    filasBase[1]?.tiros,
    live,
    T
  );
  const m2 = useMarcasFallo(
    filasBase[2]?.chips,
    filasBase[2]?.tiros,
    live,
    T
  );
  const m3 = useMarcasFallo(
    filasBase[3]?.chips,
    filasBase[3]?.tiros,
    live,
    T
  );
  const m4 = useMarcasFallo(
    filasBase[4]?.chips,
    filasBase[4]?.tiros,
    live,
    T
  );
  const m5 = useMarcasFallo(
    filasBase[5]?.chips,
    filasBase[5]?.tiros,
    live,
    T
  );
  const marcasLC = useMarcasFallo(chipsLC, [], live, T);
  const marcasArr = [m0, m1, m2, m3, m4, m5];

  const filas = useMemo(() => {
    const enriched = filasBase.map((f, i) => {
      const marcas = marcasArr[i] || {};
      const liveSt = liveStats(f.chips, f.tiros, oficiales, marcas, T);
      return { ...f, marcas, liveSt };
    });
    const sorted = [...enriched].sort(modoOrden === "score" ? cmpScore : cmpG);
    const liveStLC = liveStats(chipsLC, [], oficiales, marcasLC, T);
    const filaLC = {
      id: "lc-01",
      panel: {
        id: "lc-01",
        nombre: "Mesa-7",
        beta: false,
        lc: true,
      },
      pred: { chips: chipsLC, tiros: [] },
      chips: chipsLC,
      tiros: [],
      score: null,
      delta: null,
      banda: null,
      marcas: marcasLC,
      liveSt: liveStLC,
    };
    return [filaLC, ...sorted];
  }, [
    filasBase,
    m0,
    m1,
    m2,
    m3,
    m4,
    m5,
    marcasLC,
    chipsLC,
    oficiales,
    T,
    modoOrden,
  ]);

  const focoActivo = focoMin ?? hoverMin;

  const quienTieneFoco = useMemo(() => {
    if (focoActivo == null) return [];
    return filas
      .filter((f) => f.chips.includes(focoActivo))
      .map((f) => {
        const est = estadoChip(
          focoActivo,
          f.tiros,
          oficiales,
          f.marcas,
          T
        );
        return { id: f.id, nombre: etiquetaMesa(f.panel), est };
      });
  }, [focoActivo, filas, oficiales, T]);

  function toggleFoco(m) {
    setFocoMin((prev) => (prev === m ? null : m));
  }

  return (
    <section className="mesas-board">
      <div className="mesas-board-wrap">
        <div className="mesas-board-bar" role="toolbar" aria-label="Orden">
          <div className="board-dual" role="group">
            <button
              type="button"
              className={`board-dual-opt${modoOrden === "g" ? " on" : ""}`}
              onClick={() => setModoOrden("g")}
              title="Ordenar por G exactas"
            >
              G
            </button>
            <button
              type="button"
              className={`board-dual-opt${modoOrden === "score" ? " on" : ""}`}
              onClick={() => setModoOrden("score")}
              title="Ordenar por Score (G + ±1)"
            >
              Score
            </button>
          </div>
          {focoMin != null ? (
            <button
              type="button"
              className="board-tool"
              onClick={() => setFocoMin(null)}
            >
              Limpiar foco {pad(focoMin)}
            </button>
          ) : null}
        </div>

        <div className="mesas-board-lista">
        {filas.map((f) => {
          const activa = filaActiva === f.id;
          const chipsLista = f.chips;
          const valorTotal = f.liveSt.scoreLive;
          const cercaAlguna = chipsLista.some(
            (m) =>
              !bloqueado &&
              avisoCerca(m, T, T === ahora ? segundoTick : 0)
          );
          const metaTitle = `k${f.chips.length} · hist ${
            f.score != null ? f.score.toFixed(2) : "—"
          }${
            f.delta != null
              ? ` · Δ${f.delta > 0 ? "+" : ""}${f.delta.toFixed(2)}`
              : ""
          } · total ${valorTotal} (${f.liveSt.exacto}✓ + ${f.liveSt.vecino}±) · ${f.liveSt.fallo}×`;
          return (
            <article
              key={f.id}
              className={`mesa-row mesa-row-line${
                f.panel.lc
                  ? " es-lc"
                  : f.panel.beta
                    ? " es-beta"
                    : " es-oficial"
              }${activa ? " activa" : ""}${cercaAlguna ? " hay-cerca" : ""}`}
              title={metaTitle}
              onMouseEnter={() => setFilaActiva(f.id)}
              onMouseLeave={() =>
                setFilaActiva((id) => (id === f.id ? null : id))
              }
            >
              {onAbrirMesa && !f.panel.lc ? (
                <button
                  type="button"
                  className="mesa-row-link"
                  onClick={() => onAbrirMesa(f.id)}
                  title={`Abrir ${etiquetaMesa(f.panel)} · ${metaTitle}`}
                >
                  {etiquetaMesa(f.panel)}
                </button>
              ) : (
                <strong className="mesa-row-link-static">
                  {etiquetaMesa(f.panel)}
                </strong>
              )}
              <span
                className="mesa-g"
                title={`Total ${valorTotal} (${f.liveSt.exacto} G + ${f.liveSt.vecino} ±1)`}
              >
                {valorTotal}
              </span>
              <div
                className={`mesa-row-chips${
                  bloqueado ? " card-bloqueada" : ""
                }`}
              >
                {chipsLista.length === 0 ? (
                  <span className="mesa-row-vacio">sin fichas</span>
                ) : (
                  chipsPorBloque(chipsLista).map((bloque) => (
                    <div
                      key={bloque.key}
                      className="mesa-bloque"
                      data-rango={bloque.label}
                    >
                      {bloque.chips.length === 0 ? (
                        <span className="mesa-bloque-vacio" aria-hidden="true" />
                      ) : (
                        bloque.chips.map((m) => {
                          const est = estadoChip(
                            m,
                            f.tiros,
                            oficiales,
                            f.marcas,
                            T
                          );
                          const acerto = est.clave === "cobro";
                          const exacto =
                            acerto && est.etiqueta === "exacto";
                          const vecino = acerto && !exacto;
                          const fallo = est.etiqueta === "tiro fallido";
                          const esDiff =
                            f.panel.beta && !f.panel.lc && !oficialChips.has(m);
                          const cerca =
                            !bloqueado &&
                            avisoCerca(
                              m,
                              T,
                              T === ahora ? segundoTick : 0
                            );
                          const enfocado = focoActivo === m;
                          const atenuado =
                            focoActivo != null && focoActivo !== m;
                          return (
                            <button
                              type="button"
                              key={m}
                              disabled={bloqueado}
                              className={`mchip${exacto ? " exacto" : ""}${
                                vecino ? " vecino" : ""
                              }${fallo ? " fallo" : ""}${
                                cerca ? " cerca" : ""
                              }${esDiff ? " diff" : ""}${
                                enfocado ? " foco" : ""
                              }${atenuado ? " dim" : ""}`}
                              title={`${pad(m)} · ${est.etiqueta}${
                                esDiff ? " · no está en oficial" : ""
                              }`}
                              onMouseEnter={() => setHoverMin(m)}
                              onMouseLeave={() => setHoverMin(null)}
                              onClick={() => toggleFoco(m)}
                            >
                              {fallo ? (
                                <span className="mx">×</span>
                              ) : null}
                              {exacto ? (
                                <span className="mx">✓</span>
                              ) : null}
                              {vecino ? (
                                <span className="mx">
                                  {String(est.etiqueta)
                                    .trim()
                                    .startsWith("-")
                                    ? "−"
                                    : "+"}
                                </span>
                              ) : null}
                              {pad(m)}
                            </button>
                          );
                        })
                      )}
                    </div>
                  ))
                )}
              </div>
            </article>
          );
        })}
        </div>
      </div>

      {focoActivo != null ? (
        <aside className="mesas-board-foco" aria-live="polite">
          <strong>Minuto {pad(focoActivo)}</strong>
          <span className="dot">·</span>
          {quienTieneFoco.length === 0 ? (
            <span>ninguna mesa lo tiene</span>
          ) : (
            <span>
              {quienTieneFoco
                .map((q) => {
                  const tag =
                    q.est.etiqueta === "exacto"
                      ? "✓"
                      : q.est.etiqueta === "tiro fallido"
                        ? "×"
                        : q.est.clave === "cobro"
                          ? "±"
                          : "·";
                  return `${q.nombre} ${tag}`;
                })
                .join("  ·  ")}
            </span>
          )}
          {oficiales.includes(focoActivo) ? (
            <>
              <span className="dot">·</span>
              <span className="foco-luz">luz live en ese minuto</span>
            </>
          ) : null}
        </aside>
      ) : null}
    </section>
  );
}
