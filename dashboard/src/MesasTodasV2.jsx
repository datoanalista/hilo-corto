import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  dispararApuestaManualX3,
  fetchCuentasEstado,
  leerMontoManualPreferido,
} from "./apuestaManualApi.js";
import {
  cobraFicha,
  estadoFicha,
  etiquetaMesa,
  normalizePoolRowId,
  panelPool9,
  pinnedPoolIdsForUI,
  poolHiddenInUI,
  ventanaVista,
  yaPaso,
} from "./mesa.js";
import { tipSiguienteG, enZonaPool7 } from "./tipProxima.js";
import { chipsLiveRc } from "./liveRc.js";
import { CierreAbiertoBtn } from "./CierreAbiertoBtn.jsx";
import { BloquePerfilBtn } from "./BloquePerfilBtn.jsx";
import { FuerzaBtn } from "./FuerzaBtn.jsx";
import OlaPostSnBtn from "./OlaPostSnBtn.jsx";
import V2PlayheadLayer from "./V2PlayheadLayer.jsx";
import V2PoolRow from "./V2PoolRow.jsx";
import { ALARMA_GO_MS } from "./alarmaGo.js";
import {
  bloqueDeMinuto,
  computeTPlay,
  cortesBloques,
  gradientBloques,
  pesosBloques,
  posicionesMarksFila,
} from "./v2Layout.js";

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

function cmpG(a, b) {
  const la = a.liveSt;
  const lb = b.liveSt;
  if (lb.exacto !== la.exacto) return lb.exacto - la.exacto;
  if (lb.scoreLive !== la.scoreLive) return lb.scoreLive - la.scoreLive;
  if (la.fallo !== lb.fallo) return la.fallo - lb.fallo;
  return tieId(a, b);
}

/** Score = exacto + ±1 (banda d≤1). Empate: id de pool. */
function cmpScore(a, b) {
  const la = a.liveSt;
  const lb = b.liveSt;
  if (lb.scoreLive !== la.scoreLive) return lb.scoreLive - la.scoreLive;
  return tieId(a, b);
}

/** Orden estable por nº de Pool (no reordenar cuando cambia el score live). */
function cmpFijo(a, b) {
  const na = Number.parseInt(String(a.etiqueta || "").replace(/\D/g, ""), 10);
  const nb = Number.parseInt(String(b.etiqueta || "").replace(/\D/g, ""), 10);
  if (Number.isFinite(na) && Number.isFinite(nb) && na !== nb) return na - nb;
  return tieId(a, b);
}

/** Etiqueta vista V2: Pool 0 … Pool 9 */
function etiquetaLinea(panel, lineId) {
  if (!panel) return "—";
  if (lineId === "inter2" || panel.inter2 || panel.id === "inter2")
    return "Pool 8";
  if (lineId === "live-rc" || panel.liveRc || panel.id === "live-rc")
    return "Pool 10";
  if (lineId === "lc-01" || panel.lc || panel.id === "lc-01") return "Pool 7";
  if (
    lineId === "pool-9" ||
    lineId === "oficial-classic" ||
    panel.pool9 ||
    panel.classic ||
    panel.id === "pool-9" ||
    panel.id === "oficial-classic"
  )
    return "Pool 9";
  if (lineId === "oficial" || panel.id === "oficial") return "Pool 0";
  const map = {
    oficial: "Pool 0",
    "pool-9": "Pool 9",
    "beta-v1": "Pool 1",
    "beta-v3": "Pool 2",
    "beta-v4": "Pool 3",
    "beta-v2": "Pool 4",
    "beta-v5": "Pool 5",
  };
  if (lineId && map[lineId]) return map[lineId];
  if (panel.id && map[panel.id]) return map[panel.id];
  const m = etiquetaMesa(panel).match(/(\d+)/);
  return m ? `Pool ${m[1]}` : "Pool";
}

