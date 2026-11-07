import { useEffect, useMemo, useRef, useState } from "react";
import Habla from "./Habla.jsx";
import {
  cobraFicha,
  etiquetaMesa,
  hablaMesa,
  pad,
  poolHiddenInUI,
  ventanaVista,
  yaPaso,
} from "./mesa.js";
import { fusionFilasTips, notaPiso, pedirPiso } from "./piso.js";
import { tipsFlacaActivos } from "./opacidadInfo.js";
import TipsLabPanel from "./TipsLabPanel.jsx";
import { EcoTipsPanel } from "./EcoModal.jsx";
import { tipSiguienteG } from "./tipProxima.js";
import { chipsLiveRc, LIVE_RC_META } from "./liveRc.js";

async function pedirHistoricoMesa(mesaId) {
  const r = await fetch(
    `/api/tablero/historico?mesa=${encodeURIComponent(mesaId)}`,
    { credentials: "include" }
  );
  if (r.status === 401) throw new Error("entrar");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  if (j.ok === false) throw new Error(j.error || "fallo al leer histórico");
  return j;
}

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

const LINE_ALIAS = {
  oficial: "Pool 0",
  "pool-9": "Pool 9",
  "beta-v1": "Pool 1",
  "beta-v3": "Pool 2",
  "beta-v4": "Pool 3",
  "beta-v2": "Pool 4",
  "beta-v5": "Pool 5",
  "lc-01": "Pool 7",
  inter2: "Pool 8",
  "live-rc": "Pool 10",
};

function etiquetaLinea(panel, id) {
  if (id === "pool-9" || panel?.pool9 || panel?.classic || panel?.id === "pool-9")
    return "Pool 9";
  if (panel?.inter2 || id === "inter2") return "Pool 8";
  if (panel?.liveRc || id === "live-rc") return "Pool 10";
  if (panel?.lc || id === "lc-01") return "Pool 7";
  if (id === "oficial" || panel?.id === "oficial") return "Pool 0";
  if (id && LINE_ALIAS[id]) return LINE_ALIAS[id];
  if (panel?.id && LINE_ALIAS[panel.id]) return LINE_ALIAS[panel.id];
  const m = etiquetaMesa(panel).match(/(\d+)/);
  return m ? `Pool ${m[1]}` : panel?.nombre || id || "Pool";
}

/** Chips LC-01 de la hora viva (tips resueltos + tip actual). */
function chipsLc01(luces) {
  const sorted = [...new Set(luces || [])].sort((a, b) => a - b);
  const tips = [];
  for (let i = 0; i < sorted.length; i += 1) {
    const prev = tipSiguienteG({
      luces: sorted.slice(0, i),
      minutoAhora: null,
    });
    if (prev.tip != null) tips.push(prev.tip);
  }
  const cur = tipSiguienteG({ luces: sorted, minutoAhora: null });
  if (cur.tip != null) tips.push(cur.tip);
  return [...new Set(tips)].sort((a, b) => a - b);
}

function panelLc01(luces, horaTag) {
  const chips = chipsLc01(luces);
  return {
    id: "lc-01",
    nombre: "Pool 7",
    beta: false,
    lc: true,
    prediccion: {
      for: horaTag || null,
      chips,
      tiros: chips.map((m) => ({ minuto: m, flag: "TIBIO" })),
      lectura: "LC-01 · tip siguiente G (reloj)",
      h1: [],
    },
    historico: [],
    piso: null,
  };
}

function panelLiveRc(luces, horaTag) {
  const chips = chipsLiveRc(luces);
  return {
    id: "live-rc",
    nombre: LIVE_RC_META.nombre,
    beta: false,
    liveRc: true,
    prediccion: {
      for: horaTag || null,
      chips,
      tiros: chips.map((m) => ({ minuto: m, flag: "TIBIO" })),
      lectura: LIVE_RC_META.motor,
      h1: [],
    },
    historico: [],
    piso: null,
  };
}

