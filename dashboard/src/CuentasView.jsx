import { useCallback, useEffect, useMemo, useState } from "react";
import {
  cancelarApuestaManualX3,
  dispararApuestaManualX3,
  fetchCuentasEstado,
  guardarMontoManualPreferido,
  leerMontoManualPreferido,
} from "./apuestaManualApi.js";
import { detallePuertaA } from "./interruptorPuertaA.js";
import { ventanaCalientePool7 } from "./sequiaGo.js";

const MANUAL_MONTOS = [];
for (let v = 50; v <= 1000; v += 50) MANUAL_MONTOS.push(v);

const COLOR_LABEL = {
  rojo: "Rojo",
  azul: "Azul",
  verde: "Verde",
};

const TIPO_LOG = {
  apuesta: "Apuesta (manual)",
  apuesta_bot: "Apuesta (bot)",
  apuesta_manual: "Apuesta manual ($200)",
  premio: "Premio / cobro",
  bono_color: "Bono color",
  saldo: "Saldo",
};

function fmtHoraIso(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

function fmtUsd(n) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${Math.round(n)}`;
}

function ModalConfig({
  abierto,
  onCerrar,
  config,
  onGuardar,
  busy,
  err,
}) {
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    if (abierto && config) {
      setDraft(JSON.parse(JSON.stringify(config)));
    }
  }, [abierto, config]);

  if (!abierto || !draft) return null;

  const nb = draft.notebooks?.find((n) => n.id === draft.activeNotebookId);

  function patchNotebook(field, value) {
    setDraft((d) => ({
      ...d,
      notebooks: d.notebooks.map((n) =>
        n.id === d.activeNotebookId ? { ...n, [field]: value } : n
      ),
    }));
  }

  function patchCuenta(idx, field, value) {
    setDraft((d) => ({
      ...d,
      notebooks: d.notebooks.map((n) => {
        if (n.id !== d.activeNotebookId) return n;
        const cuentas = [...(n.cuentas || [])];
        cuentas[idx] = { ...cuentas[idx], [field]: value };
        return { ...n, cuentas };
      }),
    }));
  }

  function agregarNotebook() {
    const id = `nb-${Date.now()}`;
    setDraft((d) => ({
      ...d,
      activeNotebookId: id,
      notebooks: [
        ...(d.notebooks || []),
        {
          id,
          nombre: `Servidor ${(d.notebooks?.length || 0) + 1}`,
          cuentas: [
            { id: `${id}-rojo`, color: "rojo", url: "", wsPrimaria: false },
            { id: `${id}-azul`, color: "azul", url: "", wsPrimaria: true },
            { id: `${id}-verde`, color: "verde", url: "", wsPrimaria: false },
          ],
        },
      ],
    }));
  }

  function setWsPrimaria(idx) {
    setDraft((d) => ({
      ...d,
      notebooks: d.notebooks.map((n) => {
        if (n.id !== d.activeNotebookId) return n;
        const cuentas = (n.cuentas || []).map((c, i) => ({
          ...c,
          wsPrimaria: i === idx,
        }));
        return { ...n, cuentas };
      }),
    }));
  }

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-cuentas-config"
        role="dialog"
        aria-label="Configuración notebooks"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cuentas-modal-head">
          <h2>URLs y notebooks</h2>
          <button
            type="button"
            className="ghost icon-btn cuentas-modal-close"
            aria-label="Cerrar"
            onClick={onCerrar}
          >
            ×
          </button>
        </header>
        <p className="hint cuentas-modal-lead">
          Un notebook = un servidor con tres sesiones (rojo, azul, verde). Puedes
          agregar más servidores más adelante. Los clics en mesa siguen en solo
          lectura (ronda A).
        </p>

        <div className="cuentas-modal-section">
          <div className="cuentas-modal-servidor">
            <label className="cuentas-field cuentas-field-grow">
              <span className="cuentas-field-label">Notebook activo</span>
              <select
                value={draft.activeNotebookId}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, activeNotebookId: e.target.value }))
                }
              >
                {(draft.notebooks || []).map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.nombre || n.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="ghost cuentas-add-servidor"
              onClick={agregarNotebook}
            >
              + Agregar servidor
            </button>
          </div>
        </div>

        {nb ? (
          <>
            <div className="cuentas-modal-section">
              <label className="cuentas-field">
                <span className="cuentas-field-label">Nombre del servidor</span>
                <input
                  value={nb.nombre || ""}
                  onChange={(e) => patchNotebook("nombre", e.target.value)}
                  placeholder="Ej. Notebook prod"
                  autoComplete="off"
                />
              </label>
            </div>
            <div className="cuentas-url-stack">
              {(nb.cuentas || []).map((c, i) => (
                <div
                  key={c.id || i}
                  className={`cuenta-url-row cuenta-url-row--${c.color}`}
                >
                  <div className="cuenta-url-row-top">
                    <span className={`cuenta-color-tag ${c.color}`}>
                      {COLOR_LABEL[c.color] || c.color}
                    </span>
                    <label
                      className={`cuentas-ws-pill${c.wsPrimaria ? " on" : ""}`}
                    >
                      <input
                        type="radio"
                        name="wsPrimaria"
                        checked={Boolean(c.wsPrimaria)}
                        onChange={() => setWsPrimaria(i)}
                      />
                      <span>WS primaria</span>
                    </label>
                  </div>
                  <input
                    type="url"
                    className="cuenta-url-input"
                    value={c.url || ""}
                    onChange={(e) => patchCuenta(i, "url", e.target.value)}
                    placeholder="https://… sesión del juego"
                    spellCheck={false}
                    autoComplete="off"
                  />
                  <label className="cuentas-field cuenta-bono-field">
                    <span className="cuentas-field-label">
                      Bono 3 colores (TOMA TU DECISIÓN)
                    </span>
                    <select
                      value={c.bonoColor || c.color}
                      onChange={(e) =>
                        patchCuenta(i, "bonoColor", e.target.value)
                      }
                    >
                      <option value="rojo">Rojo (izquierda)</option>
                      <option value="azul">Azul (centro)</option>
                      <option value="verde">Verde (derecha)</option>
                    </select>
                  </label>
                </div>
              ))}
            </div>
          </>
        ) : null}

        <div className="cuentas-modal-actions row">
          <button
            type="button"
            disabled={busy}
            onClick={() => onGuardar(draft)}
          >
            {busy ? "Guardando…" : "Guardar"}
          </button>
          <button type="button" className="ghost" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
        {err ? <p className="err cuentas-modal-err">{err}</p> : null}
      </div>
    </div>
  );
}

function ModalLogApuestas({ cuenta, onCerrar }) {
  const [events, setEvents] = useState([]);
  const [loadErr, setLoadErr] = useState("");

  const cargar = useCallback(async () => {
    if (!cuenta) return;
    try {
      const q = new URLSearchParams({
        cuentaId: cuenta.id,
        limit: "100",
      });
      const r = await fetch(`/api/jokerbets/cuentas/apuestas-log?${q}`, {
        credentials: "include",
      });
      if (r.status === 401) return;
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "log");
      setEvents(Array.isArray(j.events) ? j.events : []);
      setLoadErr("");
    } catch (e) {
      setLoadErr(String(e.message || e));
    }
  }, [cuenta]);

  useEffect(() => {
    if (!cuenta) return undefined;
    cargar();
    return undefined;
  }, [cuenta, cargar]);

  if (!cuenta) return null;

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-cuentas-log"
        role="dialog"
        aria-label={`Log apuestas ${COLOR_LABEL[cuenta.color] || cuenta.color}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cuentas-modal-head">
          <h2>
            Log ·{" "}
            <span className={`cuenta-color-tag ${cuenta.color}`}>
              {COLOR_LABEL[cuenta.color] || cuenta.color}
            </span>
          </h2>
          <button type="button" className="ghost" onClick={() => cargar()}>
            Actualizar
          </button>
          <button
            type="button"
            className="ghost icon-btn cuentas-modal-close"
            aria-label="Cerrar"
            onClick={onCerrar}
          >
            ×
          </button>
        </header>
        <p className="hint cuentas-modal-lead">
          Se registra mientras Chrome está activo: cambios en barra APUESTA/PREMIO
          (manual o DOM) y gestos del bot (bono, clics). Multiplicador: texto del
          juego o premio÷apuesta cuando aplica.
        </p>
        {loadErr ? <p className="err">{loadErr}</p> : null}
        <div className="cuentas-log-scroll">
          {events.length === 0 ? (
            <p className="hint cuentas-log-empty">
              Sin eventos aún. Con clics armados, el bot y la barra PREMIO irán
              registrando aquí.
            </p>
          ) : (
            <table className="cuentas-log-table">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Tipo</th>
                  <th>Apuesta</th>
                  <th>Premio</th>
                  <th>Mult.</th>
                  <th>Saldo</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {[...events].reverse().map((ev, i) => (
                  <tr key={`${ev.ts}-${i}`}>
                    <td>{fmtHoraIso(ev.ts)}</td>
                    <td>{TIPO_LOG[ev.tipo] || ev.tipo || "—"}</td>
                    <td>{ev.montoApuesta ?? "—"}</td>
                    <td>{ev.premio ?? "—"}</td>
                    <td>{ev.multiplicador != null ? `${ev.multiplicador}x` : "—"}</td>
                    <td>{ev.saldo ?? "—"}</td>
                    <td className="cuentas-log-notas">
                      {[ev.horaTag, ev.notas, ev.fuente ? `(${ev.fuente})` : ""]
                        .filter(Boolean)
                        .join(" · ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="cuentas-modal-actions">
          <button type="button" className="ghost" onClick={cargar}>
            Actualizar
          </button>
          <button type="button" className="ghost" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

function ModalPuertaADetalle({ abierto, onCerrar, live, horaViva, det, simulPool7, botArmado, sesion, botAutoLine, notebook, intClass }) {
  if (!abierto) return null;
  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div
        className="modal modal-puerta-a"
        role="dialog"
        aria-label="Detalle Puerta A"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cuentas-modal-head">
          <h2>Puerta A · criterios</h2>
          <button type="button" className="ghost icon-btn cuentas-modal-close" aria-label="Cerrar" onClick={onCerrar}>
            ×
          </button>
        </header>
        <p className="cuentas-regla-line">
          Puerta A · (media≥68 <strong>o</strong> ALERTA con forma intra-hora) · ≥2 G · min&lt;40 · suma&lt;850 · sin techo · tip±1 · min tip−1, tip y tip+1 (Pool 7) · sequía≤3.
        </p>
        {simulPool7 ? (
          <p className="ok-text cuentas-sesion-line">
            Pool 7 activo: auto $50/bono en tip±1 solo con Brillo fuerte / muy fuerte / supernova.
            Se corta si vuelve a normal, opaca o muy apagada. Si el pill pasa a Go, Pool 7 se apaga solo y el botón queda bloqueado.
          </p>
        ) : null}
        {botArmado ? (
          <p className="hint cuentas-sesion-line">
            Go = $200/bono tip±1. No-Go no reactiva Pool 7; Puerta A On se mantiene.
          </p>
        ) : null}
        {det.formaGLabel ? (
          <p className="hint cuentas-sesion-line">
            Forma intra-hora:{" "}
            <strong className={det.puertaAFase === "formaG" ? "ok-text" : ""}>{det.formaGLabel}</strong>
            {det.ultimosGForma?.length ? ` · últimos G: ${det.ultimosGForma.join(" → ")}` : ""}
          </p>
        ) : null}
        <div className="cuentas-kpis row">
          <span className="cuentas-tag">Hora: {live?.tag || horaViva || "—"}</span>
          <span>
            Interruptor Brillo: <strong className={`cuentas-int-pill ${intClass}`}>{det.interruptor}</strong>
          </span>
          <span>
            Pool 7 tip: <strong>{det.tip ?? "—"}</strong>
          </span>
          <span>
            En zona tip±1:{" "}
            <strong className={det.enZona ? "ok-text" : ""}>{det.tip == null ? "—" : det.enZona ? "sí" : "no"}</strong>
          </span>
          <span>Notebook: {notebook?.nombre || "—"}</span>
        </div>
        <ul className="cuentas-motivos">
          {det.motivos.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <p className="hint cuentas-ro-only">
          Auto Puerta A: <strong>Puerta A {botArmado ? "On" : "Off"}</strong> + criterios arriba + minuto ±1 del tip. Auto Pool 7: toggle Pool 7 ($50/bono). Manual: panel sin depender de Puerta A.
        </p>
        {sesion?.corriendo && botArmado && !simulPool7 ? (
          <p className={sesion?.apuestaOk ? "ok-text cuentas-sesion-line" : "hint cuentas-sesion-line"}>{botAutoLine}</p>
        ) : null}
        <div className="cuentas-modal-actions">
          <button type="button" className="ghost" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

function ModalPerformanceAnalisis({ abierto, onCerrar }) {
  const [res, setRes] = useState(null);
  const [copyMsg, setCopyMsg] = useState("");

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/jokerbets/analisis/resumen", { credentials: "include" });
      if (r.status === 401) return;
      const j = await r.json();
      if (j.ok !== false) setRes(j);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!abierto) return undefined;
    cargar();
    const id = setInterval(cargar, 60_000);
    return () => clearInterval(id);
  }, [abierto, cargar]);

  async function copiarJson() {
    if (!res) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(res, null, 2));
      setCopyMsg("Copiado — pegar en chat con el agente.");
      setTimeout(() => setCopyMsg(""), 4000);
    } catch {
      setCopyMsg("No se pudo copiar.");
    }
  }

  if (!abierto) return null;
  const cuentas = res?.porCuenta ? Object.values(res.porCuenta) : [];

  return (
    <div className="modal-back" role="presentation" onClick={onCerrar}>
      <div className="modal modal-perf-analisis" role="dialog" aria-label="Performance" onClick={(e) => e.stopPropagation()}>
        <header className="cuentas-modal-head">
          <h2>Performance (análisis)</h2>
          <button type="button" className="ghost icon-btn cuentas-modal-close" aria-label="Cerrar" onClick={onCerrar}>
            ×
          </button>
        </header>
        {!res?.nEventos ? (
          <p className="hint cuentas-modal-lead">Aún sin eventos. Con Chrome activo y apuestas, el log se llena solo.</p>
        ) : (
          <>
            <p className="hint cuentas-modal-lead">
              {res.nEventos} eventos · {res.desde?.slice(0, 10) || "?"} → {res.hasta?.slice(0, 10) || "?"}
            </p>
            <ul className="cuentas-perf-list">
              {cuentas.map((row) => (
                <li key={row.cuentaId || row.color}>
                  {COLOR_LABEL[row.color] || row.color}: {row.apuestasBot ?? 0} apuestas bot · saldo{" "}
                  {row.ultimoSaldo != null ? fmtUsd(row.ultimoSaldo) : "—"}
                  {row.pnlDesdeArranque != null
                    ? ` · PnL ${row.pnlDesdeArranque >= 0 ? "+" : ""}${fmtUsd(row.pnlDesdeArranque)}`
                    : ""}
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="row cuentas-perf-actions cuentas-modal-actions">
          <button type="button" className="ghost" onClick={copiarJson}>
            Copiar JSON
          </button>
          <button type="button" className="ghost" onClick={cargar}>
            Actualizar
          </button>
          <button type="button" className="ghost" onClick={onCerrar}>
            Cerrar
          </button>
          {copyMsg ? <span className="hint ok-text">{copyMsg}</span> : null}
        </div>
      </div>
    </div>
  );
}

export default function CuentasView({ live, horaViva, simulPool7 = false }) {
  const [config, setConfig] = useState(null);
  const [modalCfg, setModalCfg] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sesion, setSesion] = useState(null);
  const [sesionBusy, setSesionBusy] = useState(false);
  const [sesionErr, setSesionErr] = useState("");
  const [botArmado, setBotArmado] = useState(false);
  const [botBusy, setBotBusy] = useState(false);
  const [logCuenta, setLogCuenta] = useState(null);
  const [manualBusy, setManualBusy] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [manualMonto, setManualMonto] = useState(leerMontoManualPreferido);
  const [modalPuerta, setModalPuerta] = useState(false);
  const [modalPerf, setModalPerf] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await fetch("/api/jokerbets/config", { credentials: "include" });
      if (r.status === 401) return;
      const j = await r.json();
      if (j.ok) setConfig(j.config);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => {
    fetch("/api/jokerbets/bot/armado", { credentials: "include" })
      .then((r) => r.json())
      .then((j) => {
        if (j.ok) setBotArmado(Boolean(j.armado));
      })
      .catch(() => {});
  }, []);

  const pollSesion = useCallback(async () => {
    try {
      const [j, rEx] = await Promise.all([
        fetchCuentasEstado(),
        fetch("/api/extraccion/estado", { credentials: "include" }),
      ]);
      if (j.auth === false) return;
      let ext = null;
      if (rEx.ok) ext = await rEx.json();
      if (j.ok) {
        setSesion({
          ...j,
          extraccionEstado: ext?.estado,
          extraccionMensaje: ext?.mensaje,
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    pollSesion();
    let lastSeq = 0;
    const revisarPulso = async () => {
      try {
        const r = await fetch("/api/jokerbets/ui-pulse", { credentials: "include" });
        if (r.status === 401) return;
        const j = await r.json();
        const seq = j?.pulse?.seq || 0;
        if (seq && seq !== lastSeq) {
          lastSeq = seq;
          await pollSesion();
        }
      } catch {
        /* ignore */
      }
    };
    const id = setInterval(revisarPulso, 8000);
    return () => clearInterval(id);
  }, [pollSesion]);

  async function cancelarApuestaManual() {
    setManualBusy(true);
    try {
      await cancelarApuestaManualX3();
      await pollSesion();
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setManualBusy(false);
    }
  }

  async function dispararApuestaManual() {
    if (!sesion?.corriendo) {
      setSesionErr("Inicia Chrome antes de apostar manual.");
      return;
    }
    setManualBusy(true);
    setSesionErr("");
    try {
      guardarMontoManualPreferido(manualMonto);
      await dispararApuestaManualX3(manualMonto);
      await pollSesion();
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setManualBusy(false);
    }
  }

  const detReal = useMemo(() => detallePuertaA(live), [live]);
  const det = useMemo(() => {
    if (!simulPool7) return detReal;
    return {
      ...detReal,
      interruptor: "ON",
      estadoTarjeta: "EN RACHA (SIM)",
      puertaA: true,
      motivos: [
        "LAB: SIM fuerza ON + puerta A + sequía≤3",
        "Minutos de clic = iguales a prod (±1 alrededor del tip, enCurso vivo)",
        "No sustituye Brillo real",
      ],
    };
  }, [detReal, simulPool7]);

  const ventanaCaliente = useMemo(
    () => ventanaCalientePool7(live?.tiros),
    [live?.tiros],
  );

  /** Go real (hora fuerte $200). No se enmascara si Pool 7 está On — así se puede apagar Pool 7. */
  const puertaGo = useMemo(() => {
    if (!botArmado) return false;
    if (det.interruptor === "OFF") return false;
    return Boolean(det.puertaA && det.enZona && ventanaCaliente);
  }, [botArmado, det.interruptor, det.puertaA, det.enZona, ventanaCaliente]);

  /** Go → Pool 7 Off (queda Off; No-Go no lo reactiva). Puerta A On no se toca. */
  useEffect(() => {
    if (!puertaGo || !simulPool7) return undefined;
    let vivo = true;
    (async () => {
      try {
        const r = await fetch("/api/jokerbets/simulacion-pool7", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ activo: false }),
        });
        const j = await r.json().catch(() => ({}));
        if (!vivo) return;
        if (!r.ok || j.ok === false) {
          setSesionErr(j.error || `HTTP ${r.status}`);
        }
      } catch (e) {
        if (vivo) setSesionErr(String(e.message || e));
      }
    })();
    return () => {
      vivo = false;
    };
  }, [puertaGo, simulPool7]);

  async function toggleSimulPool7() {
    if (puertaGo && !simulPool7) {
      setSesionErr("Puerta A en Go — Pool 7 deshabilitado ($200).");
      return;
    }
    setSimBusy(true);
    setSesionErr("");
    try {
      const r = await fetch("/api/jokerbets/simulacion-pool7", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activo: !simulPool7 }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setSimBusy(false);
    }
  }

  const manualTotalCuenta = manualMonto * 4;

  const botAutoLine = useMemo(() => {
    if (!botArmado && !simulPool7) return "Puerta A Off · Pool 7 Off — sin auto.";
    const s = sesion?.senal;
    const ok = sesion?.apuestaOk;
    if (ok) {
      if (puertaGo) {
        return "Bot auto: puede apostar (Puerta A Go · $200/bono · tip±1).";
      }
      if (simulPool7) {
        return "Bot auto: puede apostar (Pool 7 — Brillo fuerte+ · ventana ±1 del tip, $50/bono).";
      }
      if (s?.puertaAFase === "formaG" || det.puertaAFase === "formaG") {
        return `Bot auto: puede apostar (Puerta A · forma · ${s?.formaGLabel || det.formaGLabel || "—"} + ±1 + sequía≤3).`;
      }
      return "Bot auto: puede apostar (Puerta A + ventana ±1 + pocos tiros tras la G).";
    }
    const parts = [];
    if (simulPool7 && s?.simulPool7 !== true) {
      parts.push("SIM en UI pero jokerbets-senal.json aún sin simulPool7 (¿dashboard/servir?)");
    } else if (simulPool7 && s?.pool7BrilloOk === false) {
      parts.push(
        `Brillo en ${live?.brillo?.bandaMean || live?.brillo?.bandaTotal || live?.brillo?.pill || "banda baja"} — Pool 7 solo con fuerte / muy fuerte / supernova`,
      );
    } else if (simulPool7 && s?.permitirClics === false) {
      parts.push(
        `ventana tip±1 cerrada (tip ${s?.tip ?? det.tip ?? "?"} · Go! ${s?.enCurso || "?"} · reloj ${s?.relojMinuto ?? "?"}:${String(s?.relojSegundo ?? "?").padStart(2, "0")})`,
      );
    } else if (simulPool7) {
      parts.push("SIM activa pero señal aún no llegó al bot");
    }
    if (s?.interruptor === "OFF" && !simulPool7) {
      parts.push(`interruptor ${s?.interruptor || det.interruptor || "?"}`);
    }
    if (
      !s?.puertaA &&
      !det.puertaA &&
      !simulPool7
    ) {
      const fg = det.formaGLabel || s?.formaGLabel;
      parts.push(fg ? `sin puerta A · ${fg}` : "sin puerta A");
    }
    if (s?.puertaA && !s?.enZona && !simulPool7) {
      parts.push(`fuera de zona tip±1 (tip ${s?.tip ?? det.tip ?? "?"})`);
    }
    if (s?.puertaA || det.puertaA) {
      if (
        s?.enZona &&
        s?.enZonaApuesta === false &&
        s?.ventanaCaliente !== false &&
        !simulPool7
      ) {
        parts.push(
          `fuera del minuto ±1 del tip ${s?.tip ?? det.tip ?? "?"}`,
        );
      }
    }
    if (
      (s?.puertaA || det.puertaA) &&
      s?.enZona &&
      s?.ventanaCaliente === false &&
      !simulPool7
    ) {
      parts.push(
        `sequía Pool 7 (${s?.gapTiro ?? "?"} tiros tras la última G — máx. 3)`,
      );
    }
    if (!parts.length) parts.push("señal no lista");
    return `Bot auto: no · ${parts.join(" · ")}`;
  }, [botArmado, sesion, det, simulPool7, puertaGo, live?.brillo]);

  const notebook = useMemo(() => {
    if (!config?.notebooks?.length) return null;
    const id = config.activeNotebookId || config.notebooks[0].id;
    return config.notebooks.find((n) => n.id === id) || config.notebooks[0];
  }, [config]);

  const arranque = config?.arranqueUsd ?? 20000;

  const estadoPorColor = useMemo(() => {
    const map = {};
    for (const c of sesion?.cuentas || []) {
      if (c?.color) map[c.color] = c;
    }
    return map;
  }, [sesion]);

  async function iniciarChrome() {
    setSesionBusy(true);
    setSesionErr("");
    try {
      const r = await fetch("/api/extraccion/iniciar", {
        method: "POST",
        credentials: "include",
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.ok === false) {
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      await pollSesion();
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setSesionBusy(false);
    }
  }

  async function detenerChrome() {
    setSesionBusy(true);
    setSesionErr("");
    try {
      const r = await fetch("/api/extraccion/detener", {
        method: "POST",
        credentials: "include",
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.ok === false) {
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      setBotArmado(false);
      await pollSesion();
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setSesionBusy(false);
    }
  }

  async function toggleBotArmado() {
    setBotBusy(true);
    try {
      const next = !botArmado;
      const r = await fetch("/api/jokerbets/bot/armado", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ armado: next }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
      setBotArmado(Boolean(j.armado));
    } catch (e) {
      setSesionErr(String(e.message || e));
    } finally {
      setBotBusy(false);
    }
  }

  async function guardarConfig(draft, opts = {}) {
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/api/jokerbets/config", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: draft }),
      });
      const j = await r.json();
      if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
      setConfig(j.config);
      if (!opts.keepOpen) setModalCfg(false);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  const intClass =
    det.interruptor === "ON"
      ? "int-on"
      : det.interruptor === "ALERTA"
        ? "int-alerta"
        : "int-off";

  return (
    <div className="cuentas-view">
      <header className="panel-control-head">
        <h2>Panel de control</h2>
        <p className="hint panel-control-sub">
          Auto: Puerta A Go $200/bono · Pool 7 $50/bono (Off si Go) · Manual ×3
        </p>
      </header>

      <section className="panel-control card">
        <div className="panel-control-grid">
          {!sesion?.corriendo ? (
            <button
              type="button"
              className="cuentas-config-btn panel-control-primary"
              disabled={sesionBusy}
              onClick={iniciarChrome}
            >
              {sesionBusy ? "…" : "Iniciar 3 Chrome"}
            </button>
          ) : (
            <div className="panel-chrome-run">
              <span className="panel-control-status ok-text">
                Chrome activo · WS {sesion.fuenteWsColor || "—"}
              </span>
              <button
                type="button"
                className="ghost cuentas-config-btn panel-chrome-stop"
                disabled={sesionBusy}
                onClick={detenerChrome}
                title="Cierra las 3 ventanas y detiene la extracción"
              >
                {sesionBusy ? "…" : "Cerrar 3 Chrome"}
              </button>
            </div>
          )}

          <button
            type="button"
            className={botArmado ? "cuentas-config-btn" : "ghost cuentas-config-btn"}
            disabled={botBusy || !sesion?.corriendo}
            onClick={toggleBotArmado}
            title="Apuestas automáticas Puerta A (prod)"
          >
            {botArmado ? "Puerta A — On" : "Puerta A — Off"}
          </button>

          <button
            type="button"
            className={simulPool7 ? "cuentas-config-btn" : "ghost cuentas-config-btn"}
            disabled={
              simBusy ||
              !sesion?.corriendo ||
              !live?.habilitado ||
              puertaGo
            }
            onClick={toggleSimulPool7}
            title={
              puertaGo
                ? "Puerta A en Go — apuesta $200; Pool 7 deshabilitado"
                : "Apuestas auto Pool 7 (Brillo fuerte+ · ventana ±1 del tip, $50/bono)"
            }
          >
            {simBusy ? "…" : simulPool7 ? "Pool 7 — On" : "Pool 7 — Off"}
          </button>

          <div className="panel-control-manual">
            <select
              className="panel-monto-select"
              value={manualMonto}
              disabled={manualBusy}
              aria-label="Monto por bono para apuesta manual"
              onChange={(e) => {
                const m = Number(e.target.value);
                setManualMonto(m);
                guardarMontoManualPreferido(m);
              }}
            >
              {MANUAL_MONTOS.map((m) => (
                <option key={m} value={m}>
                  ${m}/bono · 4 bonos · ${m * 4} por cuenta
                </option>
              ))}
            </select>
            <button
              type="button"
              className="cuentas-config-btn"
              disabled={manualBusy || !sesion?.corriendo}
              onClick={dispararApuestaManual}
              title={`Dispara en rojo, azul y verde · total ~$${manualTotalCuenta} por cuenta`}
            >
              {manualBusy ? "…" : sesion?.manual?.pendiente ? "Enviando ×3…" : "Apostar ×3"}
            </button>
          </div>

          <button type="button" className="ghost cuentas-config-btn" onClick={() => setModalCfg(true)}>
            URLs
          </button>
          <button type="button" className="ghost cuentas-config-btn" onClick={() => setModalPerf(true)}>
            Performance
          </button>
          {sesion?.manual?.pendiente ? (
            <button
              type="button"
              className="ghost cuentas-config-btn"
              disabled={manualBusy}
              onClick={cancelarApuestaManual}
            >
              Cancelar manual
            </button>
          ) : null}
        </div>
      </section>

      {sesionErr ? <p className="err">{sesionErr}</p> : null}
      {sesion?.extraccionMensaje ? (
        <p
          className={
            sesion.extraccionEstado === "error"
              ? "err cuentas-sesion-line"
              : "hint cuentas-sesion-line"
          }
        >
          {sesion.extraccionMensaje}
        </p>
      ) : null}

      <section className="panel-control-statusbar card">
        <div className="panel-statusbar-row">
          <span className="cuentas-tag">Hora: {live?.tag || horaViva || "—"}</span>
          <span className="panel-statusbar-puerta">
            Puerta A
            <button
              type="button"
              className={`panel-go-pill${puertaGo ? " go" : " nogo"}`}
              onClick={() => setModalPuerta(true)}
              title="Ver criterios y detalle Brillo"
            >
              {puertaGo ? "Go" : "No-Go"}
            </button>
          </span>
          <span>
            Tip Pool 7: <strong>{det.tip ?? "—"}</strong>
          </span>
          <span>
            Zona ±1:{" "}
            <strong className={det.enZona ? "ok-text" : ""}>
              {det.tip == null ? "—" : det.enZona ? "sí" : "no"}
            </strong>
          </span>
          {simulPool7 ? (
            <span className="ok-text">Pool 7 activo</span>
          ) : null}
        </div>
        {sesion?.corriendo && (botArmado || simulPool7) ? (
          <p className={sesion?.apuestaOk ? "ok-text cuentas-sesion-line" : "hint cuentas-sesion-line"}>
            {botAutoLine}
          </p>
        ) : null}
        {sesion?.manual?.pendiente ? (
          <p className="hint cuentas-sesion-line">
            Apuesta manual en curso (${sesion.manual?.montoPorBono ?? manualMonto}/bono en las 3 cuentas)…
          </p>
        ) : null}
      </section>

      <p className="hint cuentas-cards-hint">
        Cards informativas: se actualizan al cerrar un bono (color) o al registrar un premio
        ganador; también al iniciar/detener Chrome o acciones del panel. Sin refresco en vivo
        cada pocos segundos.
      </p>
      <div className="cuentas-grid">
        {(notebook?.cuentas || []).map((c) => {
          const run = estadoPorColor[c.color];
          return (
          <article
            key={c.id}
            role="button"
            tabIndex={0}
            className={`cuenta-card cuenta-card-click card estado-${det.estadoTarjeta.replace(/\s+/g, "-")}`}
            onClick={() => setLogCuenta(c)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setLogCuenta(c);
              }
            }}
            title="Ver log de apuestas"
          >
            <header>
              <span className={`cuenta-color-tag ${c.color}`}>
                {COLOR_LABEL[c.color] || c.color}
              </span>
              <span className="cuenta-estado">{det.estadoTarjeta}</span>
            </header>
            <dl className="cuenta-dl">
              <div>
                <dt>SALDO {run?.saldoDom ? "(DOM)" : "(libro)"}</dt>
                <dd>
                  {run?.saldoDom ? `$${run.saldoDom}` : fmtUsd(arranque)}
                </dd>
              </div>
              <div>
                <dt>Apuesta</dt>
                <dd>
                  {run?.apuestaDom != null && run.apuestaDom !== ""
                    ? `$${run.apuestaDom}`
                    : det.puertaA && det.enZona
                      ? fmtUsd(600)
                      : "$0"}
                </dd>
              </div>
              <div>
                <dt>WS</dt>
                <dd>
                  {run?.wsActiva
                    ? "activa"
                    : c.wsPrimaria
                      ? "primaria (cfg)"
                      : "backup"}
                </dd>
              </div>
            </dl>
            <p className="hint cuenta-url">
              {c.url ? c.url.replace(/^https?:\/\//, "").slice(0, 48) : "URL sin pegar"}
            </p>
            <p className="hint cuenta-run">
              Chrome:{" "}
              {sesion?.corriendo
                ? run?.chromeAbierto
                  ? "abierto"
                  : "…"
                : "detenido"}{" "}
              · {run?.ultimoGesto || (botArmado ? "Puerta A on" : "Puerta A off")}
            </p>
            <p className="hint cuenta-log-hint">Clic para log de apuestas</p>
          </article>
          );
        })}
      </div>

      <ModalConfig
        abierto={modalCfg}
        onCerrar={() => {
          setModalCfg(false);
          setErr("");
        }}
        config={config}
        onGuardar={guardarConfig}
        busy={busy}
        err={err}
      />

      <ModalLogApuestas
        cuenta={logCuenta}
        onCerrar={() => setLogCuenta(null)}
      />

      <ModalPuertaADetalle
        abierto={modalPuerta}
        onCerrar={() => setModalPuerta(false)}
        live={live}
        horaViva={horaViva}
        det={det}
        simulPool7={simulPool7}
        botArmado={botArmado}
        sesion={sesion}
        botAutoLine={botAutoLine}
        notebook={notebook}
        intClass={intClass}
      />

      <ModalPerformanceAnalisis abierto={modalPerf} onCerrar={() => setModalPerf(false)} />
    </div>
  );
}