function MesasTodasV2Inner({
  mesas,
  catalogo,
  live,
  extraccionAbierta = false,
  onExtraccion,
  onAbrirMesa,
}) {
  const orden = catalogo?.length
    ? catalogo.map((c) => c.id)
    : ["oficial", "beta-v1", "beta-v2", "beta-v3", "beta-v4", "beta-v5"];

  const [hoverTip, setHoverTip] = useState(null);
  const [hoverBloque, setHoverBloque] = useState(null);
  const [hoverG, setHoverG] = useState(null);
  // Pool 7 anclado; el resto se reordena a cada G por scoreLive (exacto + ±1).
  const modoOrden = "score";
  const [filaActiva, setFilaActiva] = useState(null);
  // Colapsado: solo Pool 7. Clic en Pool 7 → expande el resto.
  const [poolsExpandidos, setPoolsExpandidos] = useState(false);
  // Go!: solo parpadeo (sin sonido) · 38 s por tiro, luego spin.
  const [goPulse, setGoPulse] = useState(false);
  // Alarma Pool-7: parpadeo chip (el MP3 lo dispara AlarmaGoBtn en el header).
  const [p7Pulse, setP7Pulse] = useState(false);
  const [manualBusy, setManualBusy] = useState(false);
  const [cuentasEstado, setCuentasEstado] = useState(null);

  const pollCuentas = useCallback(async () => {
    try {
      const j = await fetchCuentasEstado();
      if (j.ok) setCuentasEstado(j);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    pollCuentas();
    let lastSeq = 0;
    const revisarPulso = async () => {
      try {
        const r = await fetch("/api/jokerbets/ui-pulse", { credentials: "include" });
        if (r.status === 401) return;
        const j = await r.json();
        const seq = j?.pulse?.seq || 0;
        if (seq && seq !== lastSeq) {
          lastSeq = seq;
          await pollCuentas();
        }
      } catch {
        /* ignore */
      }
    };
    const id = setInterval(revisarPulso, 8000);
    return () => clearInterval(id);
  }, [pollCuentas]);

  const manualMonto = leerMontoManualPreferido();
  const manualTotalCuenta = manualMonto * 4;

  async function onApostarX3() {
    if (!cuentasEstado?.corriendo) return;
    setManualBusy(true);
    try {
      await dispararApuestaManualX3(manualMonto);
      await pollCuentas();
    } catch {
      /* mismo flujo que Cuentas: el bot/extracción muestra el error en logs */
    } finally {
      setManualBusy(false);
    }
  }

  const enHora = Boolean(live && !live.fuera && live.reloj);
  const bloqueado = live?.habilitado === false;
  const sosteniendoHora = Boolean(live?.sosteniendoHora);
  const enCursoKey = live?.enCurso || "";
  const goActivo = Boolean(live?.enCurso && live?.goSequia);

  useEffect(() => {
    if (!goActivo) {
      setGoPulse(false);
      return undefined;
    }
    setGoPulse(true);
    const id = setTimeout(() => setGoPulse(false), ALARMA_GO_MS);
    return () => clearTimeout(id);
  }, [goActivo, enCursoKey]);

  const T = useMemo(() => {
    const tPlay = computeTPlay({
      enCursoKey,
      sosteniendoHora,
      ultimoMinuto: live?.ultimoMinuto,
      enHora,
      reloj: live?.reloj,
    });
    return Math.min(59, Math.floor(tPlay));
  }, [
    enCursoKey,
    sosteniendoHora,
    live?.ultimoMinuto,
    live?.reloj,
    enHora,
  ]);

  const tipP7 = live?.tipProx?.tip ?? null;
  const zonaP7 = enZonaPool7(live?.enCurso, tipP7);
  const prevCursoP7 = useRef("");

  useEffect(() => {
    if (!zonaP7) {
      setP7Pulse(false);
      prevCursoP7.current = enCursoKey;
      return undefined;
    }
    const nuevoTiro =
      Boolean(enCursoKey) && enCursoKey !== prevCursoP7.current;
    prevCursoP7.current = enCursoKey;
    if (!nuevoTiro) return undefined;

    setP7Pulse(true);
    const id = setTimeout(() => setP7Pulse(false), ALARMA_GO_MS);
    return () => clearTimeout(id);
  }, [zonaP7, enCursoKey]);

  const oficiales = useMemo(
    () => [...new Set(live?.luces || [])],
    [live?.luces]
  );

  const verdesLive = useMemo(() => {
    const fromLive = live?.verdes || [];
    if (fromLive.length) {
      const byMin = new Map();
      for (const v of fromLive) {
        if (v?.minuto == null) continue;
        byMin.set(v.minuto, v);
      }
      return [...byMin.values()].sort((a, b) => a.minuto - b.minuto);
    }
    return oficiales.map((m) => ({ minuto: m, tipo: null, vecino: null }));
  }, [live?.verdes, oficiales]);

  const oficialChips = useMemo(
    () => new Set(mesas?.oficial?.prediccion?.chips || []),
    [mesas]
  );

  const scoreOficial = mesas?.oficial?.resumen?.score_hora;

  const filasBase = useMemo(() => {
    const rows = [];
    const seen = new Set();
    const push = (rawId, panel) => {
      if (!panel) return;
      const id = normalizePoolRowId(rawId, panel);
      if (seen.has(id)) return;
      seen.add(id);
      const pred = panel.prediccion || {};
      const chips = pred.chips || [];
      const tiros = pred.tiros || [];
      const score = panel.resumen?.score_hora;
      const delta =
        scoreOficial != null && score != null ? score - scoreOficial : null;
      rows.push({
        id,
        panel,
        pred,
        chips,
        tiros,
        score,
        delta,
        banda: panel.resumen?.banda,
      });
    };
    for (const rawId of orden) {
      const panel =
        rawId === "pool-9" || rawId === "oficial-classic"
          ? panelPool9(mesas)
          : mesas?.[rawId];
      push(rawId, panel);
    }
    if (mesas?.inter2) push("inter2", mesas.inter2);
    if (panelPool9(mesas)) push("pool-9", panelPool9(mesas));
    return rows;
  }, [orden, mesas, scoreOficial]);

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

  const chipsLiveRC = useMemo(() => chipsLiveRc(oficiales), [oficiales]);
  const chipsLiveRcSet = useMemo(
    () => new Set(chipsLiveRC),
    [chipsLiveRC]
  );

  const chipsOf = (id) => mesas?.[id]?.prediccion?.chips || [];
  const tirosOf = (id) => mesas?.[id]?.prediccion?.tiros || [];

  const mOficial = useMarcasFallo(chipsOf("oficial"), tirosOf("oficial"), live, T);
  const mBeta1 = useMarcasFallo(chipsOf("beta-v1"), tirosOf("beta-v1"), live, T);
  const mBeta2 = useMarcasFallo(chipsOf("beta-v2"), tirosOf("beta-v2"), live, T);
  const mBeta3 = useMarcasFallo(chipsOf("beta-v3"), tirosOf("beta-v3"), live, T);
  const mBeta4 = useMarcasFallo(chipsOf("beta-v4"), tirosOf("beta-v4"), live, T);
  const mBeta5 = useMarcasFallo(chipsOf("beta-v5"), tirosOf("beta-v5"), live, T);
  const mInter2 = useMarcasFallo(chipsOf("inter2"), tirosOf("inter2"), live, T);
  const mPool9 = useMarcasFallo(chipsOf("pool-9"), tirosOf("pool-9"), live, T);
  const marcasLC = useMarcasFallo(chipsLC, [], live, T);
  const marcasLiveRC = useMarcasFallo(chipsLiveRC, [], live, T);
  const marcasById = {
    oficial: mOficial,
    "pool-9": mPool9,
    "beta-v1": mBeta1,
    "beta-v2": mBeta2,
    "beta-v3": mBeta3,
    "beta-v4": mBeta4,
    "beta-v5": mBeta5,
    inter2: mInter2,
    "lc-01": marcasLC,
    "live-rc": marcasLiveRC,
  };

  const filas = useMemo(() => {
    const enriched = filasBase.map((f) => {
      const id = normalizePoolRowId(f.id, f.panel);
      const marcas = marcasById[id] || marcasById[f.id] || {};
      const liveSt = liveStats(f.chips, f.tiros, oficiales, marcas, T);
      return {
        ...f,
        id,
        etiqueta: etiquetaLinea(f.panel, f.id),
        marcas,
        liveSt,
      };
    });
    const liveStLC = liveStats(chipsLC, [], oficiales, marcasLC, T);
    const lcRow = {
      id: "lc-01",
      panel: { id: "lc-01", nombre: "Mesa-7", beta: false, lc: true },
      pred: { chips: chipsLC, tiros: [] },
      chips: chipsLC,
      tiros: [],
      score: null,
      delta: null,
      banda: null,
      etiqueta: "Pool 7",
      marcas: marcasLC,
      liveSt: liveStLC,
    };
    const byId = new Map();
    for (const f of enriched) {
      byId.set(f.id, f);
    }
    byId.set("lc-01", lcRow);
    const pinnedSet = new Set(pinnedPoolIdsForUI());
    const pinned = pinnedPoolIdsForUI()
      .map((id) => byId.get(id))
      .filter(Boolean);
    const rest = [...byId.values()].filter(
      (f) => !pinnedSet.has(f.id) && !poolHiddenInUI(f.id, f.panel, mesas)
    );
    const sorted = rest.sort(
      modoOrden === "fijo" ? cmpFijo : modoOrden === "score" ? cmpScore : cmpG
    );
    return [...pinned, ...sorted];
  }, [
    filasBase,
    mOficial,
    mPool9,
    mBeta1,
    mBeta2,
    mBeta3,
    mBeta4,
    mBeta5,
    mInter2,
    marcasLC,
    marcasLiveRC,
    chipsLC,
    chipsLiveRC,
    oficiales,
    T,
    modoOrden,
  ]);

  const verdesPorMinuto = useMemo(() => {
    const map = new Map();
    for (const v of verdesLive) {
      if (v?.minuto == null) continue;
      map.set(v.minuto, v);
    }
    return map;
  }, [verdesLive]);

  const goHitsSet = useMemo(
    () => new Set(live?.goHits || []),
    [live?.goHits]
  );

  const focoActivo = hoverTip;

  function mostrarTip(id, m) {
    setHoverTip({ id, m });
    setHoverBloque(bloqueDeMinuto(m));
  }

  function ocultarTip(id, m) {
    setHoverTip((cur) =>
      cur && cur.id === id && cur.m === m ? null : cur
    );
  }

  const bloqueCurso = bloqueDeMinuto(T);
  const bloqueExpandido = hoverBloque ?? bloqueCurso;
  const pesos = useMemo(
    () => pesosBloques(bloqueExpandido),
    [bloqueExpandido]
  );
  const cortes = useMemo(() => cortesBloques(pesos), [pesos]);
  const posPorFila = useMemo(() => {
    const out = new Map();
    for (const f of filas) {
      out.set(f.id, posicionesMarksFila(f.chips, pesos, bloqueExpandido));
    }
    return out;
  }, [filas, pesos, bloqueExpandido]);
  const railBg = useMemo(
    () => gradientBloques(pesos, bloqueExpandido),
    [pesos, bloqueExpandido]
  );

  const filasVisibles = useMemo(() => {
    if (poolsExpandidos) return filas;
    return filas.filter((f) => f.id === "lc-01");
  }, [filas, poolsExpandidos]);

  function onRailPointer(e) {
    const rail = e.currentTarget.querySelector(".v2-rail");
    if (!rail) return;
    const rect = rail.getBoundingClientRect();
    if (rect.width <= 0) return;
    if (e.clientX < rect.left || e.clientX > rect.right) return;
    const x = (e.clientX - rect.left) / rect.width;
    let acc = 0;
    for (let i = 0; i < 3; i += 1) {
      acc += pesos[i];
      if (x <= acc + 0.001) {
        setHoverBloque(i);
        return;
      }
    }
    setHoverBloque(2);
  }

  return (
    <section className="v2-board" aria-label="Mesa">
      <div className="v2-bar">
        <div className="v2-bar-estado">
          <CierreAbiertoBtn lectura={live?.cierre} />
          <BloquePerfilBtn lectura={live?.bloquePerfil} />
          {live?.enCurso ? (
            <div
              className={`v2-en-curso${
                !goActivo
                  ? " nogo"
                  : goPulse
                    ? " go pulse"
                    : " go"
              }${live?.goDiag?.tipo ? ` tipo-${live.goDiag.tipo}` : ""}`}
              title={
                live?.goDiag?.tooltip ||
                (live?.goDiag?.tipo === "pasa"
                  ? "Pasa · poda +1 · se deja pasar el pegado"
                  : !goActivo
                    ? "No-Go · fuera de ventana sequía"
                    : "Go! · ventana +2,+3,+4")
              }
            >
              <span className="v2-en-curso-copy">
                <b>{live.enCurso}</b>{" "}
                {live?.goDiag?.tipo === "pasa" ? (
                  <em>{live.goDiag.etiqueta || "Pasa"}</em>
                ) : !goActivo ? (
                  <em>{live?.goDiag?.badge ? `No-Go · ${live.goDiag.badge}` : "No-Go"}</em>
                ) : (
                  <em>{live?.goDiag?.etiqueta || "Go!"}</em>
                )}
              </span>
            </div>
          ) : null}
          {zonaP7 ? (
            <div
              className={`v2-en-curso pool7${p7Pulse ? " pulse" : ""}`}
              title={
                tipP7 != null
                  ? `Pool 7 · tip ${String(tipP7).padStart(2, "0")} · zona ±1 · alarma`
                  : "Pool 7 · zona tip ±1 · alarma"
              }
            >
              <span className="v2-en-curso-copy">
                {p7Pulse ? (
                  <em>Pool-7</em>
                ) : (
                  <span
                    className="v2-go-spin v2-p7-spin"
                    aria-label="Pool 7 · esperando tiro"
                    title="Pool 7 · zona ±1"
                  />
                )}
              </span>
            </div>
          ) : null}
          {live?.fuerza ? (
            <FuerzaBtn lectura={live.fuerza} />
          ) : null}
          {live?.tipProx ? (
            <span
              className={`v2-next${
                live.tipProx.estado === "pasado"
                  ? " searching"
                  : live.tipProx.estado === "calculando"
                    ? " calculando"
                    : ""
              }`}
              title={live.tipProx.why || "tip · sombra"}
            >
              Next:{" "}
              {live.tipProx.estado === "calculando" ? (
                <span
                  className="v2-next-spin"
                  aria-label="calculando próximo tip"
                />
              ) : live.tipProx.estado === "pasado" ? (
                <span
                  className="live-gplus-search"
                  aria-label={`tip ${live.tipProx.label} pasó · esperando G`}
                >
                  <i />
                  <i />
                  <i />
                </span>
              ) : (
                live.tipProx.label
              )}
            </span>
          ) : null}
          {live?.lampara?.ok ? (
            <span
              className="v2-lampara"
              title={live.lampara.tooltip || live.lampara.linea}
            >
              {live.lampara.pill}
            </span>
          ) : null}
          <button
            type="button"
            className="v2-apostador v2-apostador-x3"
            disabled={manualBusy || !cuentasEstado?.corriendo}
            onClick={onApostarX3}
            title={
              cuentasEstado?.corriendo
                ? `Apostar ×3 · rojo, azul y verde · $${manualMonto}/bono · ~$${manualTotalCuenta} por cuenta`
                : "Inicia Chrome (extracción) antes de apostar manual"
            }
          >
            {manualBusy
              ? "…"
              : cuentasEstado?.manual?.pendiente
                ? "Enviando ×3…"
                : "Apostar ×3"}
          </button>
          <OlaPostSnBtn lectura={live?.olaPostSn} />
          {live?.costuraH15 ? (
            <span
              className="v2-costura-h15"
              title={`${live.costuraH15.linea} ${live.costuraH15.detalle || ""}`}
            >
              {live.costuraH15.pill}
            </span>
          ) : null}
        </div>
        <div className="v2-bar-acciones">
          <button
            type="button"
            className={`nav-cta${extraccionAbierta ? " activo" : ""}${
              live?.extraccionPausada ? " pausado" : ""
            }`}
            onClick={() => onExtraccion?.()}
            title={
              live?.extraccionPausada
                ? "Extracción en pausa manual (sala detenida)"
                : undefined
            }
          >
            {live?.extraccionPausada ? "Live ⏸" : "Live"}
          </button>
        </div>
      </div>

      <div className="v2-stage">
        <V2PlayheadLayer
          enCursoKey={enCursoKey}
          sosteniendoHora={sosteniendoHora}
          ultimoMinuto={live?.ultimoMinuto}
          enHora={enHora}
          pesos={pesos}
          verdesLive={verdesLive}
          goHitsSet={goHitsSet}
          hoverG={hoverG}
          setHoverG={setHoverG}
          setHoverBloque={setHoverBloque}
        >
          {({ ruler, overlay }) => (
            <>
              {ruler}
              <div
                className="v2-body"
                onMouseMove={onRailPointer}
                onMouseLeave={() => setHoverBloque(null)}
              >
                {overlay}
                <div className="v2-lista">
                  {filasVisibles.map((f) => (
                    <V2PoolRow
                      key={f.id}
                      f={f}
                      T={T}
                      bloqueado={bloqueado}
                      oficiales={oficiales}
                      oficialChips={oficialChips}
                      chipsLiveRcSet={chipsLiveRcSet}
                      pesos={pesos}
                      bloqueExpandido={bloqueExpandido}
                      posMap={posPorFila.get(f.id)}
                      railBg={railBg}
                      cortes={cortes}
                      focoActivo={focoActivo}
                      filaActiva={filaActiva}
                      modoOrden={modoOrden}
                      verdesPorMinuto={verdesPorMinuto}
                      poolsExpandidos={poolsExpandidos}
                      onTogglePoolsExpand={
                        f.id === "lc-01"
                          ? () => setPoolsExpandidos((v) => !v)
                          : undefined
                      }
                      onAbrirMesa={onAbrirMesa}
                      onFilaEnter={setFilaActiva}
                      onFilaLeave={(id) =>
                        setFilaActiva((cur) => (cur === id ? null : cur))
                      }
                      onShowTip={mostrarTip}
                      onHideTip={ocultarTip}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </V2PlayheadLayer>
      </div>
    </section>
  );
}

const MesasTodasV2 = memo(MesasTodasV2Inner);

export default MesasTodasV2;