import { useCallback, useEffect, useRef, useState } from "react";
import Extraccion from "./Extraccion.jsx";
import LiveAvance from "./LiveAvance.jsx";
import MesasTodasV2 from "./MesasTodasV2.jsx";
import MesaOficialModales from "./MesaOficialModales.jsx";
import Panel from "./Panel.jsx";
import CuentasView from "./CuentasView.jsx";
import { detallePuertaA } from "./interruptorPuertaA.js";
import { enZonaApuestaPool7Live } from "./tipProxima.js";
import {
  gapTiroDesdeUltimaG,
  ventanaCalientePool7,
} from "./sequiaGo.js";
import { pool7BrilloPermite } from "./brilloInfo.js";

const TAG_CINTA_RE = /^h\d{1,2}-\d{6}$/i;
const API_TIMEOUT_MS = 45_000;

function pedir(path, opts = {}) {
  const { timeoutMs = 0, ...fetchOpts } = opts;
  if (!timeoutMs) {
    return fetch(path, { credentials: "include", ...fetchOpts });
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  return fetch(path, {
    credentials: "include",
    ...fetchOpts,
    signal: ctrl.signal,
  }).finally(() => clearTimeout(timer));
}

function textoTieneTagCinta(texto) {
  return (texto || "")
    .split(/\r?\n/)
    .some((l) => TAG_CINTA_RE.test(l.trim()));
}

const PLACEHOLDER = `h23-170826
00:05-01:12 R
01:13-02:40 G2 30`;

/** Refresco silencioso del tablero cada hora (sin reload de página). */
const REFRESCO_MS = 60 * 60 * 1000;

function Acceso({ onOk }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);

  async function entrar(e) {
    e.preventDefault();
    setBusy(true);
    setErr(false);
    try {
      const r = await pedir("/api/entrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario, clave }),
      });
      if (!r.ok) {
        setErr(true);
        return;
      }
      onOk();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="acceso">
      <form className="card" onSubmit={entrar}>
        <input
          autoFocus
          autoComplete="username"
          value={usuario}
          onChange={(e) => setUsuario(e.target.value)}
          placeholder="usuario"
        />
        <input
          type="password"
          autoComplete="current-password"
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          placeholder="contraseña"
        />
        <button disabled={busy || !usuario || !clave} type="submit">
          {busy ? "…" : "entrar"}
        </button>
        {err ? <p className="err">no</p> : null}
      </form>
    </div>
  );
}

function ModalCinta({
  texto,
  setTexto,
  busy,
  onCerrar,
  onAgregar,
  err,
  ok,
}) {
  return (
    <div className="modal-back" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-labelledby="cinta-titulo"
      >
        <h2 id="cinta-titulo">Agregar a la cinta</h2>
        <p className="hint">
          Pegá tag + tramos de una hora ya cerrada (ej. h18-290826 en la primera
          línea). Entra al archivo. El live de la hora en curso va arriba, no
          acá.
        </p>
        <textarea
          autoFocus
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder={PLACEHOLDER}
          spellCheck={false}
        />
        <div className="row">
          <button
            disabled={busy || !texto.trim()}
            onClick={() => onAgregar()}
          >
            {busy ? "Leyendo…" : "Agregar a la cinta"}
          </button>
          <button className="ghost" type="button" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
        {ok ? <p className="ok">{ok}</p> : null}
        {err ? <p className="err">{err}</p> : null}
      </div>
    </div>
  );
}

