import { useEffect, useMemo, useRef, useState } from "react";
import {
  NOMBRES_G,
  TIPOS_G,
  esTodos,
  etiquetaHora,
  filtrarRecords,
  horaBono,
  ordenarRecords,
  toggleTipo,
} from "./recordsInfo.js";

export function IconRecords({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <path
        d="M7.2 4.4h9.6v2.6c0 3.15-2.15 5.2-4.8 5.2s-4.8-2.05-4.8-5.2V4.4z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path
        d="M7.2 6.2H4.4c.05 2.35 1.35 3.7 3.35 4.15"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M16.8 6.2h2.8c-.05 2.35-1.35 3.7-3.35 4.15"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <line
        x1="12"
        y1="12.2"
        x2="12"
        y2="16.2"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M8.4 16.2h7.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M8 20h8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M12 2.2l.55 1.15 1.25.18-.9.9.21 1.24L12 5.08l-1.11.59.21-1.24-.9-.9 1.25-.18z"
        fill="currentColor"
      />
    </svg>
  );
}

const ROW_H = 30;

function RecordsCuerpo({ rows }) {
  const wrapRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [vh, setVh] = useState(420);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const sync = () => setVh(el.clientHeight || 420);
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - 3);
  const count = Math.ceil(vh / ROW_H) + 8;
  const slice = rows.slice(start, start + count);

  return (
    <div
      ref={wrapRef}
      className="records-cuerpo"
      onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
    >
      <div
        className="records-cuerpo-inner"
        style={{ height: Math.max(rows.length * ROW_H, vh) }}
      >
        {slice.map((r, i) => {
          const idx = start + i;
          return (
            <div
              key={`${r.tag}-${r.m0}-${r.s0}-${r.tipo}-${idx}`}
              className={`records-fila tipo-${r.tipo}`}
              style={{ top: idx * ROW_H, height: ROW_H }}
            >
              <span className="records-col-fecha">{r.fecha}</span>
              <span className="records-col-hora">{horaBono(r)}</span>
              <span className="records-col-x">×{r.x}</span>
              <span className="records-col-tipo">
                G{r.tipo} {r.nombre}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function RecordsModal({ abierto, onCerrar }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [tipos, setTipos] = useState([]);
  const [minX, setMinX] = useState(null);
  const [maxX, setMaxX] = useState(null);
  const [ordenCol, setOrdenCol] = useState("x");
  const [ordenDir, setOrdenDir] = useState("desc");
  const [cargandoDash, setCargandoDash] = useState(false);

  useEffect(() => {
    if (!abierto) return undefined;
    let cancel = false;
    (async () => {
      setBusy(true);
      setErr("");
      try {
        const r = await fetch("/api/records", { credentials: "include" });
        const j = await r.json().catch(() => ({}));
        if (cancel) return;
        if (!r.ok || !j.ok) {
          throw new Error(j.error || `HTTP ${r.status}`);
        }
        setData(j);
        setMinX((prev) => (prev == null ? j.min_x : prev));
        setMaxX((prev) => (prev == null ? j.max_x : prev));
      } catch (e) {
        if (!cancel) setErr(String(e.message || e));
      } finally {
        if (!cancel) setBusy(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [abierto]);

  const dataMin = data?.min_x ?? 0;
  const dataMax = data?.max_x ?? 0;
  const lo = minX == null ? dataMin : minX;
  const hi = maxX == null ? dataMax : maxX;

  const filas = useMemo(() => {
    const filtradas = filtrarRecords(data?.items, {
      tipos,
      minX: Math.min(lo, hi),
      maxX: Math.max(lo, hi),
    });
    return ordenarRecords(filtradas, ordenCol, ordenDir);
  }, [data, tipos, lo, hi, ordenCol, ordenDir]);

  if (!abierto) return null;

  const todosOn = esTodos(tipos);
  const nombres = data?.nombres || NOMBRES_G;

  function setMin(v) {
    const a = Number(v);
    const n = Number.isFinite(a) ? a : dataMin;
    setMinX(Math.min(n, hi));
  }

  function setMax(v) {
    const b = Number(v);
    const n = Number.isFinite(b) ? b : dataMax;
    setMaxX(Math.max(n, lo));
  }

  function toggleOrden(col) {
    if (ordenCol === col) {
      setOrdenDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setOrdenCol(col);
    setOrdenDir(col === "x" ? "asc" : "asc");
  }

  async function cargarAlHistorico() {
    if (cargandoDash || busy) return;
    setCargandoDash(true);
    setErr("");
    try {
      const r = await fetch("/api/records/cargar", {
        method: "POST",
        credentials: "include",
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) {
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      setData(j);
      setMinX(j.min_x);
      setMaxX(j.max_x);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setCargandoDash(false);
    }
  }

  const marcaOrden = (col) =>
    ordenCol === col ? (ordenDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-brillo modal-records"
        role="dialog"
        aria-label="Records"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="brillo-head">
          <h2>Records</h2>
          <button type="button" className="brillo-cerrar" onClick={onCerrar}>
            cerrar
          </button>
        </div>

        <div className="records-dash">
          <button
            type="button"
            className="records-dash-btn"
            disabled={
              busy || cargandoDash || !(data?.dashboard?.n_horas > 0)
            }
            title="Agrega al archivo las horas siguientes que el tablero ya tiene. Un hueco de 1 h se omite."
            onClick={cargarAlHistorico}
          >
            {cargandoDash
              ? "Cargando…"
              : data?.dashboard?.n_horas
                ? `Cargar ${data.dashboard.n_horas} h al histórico`
                : "Histórico al día"}
          </button>
          <p className="records-dash-nota">
            Histórico {etiquetaHora(data?.historico?.ultima)} ·{" "}
            {data?.historico?.n_horas ?? "—"} h
            {data?.dashboard?.omitidas_n
              ? ` · ${data.dashboard.omitidas_n} hueco${
                  data.dashboard.omitidas_n === 1 ? "" : "s"
                } omitido${data.dashboard.omitidas_n === 1 ? "" : "s"}`
              : ""}
          </p>
        </div>

        <div className="records-filtros">
          <div className="records-tipos" role="group" aria-label="Tipo de bono">
            <button
              type="button"
              className={`records-chip${todosOn ? " on" : ""}`}
              onClick={() => setTipos([])}
            >
              Todos
            </button>
            {TIPOS_G.map((t) => {
              const on = !todosOn && tipos.includes(t);
              return (
                <button
                  key={t}
                  type="button"
                  className={`records-chip tipo-${t}${on ? " on" : ""}`}
                  onClick={() => setTipos((prev) => toggleTipo(prev, t))}
                >
                  G{t} {nombres[t] || nombres[String(t)] || NOMBRES_G[t]}
                </button>
              );
            })}
          </div>

          <div className="records-rango">
            <div className="records-rango-nums">
              <span className="records-rango-label">Multiplicador</span>
              <label className="records-rango-campo">
                desde
                <input
                  type="number"
                  min={dataMin}
                  max={dataMax}
                  value={lo}
                  onChange={(e) => setMin(e.target.value)}
                />
              </label>
              <label className="records-rango-campo">
                hasta
                <input
                  type="number"
                  min={dataMin}
                  max={dataMax}
                  value={hi}
                  onChange={(e) => setMax(e.target.value)}
                />
              </label>
            </div>
            <div className="records-sliders">
              <input
                className="records-slider"
                type="range"
                min={dataMin}
                max={dataMax}
                value={lo}
                onChange={(e) => setMin(e.target.value)}
                aria-label="Multiplicador mínimo"
              />
              <input
                className="records-slider"
                type="range"
                min={dataMin}
                max={dataMax}
                value={hi}
                onChange={(e) => setMax(e.target.value)}
                aria-label="Multiplicador máximo"
              />
            </div>
          </div>
        </div>

        <p className="records-meta">
          {busy
            ? "Cargando…"
            : err
              ? err
              : `${filas.length} bono${filas.length === 1 ? "" : "s"} · ×${Math.min(lo, hi)}–×${Math.max(lo, hi)}`}
        </p>

        <div className="records-tabla">
          <div className="records-thead">
            <button
              type="button"
              className={`records-sort${ordenCol === "fecha" ? " on" : ""}`}
              onClick={() => toggleOrden("fecha")}
            >
              Fecha{marcaOrden("fecha")}
            </button>
            <button
              type="button"
              className={`records-sort${ordenCol === "hora" ? " on" : ""}`}
              onClick={() => toggleOrden("hora")}
            >
              Hora{marcaOrden("hora")}
            </button>
            <button
              type="button"
              className={`records-sort${ordenCol === "x" ? " on" : ""}`}
              onClick={() => toggleOrden("x")}
            >
              ×{marcaOrden("x")}
            </button>
            <button
              type="button"
              className={`records-sort${ordenCol === "tipo" ? " on" : ""}`}
              onClick={() => toggleOrden("tipo")}
            >
              Bono{marcaOrden("tipo")}
            </button>
          </div>
          {busy && !data ? (
            <p className="hint">Cargando cinta…</p>
          ) : err ? (
            <p className="hint">{err}</p>
          ) : filas.length ? (
            <RecordsCuerpo rows={filas} />
          ) : (
            <p className="hint">Ningún bono en ese filtro.</p>
          )}
        </div>
      </div>
    </div>
  );
}