function listaMesas(mesas, catalogo, panelFallback, live) {
  const orden = catalogo?.length
    ? catalogo.map((c) => c.id)
    : ["oficial", "beta-v1", "beta-v2", "beta-v3", "beta-v4", "beta-v5"];
  const out = [];
  const seen = new Set();

  const horaTag =
    mesas?.oficial?.prediccion?.for ||
    panelFallback?.prediccion?.for ||
    live?.reloj?.tag ||
    null;
  const luces = live?.luces || [];

  if (mesas?.inter2) {
    // Pool 8 (inter2): motor vivo; oculto en UI (UI_HIDDEN_POOL_IDS).
    out.push({
      id: "inter2",
      panel: { ...mesas.inter2, id: "inter2", inter2: true },
    });
    seen.add("inter2");
  }

  out.push({
    id: "lc-01",
    panel: panelLc01(luces, horaTag),
  });
  seen.add("lc-01");

  // Pool 10 (live-rc): panelLiveRc / chipsLiveRc siguen; no tab en UI

  for (const id of orden) {
    const p = mesas?.[id];
    if (!p || seen.has(id)) continue;
    seen.add(id);
    out.push({ id, panel: { ...p, id: p.id || id } });
  }
  if (out.length === 1 && panelFallback && !mesas) {
    out.push({
      id: panelFallback.id || "oficial",
      panel: panelFallback,
    });
  }
  return out.filter((f) => !poolHiddenInUI(f.id, f.panel, mesas));
}