export default function App() {
  const [sesion, setSesion] = useState(null);
  const [texto, setTexto] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyCinta, setBusyCinta] = useState(false);
  const [sel, setSel] = useState(null);
  const [modal, setModal] = useState(false);
  const [live, setLive] = useState(null);
  const [okCinta, setOkCinta] = useState("");
  const [modalLiveAbierto, setModalLiveAbierto] = useState(false);
  const [prefillLive, setPrefillLive] = useState("");
  const [liveManualTexto, setLiveManualTexto] = useState("");
  const [modalStats, setModalStats] = useState(false);
  const [modalTips, setModalTips] = useState(false);
  const [modalHistorico, setModalHistorico] = useState(false);
  const [mesaId, setMesaId] = useState("oficial");
  const [vistaBoard, setVistaBoard] = useState("v2"); // panel | v2
  const vistaTodas = vistaBoard === "v2";
  const [modalExtraccion, setModalExtraccion] = useState(false);
  const [pestaña, setPestaña] = useState("mesa"); // mesa | cuentas

  const onExtraccion = useCallback(() => setModalExtraccion(true), []);
  const onAbrirMesa = useCallback((id) => {
    setMesaId(id);
    setVistaBoard("panel");
    setSel(null);
  }, []);

  async function cargar(opts = {}) {
    const { body, guardar, silent = false } = opts;
    if (!silent) setBusy(true);
    setErr("");
    try {
      const usarPost = Boolean(body) || guardar;
      const r = await pedir("/api/tablero", {
        method: usarPost ? "POST" : "GET",
        headers: usarPost ? { "Content-Type": "application/json" } : undefined,
        body: usarPost
          ? JSON.stringify({ texto: body || texto, guardar: Boolean(guardar) })
          : undefined,
        timeoutMs: usarPost ? API_TIMEOUT_MS : 0,
      });
      if (r.status === 401) {
        setSesion(false);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j.ok === false) throw new Error(j.error || "fallo al leer");
      setData(j);
      return j;
    } catch (e) {
      const msg =
        e?.name === "AbortError"
          ? "El servidor no respondió a tiempo. Revisá que servir.py esté corriendo."
          : String(e.message || e);
      setErr(msg);
      return false;
    } finally {
      if (!silent) setBusy(false);
    }
  }

  const cargarRef = useRef(cargar);
  cargarRef.current = cargar;

  const onAutoCinta = useCallback(async (t) => {
    try {
      const r = await pedir("/api/tablero", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          texto: t,
          guardar: true,
          solo_guardar: true,
        }),
        timeoutMs: 120_000,
      });
      if (r.status === 401) {
        setSesion(false);
        return { ok: false };
      }
      if (!r.ok) return { ok: false };
      const j = await r.json();
      if (j?.guardadas?.length) {
        cargarRef.current({ silent: true });
      }
      return j;
    } catch {
      return { ok: false };
    }
  }, []);

  async function confirmarCinta() {
    const t = texto.trim();
    setOkCinta("");
    setErr("");
    if (!t) return;
    if (!textoTieneTagCinta(t)) {
      setErr(
        "Falta el tag de la hora (ej. h18-290826). Sin él no entra nada a la cinta."
      );
      return;
    }
    setBusyCinta(true);
    try {
      const r = await pedir("/api/tablero", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: t, guardar: true }),
        timeoutMs: API_TIMEOUT_MS,
      });
      if (r.status === 401) {
        setSesion(false);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (j.ok === false) throw new Error(j.error || "fallo al leer");
      setData(j);
      if (j.guardadas?.length) {
        setTexto("");
        let msg = `Se agregó con éxito: ${j.guardadas.join(", ")}.`;
        if (j.alertas_ingesta?.length) {
          const tags = j.alertas_ingesta.map((a) => a.tag).join(", ");
          msg += ` Alerta ingesta (${tags}) — ver reports/log_alertas_ingesta.txt.`;
        }
        setOkCinta(msg);
        return;
      }
      setErr(
        "Ninguna hora cerrada: no se escribió. Revisá que esté completa (≥40 tiros, corte ~59)."
      );
    } catch (e) {
      const msg =
        e?.name === "AbortError"
          ? "El servidor no respondió a tiempo. Revisá que servir.py esté corriendo."
          : String(e.message || e);
      setErr(msg);
    } finally {
      setBusyCinta(false);
    }
  }

  useEffect(() => {
    let vivo = true;
    pedir("/api/sesion")
      .then((r) => r.json())
      .then((j) => {
        if (!vivo) return;
        const ok = Boolean(j.ok);
        setSesion(ok);
        if (ok) cargar();
      })
      .catch(() => {
        if (vivo) setSesion(false);
      });
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    if (sesion !== true) return;
    const id = setInterval(() => {
      cargarRef.current({ silent: true });
    }, REFRESCO_MS);
    return () => clearInterval(id);
  }, [sesion]);

  const [simulPool7, setSimulPool7] = useState(false);

  useEffect(() => {
    if (sesion !== true) return;
    let vivo = true;
    const poll = () => {
      pedir("/api/jokerbets/simulacion-pool7")
        .then((r) => r.json())
        .then((j) => {
          if (vivo && j.ok) setSimulPool7(Boolean(j.activo));
        })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, 2500);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, [sesion]);

  useEffect(() => {
    if (sesion !== true || !live?.habilitado) return;
    const pushSenal = () => {
      const det = detallePuertaA(live);
      const interruptor = simulPool7 ? "ON" : det.interruptor;
      const puertaA = simulPool7 ? true : det.puertaA;
      const tip = det.tip ?? live.tipProx?.tip ?? null;
      const enZona = det.enZona;
      const relojParaPool7 = {
        minuto: live.reloj?.minuto ?? live.brillo?.T ?? null,
        segundo: live.reloj?.segundo ?? 0,
      };
      const enZonaApuesta = enZonaApuestaPool7Live({
        enCurso: live.enCurso,
        tip,
        simulPool7,
        reloj: relojParaPool7,
      });
      const gapTiro = gapTiroDesdeUltimaG(live.tiros);
      const ventanaCalienteReal = ventanaCalientePool7(live.tiros);
      const ventanaCaliente = simulPool7 ? true : ventanaCalienteReal;
      /** Pool 7: solo fuerte / muy fuerte / supernova (no normal/opaca/muy apagada). */
      const pool7BrilloOk = pool7BrilloPermite(live.brillo);
      /** Hora fuerte real (no la fuerza SIM). Go en UI = esto + Puerta A On. */
      const puertaGoBrillo = Boolean(
        det.puertaA &&
          det.interruptor !== "OFF" &&
          enZonaApuesta &&
          ventanaCalienteReal,
      );
      /** SIM: tip±1 + Brillo fuerte+. Prod: Pool7 + Puerta A + sequía≤3. */
      const permitirClics = simulPool7
        ? tip != null && enZonaApuesta && pool7BrilloOk
        : puertaA &&
          det.interruptor !== "OFF" &&
          enZonaApuesta &&
          ventanaCaliente;
      pedir("/api/jokerbets/senal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tag: live.tag || "",
          interruptor,
          puertaA,
          enZona,
          enZonaApuesta,
          enCurso: live.enCurso || "",
          confirmadoHasta: live.confirmadoHasta ?? -1,
          nTiros: Array.isArray(live.tiros) ? live.tiros.length : 0,
          brilloFp: live.brillo?.fingerprint ?? "",
          relojMinuto: relojParaPool7.minuto,
          relojSegundo: relojParaPool7.segundo,
          tip,
          tipEstado: live.tipProx?.estado ?? null,
          gapTiro,
          ventanaCaliente,
          permitirClics,
          simulPool7,
          pool7BrilloOk,
          puertaGoBrillo,
          puertaAFase: det.puertaAFase || null,
          formaG: det.formaG || "",
          formaGLabel: det.formaGLabel || "",
          formaGApuesta: det.puertaAFase === "formaG",
          viaApuesta: puertaGoBrillo
            ? det.puertaAFase || "puertaA"
            : simulPool7
              ? "sim"
              : det.puertaA
                ? det.puertaAFase || "puertaA"
                : null,
        }),
      }).catch((e) => {
        if (typeof console !== "undefined") {
          console.warn("jokerbets/senal POST:", e?.message || e);
        }
      });
    };
    pushSenal();
    const id = setInterval(pushSenal, 2000);
    return () => clearInterval(id);
  }, [
    sesion,
    simulPool7,
    live?.tag,
    live?.habilitado,
    live?.brillo?.fingerprint,
    live?.reloj?.minuto,
    live?.reloj?.segundo,
    live?.enCurso,
    live?.tipProx?.tip,
    live?.tipProx?.estado,
    live?.tiros?.length,
    live?.confirmadoHasta,
    live?.brillo?.fingerprint,
    live?.brillo?.T,
  ]);

  if (sesion !== true) {
    if (sesion === null) return <div className="acceso" />;
    return (
      <Acceso
        onOk={() => {
          setSesion(true);
          cargar();
        }}
      />
    );
  }

  const panel = data?.mesas?.[mesaId] || data?.joker;
  const catalogo = data?.catalogo_mesas || [
    { id: "oficial", nombre: "Mesa-0", beta: false },
  ];
  const chipsLive = vistaTodas
    ? data?.mesas?.oficial?.prediccion?.chips ||
      data?.joker?.prediccion?.chips ||
      []
    : panel?.prediccion?.chips || [];
  const horaViva =
    panel?.prediccion?.for ||
    data?.mesas?.oficial?.prediccion?.for ||
    data?.joker?.prediccion?.for;

  return (
    <div className="shell">
      <nav className="app-tabs" aria-label="Secciones">
        <button
          type="button"
          className={pestaña === "mesa" ? "activo" : ""}
          onClick={() => setPestaña("mesa")}
        >
          Mesa
        </button>
        <button
          type="button"
          className={pestaña === "cuentas" ? "activo" : ""}
          onClick={() => setPestaña("cuentas")}
        >
          Cuentas
        </button>
      </nav>

      <LiveAvance
        horaViva={horaViva}
        ultimaIngerida={data?.ultima_cerrada}
        chips={chipsLive}
        mesasChips={
          vistaTodas
            ? (catalogo || []).map(
                (m) =>
                  data?.mesas?.[m.id]?.prediccion?.chips ||
                  (m.id === "oficial"
                    ? data?.joker?.prediccion?.chips || []
                    : [])
              )
            : []
        }
        showSiguienteG={vistaTodas}
        onAvance={setLive}
        onTips={() => setModalTips(true)}
        tipsAbierto={modalTips}
        modalAbierto={modalLiveAbierto}
        setModalAbierto={setModalLiveAbierto}
        textoInicial={prefillLive}
        liveManualTexto={liveManualTexto}
      />

      {err && !modal ? <p className="err">{err}</p> : null}

      {pestaña === "cuentas" ? (
        <CuentasView live={live} horaViva={horaViva} simulPool7={simulPool7} />
      ) : vistaBoard === "v2" ? (
        <MesasTodasV2
          mesas={data?.mesas || { oficial: data?.joker }}
          catalogo={catalogo}
          live={live}
          extraccionAbierta={modalExtraccion}
          onExtraccion={onExtraccion}
          onAbrirMesa={onAbrirMesa}
        />
      ) : (
        <Panel
          id="joker"
          panel={panel}
          sel={sel}
          onSel={setSel}
          live={live}
          statsAbierto={modalStats}
          onCerrarStats={() => setModalStats(false)}
          onAbrirStats={() => setModalStats(true)}
          tipsAbierto={modalTips}
          onCerrarTips={() => setModalTips(false)}
          onAbrirTips={() => setModalTips(true)}
          historicoAbierto={modalHistorico}
          onCerrarHistorico={() => setModalHistorico(false)}
          onAbrirHistorico={() => setModalHistorico(true)}
        />
      )}

      <MesaOficialModales
        mesas={data?.mesas || { oficial: data?.joker }}
        catalogo={catalogo}
        panel={data?.mesas?.oficial || data?.joker}
        live={live}
        sel={sel}
        mesaActivaId={mesaId}
        onAbrirReplay={(id, tag) => {
          setMesaId(id);
          setSel(tag);
          if (tag) setVistaBoard("panel");
        }}
        tipsAbierto={modalTips}
        onCerrarTips={() => setModalTips(false)}
        historicoAbierto={modalHistorico}
        onCerrarHistorico={() => setModalHistorico(false)}
      />

      {sesion === true ? (
        <div
          className={modalExtraccion ? "modal-back" : undefined}
          style={modalExtraccion ? undefined : { display: "none" }}
          onClick={
            modalExtraccion ? () => setModalExtraccion(false) : undefined
          }
          role={modalExtraccion ? "presentation" : undefined}
          aria-hidden={!modalExtraccion}
        >
          <div
            className="modal modal-extraccion"
            role="dialog"
            aria-label="Extracción"
            onClick={(e) => e.stopPropagation()}
          >
            <Extraccion
              pollActivo={true}
              ultimaIngerida={data?.ultima_cerrada}
              mesas={data?.mesas || { oficial: data?.joker }}
              catalogo={catalogo}
              live={live}
              onCargarLive={(t) => {
                // Ya quedó en extraccion-en-vivo (API). Refuerzo inmediato en UI.
                setLiveManualTexto(t);
                setPrefillLive(t);
                setModalExtraccion(false);
                setSel(null);
              }}
              onAgregarCinta={(t) => {
                setTexto(t);
                setOkCinta("");
                setErr("");
                setModalExtraccion(false);
                setModal(true);
              }}
              onAutoCinta={onAutoCinta}
            />
          </div>
        </div>
      ) : null}

      {modal ? (
        <ModalCinta
          texto={texto}
          setTexto={setTexto}
          busy={busyCinta}
          err={err}
          ok={okCinta}
          onCerrar={() => {
            setModal(false);
            setOkCinta("");
            setErr("");
            setBusyCinta(false);
          }}
          onAgregar={confirmarCinta}
        />
      ) : null}
    </div>
  );
}