/** Modales Tips + Histórico para todas las Lines (Panel / MESA). */
export default function MesaOficialModales({
  mesas = null,
  catalogo = null,
  panel = null,
  live = null,
  sel = null,
  mesaActivaId = "oficial",
  onAbrirReplay,
  onSel,
  tipsAbierto,
  onCerrarTips,
  historicoAbierto,
  onCerrarHistorico,
}) {
  const filas = useMemo(
    () => listaMesas(mesas, catalogo, panel, live),
    [mesas, catalogo, panel, live?.luces, live?.reloj?.tag]
  );

  const [mesaId, setMesaId] = useState(() => mesaActivaId || filas[0]?.id || "oficial");
  const estabaAbierto = useRef(false);
  const [histCache, setHistCache] = useState({});

  // Solo al abrir el modal: arrancar en la line activa. No pisar si el usuario cambia de tab.
  useEffect(() => {
    const abierto = Boolean(tipsAbierto || historicoAbierto);
    if (abierto && !estabaAbierto.current) {
      const existe = filas.some((f) => f.id === mesaActivaId);
      setMesaId(existe ? mesaActivaId : filas[0]?.id || "oficial");
    }
    estabaAbierto.current = abierto;
  }, [tipsAbierto, historicoAbierto, mesaActivaId, filas]);

  const actual = filas.find((f) => f.id === mesaId) || filas[0] || null;
  const panelActivo = actual?.panel || panel;
  const pred = panelActivo?.prediccion;
  const histPreview = panelActivo?.historico || [];
  const histTotal =
    panelActivo?.historico_total ?? histPreview.length;
  const cacheMesa = histCache[mesaId];
  const histCompleto = cacheMesa?.rows || null;
  const histLookup = histCompleto || histPreview;

  useEffect(() => {
    if (!historicoAbierto) return;
    const id = mesaId;
    if (id === "lc-01" || id === "live-rc") return;

    let cancelado = false;
    let debeFetch = false;
    setHistCache((prev) => {
      if (prev[id]?.rows || prev[id]?.loading) return prev;
      debeFetch = true;
      return {
        ...prev,
        [id]: { ...(prev[id] || {}), loading: true, error: null },
      };
    });
    if (!debeFetch) return;

    pedirHistoricoMesa(id)
      .then((j) => {
        if (cancelado) return;
        setHistCache((prev) => ({
          ...prev,
          [id]: {
            rows: j.historico || [],
            total: j.total ?? (j.historico || []).length,
            loading: false,
            error: null,
          },
        }));
      })
      .catch((e) => {
        if (cancelado) return;
        setHistCache((prev) => ({
          ...prev,
          [id]: {
            ...(prev[id] || {}),
            loading: false,
            error: String(e.message || e),
          },
        }));
      });

    return () => {
      cancelado = true;
    };
  }, [historicoAbierto, mesaId]);

  const histModal = historicoAbierto
    ? histCompleto || (cacheMesa?.loading ? null : histPreview)
    : histPreview;
  const replay =
    sel && mesaId === (mesaActivaId || mesaId)
      ? histLookup.find((h) => h.for === sel)
      : null;
  const chips = replay?.chips || pred?.chips || [];
  const tiros = replay
    ? (replay.chips_log || []).map((c) => ({
        minuto: c.minuto,
        flag: c.flag,
      }))
    : pred?.tiros || [];

  const [T, setT] = useState(0);
  const [marcas, setMarcas] = useState({});
  const [pisoReplay, setPisoReplay] = useState(null);

  const enHora = Boolean(live && !live.fuera && live.reloj);
  const ahora = replay
    ? null
    : enHora
      ? live.reloj.minuto
      : live?.ultimoMinuto != null
        ? live.ultimoMinuto
        : null;

  useEffect(() => {
    setT(ahora ?? 0);
    setMarcas({});
  }, [sel, pred?.for, mesaId]);

  useEffect(() => {
    if (replay) return;
    if (ahora != null) setT(ahora);
  }, [ahora, replay]);

  useEffect(() => {
    if (!replay) {
      setPisoReplay(null);
      return;
    }
    let vivo = true;
    pedirPiso(replay.for).then((j) => {
      if (vivo) setPisoReplay(j);
    });
    return () => {
      vivo = false;
    };
  }, [replay?.for]);

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

  const pleno = (tiros || []).find((t) => t.flag === "SEGURO");
  const fotoVacia = !(chips || []).length;
  const pisoActivo = replay
    ? pisoReplay
    : panelActivo?.piso?.ok
      ? panelActivo.piso
      : null;

  const habla = useMemo(() => {
    if (!panelActivo) return null;
    const base = hablaMesa({
      T,
      oficiales,
      chips,
      tiros,
      hayPleno: Boolean(pleno),
      plenoMin: pleno?.minuto ?? null,
      fotoVacia,
      h1: replay?.h1 || pred?.h1 || [],
      nGClima: pred?.nG_clima ?? null,
      k: pred?.k ?? chips?.length ?? null,
      som02Meta: pred?.som02 ?? null,
      modo: replay ? "replay" : "viva",
      hora: replay ? replay.for : pred?.for,
      abierta:
        Boolean(enHora || live?.luces?.length || Object.keys(marcas).length) &&
        !replay,
    });
    if (!base) return null;
    const nota = notaPiso(pisoActivo);
    const filasTips = fusionFilasTips(
      base.tips?.filas || [],
      pisoActivo?.filas || []
    );
    const parrafos = [...(base.parrafos || [])];
    if (nota && !parrafos.some((p) => p.startsWith("Piso:"))) {
      parrafos.push(nota);
    }
    return {
      ...base,
      parrafos,
      tips: { ...(base.tips || {}), filas: filasTips },
    };
  }, [
    panelActivo,
    T,
    oficiales,
    chips,
    tiros,
    pleno,
    fotoVacia,
    replay,
    pred?.h1,
    pred?.for,
    enHora,
    live?.luces,
    marcas,
    pisoActivo,
  ]);

  const tipsLab = useMemo(() => {
    const brillo = live?.brillo;
    if (!brillo) return { cola: [], flaca: [], hay: false, alerta: false };
    const cola = brillo.tipsColaG || [];
    const flaca = tipsFlacaActivos(
      brillo.tipsOpacidad,
      brillo.tipsIntraHora
    );
    return {
      cola,
      flaca,
      hay: cola.length > 0 || flaca.length > 0,
      alerta:
        cola.some((t) => t.alerta || t.tono === "confirmada") ||
        flaca.some((t) => t.alerta),
    };
  }, [
    live?.brillo?.fingerprint,
    live?.brillo?.tipsColaG,
    live?.brillo?.tipsOpacidad,
    live?.brillo?.tipsIntraHora,
  ]);

  const ecoHay = useMemo(() => {
    const lineas = live?.eco?.lineas || [];
    return lineas.some(
      (l) => l && !/no es boleto/i.test(l) && !/^Eco:\s*sin/i.test(l)
    );
  }, [live?.eco?.fingerprint, live?.eco?.lineas]);

  function elegirHora(tag) {
    const id = actual?.id || "oficial";
    if (id === "lc-01" || id === "live-rc") return;
    if (onAbrirReplay) {
      onAbrirReplay(id, tag === sel && id === mesaActivaId ? null : tag);
    } else {
      onSel?.(tag === sel ? null : tag);
    }
    onCerrarHistorico?.();
  }

  function tabs(aria) {
    if (filas.length <= 1) return null;
    return (
      <div className="hist-tabs" role="tablist" aria-label={aria}>
        {filas.map((f) => {
          const lab = etiquetaLinea(f.panel, f.id);
          const on = f.id === (actual?.id || mesaId);
          const n =
            f.panel?.historico_total ?? (f.panel?.historico || []).length;
          return (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={on}
              className={`hist-tab${on ? " on" : ""}`}
              onClick={() => setMesaId(f.id)}
              title={`${lab}${n ? ` · ${n} horas` : ""}`}
            >
              {lab}
            </button>
          );
        })}
      </div>
    );
  }

  if (!panelActivo && !filas.length) return null;

  return (
    <>
      {tipsAbierto ? (
        <div
          className="modal-back"
          onClick={() => onCerrarTips?.()}
          role="presentation"
        >
          <div
            className="modal modal-tips"
            role="dialog"
            aria-label="Tips de la hora"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="hist-modal-head">
              <h2>Tips de la hora</h2>
              {live?.tag || pred?.for ? (
                <p className="hint">{live?.tag || pred?.for}</p>
              ) : null}
            </div>

            <TipsLabPanel colaTips={tipsLab.cola} flacaTips={tipsLab.flaca} />

            {live?.costuraH15 ? (
              <p className="tips-costura-h15" role="note">
                <strong>{live.costuraH15.pill}</strong> {live.costuraH15.linea}
              </p>
            ) : null}

            <EcoTipsPanel eco={live?.eco} />

            {tipsLab.hay || ecoHay || live?.costuraH15 ? (
              <hr className="tips-lab-sep" aria-hidden="true" />
            ) : null}

            <div className="hist-modal-head tips-mesa-head">
              <h3 className="proy-seccion-titulo">
                Mesa · {etiquetaLinea(panelActivo, actual?.id)}
              </h3>
              {tabs("Elegir line para tips")}
            </div>
            {habla ? (
              <Habla habla={habla} T={T} planLectura={pred?.lectura} />
            ) : (
              <p className="hint">Sin novedades por ahora.</p>
            )}
            <div className="row">
              <button
                className="ghost"
                type="button"
                onClick={() => onCerrarTips?.()}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {historicoAbierto ? (
        <div
          className="modal-back"
          onClick={() => onCerrarHistorico?.()}
          role="presentation"
        >
          <div
            className="modal modal-historico"
            role="dialog"
            aria-label="Mesas anteriores"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="hist-modal-head">
              <h2>Mesas anteriores</h2>
              {tabs("Elegir line")}
            </div>
            <p className="hint">
              {etiquetaLinea(panelActivo, actual?.id)} · tocá una hora para
              oírla
              {histTotal > histPreview.length
                ? ` · últimas ${histPreview.length} en vivo · ${histTotal} en total`
                : ""}
            </p>
            {cacheMesa?.loading && !histCompleto ? (
              <p className="hint">Cargando histórico completo…</p>
            ) : null}
            {cacheMesa?.error && !histCompleto ? (
              <p className="err">{cacheMesa.error}</p>
            ) : null}
            {(histModal || []).length === 0 ? (
              <p className="hint">
                {actual?.id === "lc-01"
                  ? "Pool 7 es tip LC-01 en vivo · no guarda histórico de cinta. Abrí Tips para la hora actual."
                  : actual?.id === "live-rc"
                    ? "Pool 10 es LIVE-RC en vivo · recomputa chips intra-hora. Abrí Tips para la hora actual."
                    : "Sin histórico todavía en esta line."}
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>hora</th>
                    <th>cobró</th>
                    <th>vecino</th>
                    <th>banda</th>
                    <th>fichas</th>
                  </tr>
                </thead>
                <tbody>
                  {[...(histModal || [])].reverse().map((h) => (
                    <tr
                      key={`${actual?.id}-${h.for}`}
                      className={
                        h.for === sel && actual?.id === mesaActivaId
                          ? "sel"
                          : ""
                      }
                      onClick={() => elegirHora(h.for)}
                    >
                      <td>{h.for}</td>
                      <td>
                        {h.g_ok}/{h.g_of}
                      </td>
                      <td>{h.pm1}</td>
                      <td className={pctClass(h.pct)}>{pct(h.pct)}</td>
                      <td>{chipsTxt(h.chips)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="row">
              <button
                className="ghost"
                type="button"
                onClick={() => onCerrarHistorico?.()}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function IconTip() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        d="M12 2a7 7 0 0 0-4 12.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26A7 7 0 0 0 12 2z"
        fill="currentColor"
      />
      <rect x="9" y="20" width="6" height="2" rx="1" fill="currentColor" />
    </svg>
  );
}

export function IconHistorico() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <circle
        cx="12"
        cy="13"
        r="8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M12 9v4l3 2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M9 2h6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
