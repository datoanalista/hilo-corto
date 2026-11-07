import { useEffect, useMemo, useRef, useState } from "react";
import { fingerprintLineas } from "./cintaParse.js";
import { crearPollVisibilidad } from "./pollVisibilidad.js";
import { parseTag, parseTiro, relojSistema } from "./live.js";
import { deltaAnillo, dist, etiquetaMesa, normalizePoolRowId, panelPool9, PINNED_POOL_IDS, pinnedPoolIdsForUI, poolHiddenInUI, pad } from "./mesa.js";
import { tipSiguienteG } from "./tipProxima.js";
import { chipsLiveRc } from "./liveRc.js";

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

function filaTramoValida(l) {
  return /^\d{2}:\d{2}-\d{2}:\d{2}\s/.test((l || "").trim());
}

/** Basura del F5 viejo: no entra a cinta ni al footer vivo. */
function sanitizarLineasExtraccion(lineas) {
  let lastVivo = -1;
  for (let i = 0; i < lineas.length; i += 1) {
    const s = (lineas[i] || "").trim();
    if (/en juego/i.test(s) && !/interrumpido/i.test(s)) lastVivo = i;
  }
  return lineas.filter((l, i) => {
    const s = (l || "").trim();
    if (/interrumpido/i.test(s)) return false;
    if (/en juego/i.test(s) && i !== lastVivo) return false;
    return true;
  });
}

function bloquesPorHora(lineas) {
  const bloques = [];
  let actual = null;
  for (const l of lineas) {
    if (!l) continue;
    if (/^h\d{1,2}-\d{6}$/i.test(l)) {
      actual = { header: l, filas: [] };
      bloques.push(actual);
    } else if (actual && filaTramoValida(l)) {
      actual.filas.push(l);
    }
  }
  return bloques;
}

function tagKey(tag) {
  const t = parseTag(tag);
  if (!t) return 0;
  return t.anio * 1e8 + t.mes * 1e6 + t.dia * 1e4 + t.hora;
}

function parseLineaFeed(l) {
  const s = (l || "").trim();
  if (!s) return null;
  if (/^h\d{1,2}-\d{6}$/i.test(s)) return { kind: "hora", tag: s };
  const m = /^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\s+(R|G\d?)(?:\s+(\d+))?/i.exec(s);
  if (m) {
    const tok = m[3].toUpperCase();
    return {
      kind: "tiro",
      a: m[1],
      b: m[2],
      color: tok.startsWith("G") ? "G" : "R",
      tipo: tok.startsWith("G") && tok.length > 1 ? tok.slice(1) : null,
      lumen: m[4] || null,
      raw: s,
    };
  }
  if (/en juego/i.test(s)) {
    // Huérfanos del F5 viejo: no son la ronda actual.
    if (/interrumpido/i.test(s)) return { kind: "otro", text: s };
    const ini = /^(\d{1,2}:\d{2})/.exec(s);
    return {
      kind: "vivo",
      text: s,
      inicio: ini ? ini[1] : null,
    };
  }
  return { kind: "otro", text: s };
}

function minutoDe(rango) {
  const m = /^(\d{1,2})/.exec(rango || "");
  return m ? Number(m[1]) : null;
}

function minutoPad(rango) {
  const n = minutoDe(rango);
  return n == null ? "—" : pad(n);
}

const HORAS_VISIBLES = 4;
const AUTO_CINTA_KEY = "hilo-corto-auto-cinta";
const AUTO_CINTA_DONE_KEY = "hilo-corto-auto-cinta-done";

function extraccionActivaDesdeApi(j) {
  return Boolean(
    j?.corriendo ||
      j?.estado === "conectado" ||
      j?.estado === "esperando" ||
      j?.estado === "pausado"
  );
}

function statsSeccion(items) {
  const tiros = items.filter((x) => x.kind === "tiro");
  const nG = tiros.filter((t) => t.color === "G").length;
  let sum = 0;
  for (const t of tiros) {
    if (t.lumen == null || Number.isNaN(Number(t.lumen))) continue;
    sum += Number(t.lumen);
  }
  return { nG, sum, vacia: tiros.length === 0 };
}

function textoStatsSeccion(stats) {
  if (stats.vacia) return "";
  return `${stats.nG} - ${stats.sum > 0 ? stats.sum : "—"}`;
}

function leerAutoCintaDone() {
  try {
    const raw = localStorage.getItem(AUTO_CINTA_DONE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr.map(String) : []);
  } catch (_) {
    return new Set();
  }
}

function guardarAutoCintaDone(set) {
  try {
    localStorage.setItem(AUTO_CINTA_DONE_KEY, JSON.stringify([...set]));
  } catch (_) {}
}

const LINE_ALIAS = {
  oficial: "Pool 0",
  "pool-9": "Pool 9",
  "oficial-classic": "Pool 9",
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
  if (panel?.inter2 || id === "inter2") return "Pool 8";
  if (panel?.liveRc || id === "live-rc") return "Pool 10";
  if (panel?.lc || id === "lc-01") return "Pool 7";
  if (
    id === "pool-9" ||
    id === "oficial-classic" ||
    panel?.pool9 ||
    panel?.classic
  )
    return "Pool 9";
  if (id && LINE_ALIAS[id]) return LINE_ALIAS[id];
  if (panel?.id && LINE_ALIAS[panel.id]) return LINE_ALIAS[panel.id];
  const m = etiquetaMesa(panel).match(/(\d+)/);
  return m ? `Pool ${m[1]}` : panel?.nombre || id || "Pool";
}

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

function chipsMesaEnHora(panel, id, tag, lucesHora) {
  if (!panel && id !== "lc-01" && id !== "live-rc") return [];
  if (id === "lc-01" || panel?.lc) return chipsLc01(lucesHora);
  if (id === "live-rc" || panel?.liveRc) return chipsLiveRc(lucesHora);
  const t = (tag || "").toLowerCase();
  const pred = panel?.prediccion;
  if (pred?.for && String(pred.for).toLowerCase() === t) {
    return pred.chips || [];
  }
  const hist = (panel?.historico || []).find(
    (h) => String(h.for || "").toLowerCase() === t
  );
  return hist?.chips || [];
}

function aciertosSobreLuz(minuto, lineas) {
  const out = [];
  for (const L of lineas || []) {
    for (const c of L.chips || []) {
      const d = dist(c, minuto);
      if (d > 1) continue;
      out.push({
        id: L.id,
        nombre: L.nombre,
        chip: c,
        clase: d === 0 ? "exacto" : "vecino",
        delta: d === 0 ? 0 : deltaAnillo(c, minuto),
      });
    }
  }
  return out;
}

function IconGrabar() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <circle cx="12" cy="12" r="7" fill="currentColor" />
    </svg>
  );
}

function IconDetener() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" />
    </svg>
  );
}

function IconLive() {
  return (
    <svg
      className="ex-icon-live"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      aria-hidden="true"
    >
      <path
        d="M4 12a8 8 0 0 1 16 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M7 12a5 5 0 0 1 10 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
    </svg>
  );
}

function IconCinta() {
  return (
    <svg
      className="ex-icon-cinta"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 10h18" />
      <circle cx="8" cy="15" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="16" cy="15" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

function IconRToggle({ tachado }) {
  return (
    <svg
      className="ex-icon-r-toggle"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      aria-hidden="true"
    >
      <text
        x="12"
        y="16.5"
        textAnchor="middle"
        fontSize="13"
        fontWeight="700"
        fill="currentColor"
        fontFamily="system-ui, sans-serif"
      >
        R
      </text>
      {tachado ? (
        <line
          x1="5"
          y1="19"
          x2="19"
          y2="5"
          stroke="#e04040"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}

let avisadoConexion = false;

export default function Extraccion({
  ultimaIngerida,
  onCargarLive,
  onAgregarCinta,
  onAutoCinta,
  mesas = null,
  catalogo = null,
  live = null,
  pollActivo = true,
}) {
  const [corriendo, setCorriendo] = useState(false);
  const [estado, setEstado] = useState("detenido");
  const [mensaje, setMensaje] = useState("");
  const [lineas, setLineas] = useState([]);
  const [modal, setModal] = useState(false);
  const [modalCargarLive, setModalCargarLive] = useState(false);
  const [modoCargar, setModoCargar] = useState("live");
  const [textoLive, setTextoLive] = useState("");
  const [busyCargar, setBusyCargar] = useState(false);
  const [busySync, setBusySync] = useState(false);
  const [msgSync, setMsgSync] = useState("");
  const [errCargar, setErrCargar] = useState("");
  const [horasSeleccionadas, setHorasSeleccionadas] = useState({});
  const [mostrarTodasHoras, setMostrarTodasHoras] = useState(false);
  const [modalHistoricoHoras, setModalHistoricoHoras] = useState(false);
  const [horaVista, setHoraVista] = useState(null);
  const seguirVivo = useRef(true);
  const [ocultarExitoConexion, setOcultarExitoConexion] = useState(false);
  const [detalleTiro, setDetalleTiro] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pausado, setPausado] = useState(false);
  const [err, setErr] = useState("");
  const autoCinta = true;
  const [ocultarR, setOcultarR] = useState(false);
  const autoBusy = useRef(false);
  const autoDone = useRef(leerAutoCintaDone());
  const autoTried = useRef(new Map());
  const onAutoCintaRef = useRef(onAutoCinta);
  onAutoCintaRef.current = onAutoCinta;
  const extraPollBusy = useRef(false);
  const feedRef = useRef(null);
  const pegadoAbajo = useRef(true);
  const lineasFpRef = useRef("");

  useEffect(() => {
    try {
      localStorage.setItem(AUTO_CINTA_KEY, "1");
    } catch (_) {}
  }, []);

  useEffect(() => {
    if (!pollActivo) return undefined;
    return crearPollVisibilidad(async () => {
      if (extraPollBusy.current) return;
      extraPollBusy.current = true;
      try {
        const r = await pedir("/api/extraccion/estado", { timeoutMs: 15000 });
        if (r.status === 401) return;
        const j = await r.json();
        if (!j.ok) return;
        setEstado(j.estado);
        setPausado(Boolean(j.pausado));
        setMensaje(j.mensaje || "");
        const lineasNuevas = sanitizarLineasExtraccion(j.lineas || []);
        const fp = j.lineas_fp || fingerprintLineas(lineasNuevas);
        if (fp !== lineasFpRef.current) {
          lineasFpRef.current = fp;
          setLineas(lineasNuevas);
        }
        setCorriendo(extraccionActivaDesdeApi(j));
        if (j.estado === "conectado" && !avisadoConexion) {
          avisadoConexion = true;
          setModal(true);
        }
        if (j.estado !== "conectado") {
          avisadoConexion = false;
        }
      } catch (_) {
        // silencioso
      } finally {
        extraPollBusy.current = false;
      }
    }, 2000);
  }, [pollActivo]);

  useEffect(() => {
    if (feedRef.current && pegadoAbajo.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [lineas]);

  useEffect(() => {
    if (!/conexi[oó]n exitosa/i.test(mensaje || "")) {
      setOcultarExitoConexion(false);
      return;
    }
    setOcultarExitoConexion(false);
    const id = window.setTimeout(() => setOcultarExitoConexion(true), 2000);
    return () => window.clearTimeout(id);
  }, [mensaje]);

  useEffect(() => {
    if (!msgSync) return undefined;
    const id = window.setTimeout(() => setMsgSync(""), 10000);
    return () => window.clearTimeout(id);
  }, [msgSync]);

  function alScrollear() {
    const el = feedRef.current;
    if (!el) return;
    const distanciaAlFondo = el.scrollHeight - el.scrollTop - el.clientHeight;
    pegadoAbajo.current = distanciaAlFondo < 48;
  }

  async function comenzar() {
    setBusy(true);
    setErr("");
    try {
      const r = await pedir("/api/extraccion/iniciar", { method: "POST" });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "no se pudo iniciar");
      setCorriendo(true);
      setEstado("esperando");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function detener() {
    setBusy(true);
    try {
      await pedir("/api/extraccion/detener", { method: "POST" });
    } finally {
      setCorriendo(false);
      setPausado(false);
      setEstado("detenido");
      setBusy(false);
    }
  }

  async function alternarPausa() {
    setBusy(true);
    setErr("");
    try {
      const ep = pausado ? "/api/extraccion/reanudar" : "/api/extraccion/pausar";
      const r = await pedir(ep, { method: "POST" });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "no se pudo cambiar el estado de pausa");
      const nuevoPausado = Boolean(j.pausado);
      setPausado(nuevoPausado);
      setEstado(nuevoPausado ? "pausado" : "conectado");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  const bloques = useMemo(() => bloquesPorHora(lineas), [lineas]);

  const secciones = useMemo(() => {
    const out = [];
    let cur = null;
    for (const l of lineas) {
      const p = parseLineaFeed(l);
      if (!p) continue;
      if (p.kind === "hora") {
        cur = { tag: p.tag, items: [] };
        out.push(cur);
      } else if (cur) {
        cur.items.push(p);
      }
    }
    return out;
  }, [lineas]);
  const seccionesRef = useRef(secciones);
  seccionesRef.current = secciones;

  const tagReloj = (live?.reloj?.tag || "").trim();

  const seccionesTodas = useMemo(() => {
    const sorted = [...secciones].sort((a, b) => tagKey(b.tag) - tagKey(a.tag));
    if (
      tagReloj &&
      !sorted.some((s) => s.tag.toLowerCase() === tagReloj.toLowerCase())
    ) {
      return [{ tag: tagReloj, items: [] }, ...sorted];
    }
    return sorted;
  }, [secciones, tagReloj]);

  const seccionesVisibles = useMemo(
    () => seccionesTodas.slice(0, HORAS_VISIBLES),
    [seccionesTodas]
  );

  const seccionesHistorico = useMemo(
    () => seccionesTodas.slice(HORAS_VISIBLES),
    [seccionesTodas]
  );

  const hayHistoricoHoras = seccionesHistorico.length > 0;

  // Auto-cinta: al pasar de hora, si no hay tiro abierto, pega sola a la cinta.
  useEffect(() => {
    if (!autoCinta || !onAutoCinta) return undefined;
    let cancel = false;

    async function tick() {
      if (cancel || autoBusy.current) return;
      const pegar = onAutoCintaRef.current;
      if (!pegar) return;
      const tagAhora = relojSistema().tag;
      const candidatos = [];
      for (const s of seccionesRef.current) {
        const tag = s.tag;
        if (!tag) continue;
        const key = tag.toLowerCase();
        if (key === tagAhora.toLowerCase()) continue;
        if (tagKey(tag) >= tagKey(tagAhora)) continue;
        if (autoDone.current.has(key)) continue;
        if (ultimaIngerida && tagKey(tag) <= tagKey(ultimaIngerida)) {
          autoDone.current.add(key);
          guardarAutoCintaDone(autoDone.current);
          continue;
        }
        if (s.items.some((x) => x.kind === "vivo")) continue;
        const tiros = s.items.filter((x) => x.kind === "tiro" && x.raw);
        if (tiros.length < 40) continue;
        const prevTry = autoTried.current.get(key);
        if (
          prevTry &&
          prevTry.n === tiros.length &&
          (prevTry.ok || Date.now() - prevTry.at < 60_000)
        ) {
          continue;
        }
        candidatos.push({ tag, tiros });
      }
      candidatos.sort((a, b) => tagKey(a.tag) - tagKey(b.tag));
      const next = candidatos[0];
      if (!next) return;

      const texto = `${next.tag}\n${next.tiros.map((t) => t.raw).join("\n")}\n`;
      autoTried.current.set(next.tag.toLowerCase(), {
        n: next.tiros.length,
        at: Date.now(),
        ok: false,
      });
      autoBusy.current = true;
      try {
        const j = await pegar(texto);
        if (cancel) return;
        const okSave = Boolean(j?.guardadas?.length) || j?.ok === true;
        autoTried.current.set(next.tag.toLowerCase(), {
          n: next.tiros.length,
          at: Date.now(),
          ok: okSave,
        });
        if (j?.guardadas?.length) {
          for (const g of j.guardadas) {
            autoDone.current.add(String(g).toLowerCase());
          }
          autoDone.current.add(next.tag.toLowerCase());
          guardarAutoCintaDone(autoDone.current);
        }
      } catch {
        /* silencioso: el checkbox auto-cinta ya indica el modo */
      } finally {
        autoBusy.current = false;
      }
    }

    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancel = true;
      clearInterval(id);
    };
  }, [autoCinta, ultimaIngerida, onAutoCinta]);

  const horaActivaTag =
    horaVista && secciones.some((s) => s.tag === horaVista)
      ? horaVista
      : seccionesTodas[0]?.tag || null;

  const seccionActiva = useMemo(
    () => secciones.find((s) => s.tag === horaActivaTag) || null,
    [secciones, horaActivaTag]
  );

  const esHoraEnVivo =
    Boolean(seccionesTodas[0]) &&
    seccionActiva?.tag === seccionesTodas[0]?.tag;

  const horaEnHistorico = Boolean(
    horaActivaTag &&
      !seccionesVisibles.some((s) => s.tag === horaActivaTag)
  );

  useEffect(() => {
    const tip = tagReloj || seccionesTodas[0]?.tag;
    if (!tip) {
      setHoraVista(null);
      return;
    }
    if (seguirVivo.current) setHoraVista(tip);
  }, [tagReloj, seccionesTodas[0]?.tag]);

  const tirosActivos = useMemo(
    () => (seccionActiva?.items || []).filter((x) => x.kind === "tiro"),
    [seccionActiva]
  );
  const tirosVisibles = useMemo(
    () => (ocultarR ? tirosActivos.filter((t) => t.color === "G") : tirosActivos),
    [tirosActivos, ocultarR]
  );
  const vivoActivo = useMemo(() => {
    const items = seccionActiva?.items || [];
    for (let i = items.length - 1; i >= 0; i -= 1) {
      if (items[i].kind === "vivo") return items[i];
    }
    return null;
  }, [seccionActiva]);

  const lucesHora = useMemo(
    () =>
      tirosActivos
        .filter((t) => t.color === "G")
        .map((t) => minutoDe(t.a))
        .filter((m) => m != null),
    [tirosActivos]
  );

  const lineasChips = useMemo(() => {
    const tag = horaActivaTag;
    if (!tag) return [];
    const byId = new Map();
    const pool9 = panelPool9(mesas);

    const add = (rawId, panel, nombreOverride) => {
      if (!panel && rawId !== "lc-01" && rawId !== "live-rc") return;
      const id = normalizePoolRowId(rawId, panel);
      if (byId.has(id)) return;
      const chips =
        id === "lc-01"
          ? chipsLc01(lucesHora)
          : id === "live-rc"
            ? chipsLiveRc(lucesHora)
            : chipsMesaEnHora(panel, id, tag, lucesHora);
      byId.set(id, {
        id,
        nombre: nombreOverride || etiquetaLinea(panel, id),
        chips,
      });
    };

    if (mesas?.inter2) add("inter2", mesas.inter2, "Pool 8");
    add("lc-01", { id: "lc-01", lc: true }, "Pool 7");
    // Pool 8 (inter2) y Pool 10 (live-rc): lógica viva; ocultos en UI

    const orden = catalogo?.length
      ? catalogo.map((c) => c.id)
      : ["oficial", "beta-v1", "beta-v2", "beta-v3", "beta-v4", "beta-v5"];
    for (const rawId of orden) {
      const id = normalizePoolRowId(rawId, mesas?.[rawId]);
      if (PINNED_POOL_IDS.includes(id)) continue;
      const panel =
        id === "pool-9" ? pool9 : mesas?.[rawId] || mesas?.[id];
      add(rawId, panel);
    }

    const pinnedSet = new Set(pinnedPoolIdsForUI());
    const pinned = pinnedPoolIdsForUI()
      .map((id) => byId.get(id))
      .filter(Boolean);
    const rest = [...byId.values()].filter(
      (l) => !pinnedSet.has(l.id) && !poolHiddenInUI(l.id, null, mesas)
    );
    return [...pinned, ...rest];
  }, [mesas, catalogo, horaActivaTag, lucesHora]);

  const nGActiva = lucesHora.length;
  const acumBrilloActiva = useMemo(() => {
    let sum = 0;
    for (const t of tirosActivos) {
      if (t.lumen == null || Number.isNaN(Number(t.lumen))) continue;
      sum += Number(t.lumen);
    }
    return sum;
  }, [tirosActivos]);

  const tagEnCurso = useMemo(() => relojSistema().tag, [modalCargarLive]);

  const bloquesElegibles = useMemo(() => {
    let list = [...bloques].sort(
      (a, b) => tagKey(b.header) - tagKey(a.header)
    );
    if (modoCargar === "cinta" && tagEnCurso) {
      list = list.filter(
        (b) => b.header.toLowerCase() !== tagEnCurso.toLowerCase()
      );
    }
    return list;
  }, [bloques, modoCargar, tagEnCurso]);

  const bloquesVisibles = mostrarTodasHoras
    ? bloquesElegibles
    : bloquesElegibles.slice(0, HORAS_VISIBLES);
  const hayMasHoras = bloquesElegibles.length > HORAS_VISIBLES;

  const estadoTxt =
    estado === "pausado" || pausado
      ? "pausado"
      : estado === "conectado"
        ? "en vivo"
        : estado === "error"
          ? "error"
          : estado === "esperando"
            ? "esperando"
            : "detenido";

  const esHoraIngesta =
    Boolean(
      horaActivaTag &&
        ultimaIngerida &&
        horaActivaTag.toLowerCase() === String(ultimaIngerida).toLowerCase()
    );

  const mensajeBanner = (() => {
    if (msgSync) return msgSync;
    if (err) return err;
    if (pausado || estado === "pausado") {
      return "⏸️ Extracción en pausa manual (sala detenida). El vigilante automático está en espera. Haz clic en Reanudar cuando la ruleta vuelva a girar.";
    }
    if (!mensaje) return "";
    if (/conexi[oó]n exitosa/i.test(mensaje)) {
      if (ocultarExitoConexion) return "";
      return mensaje;
    }
    return mensaje;
  })();

  function abrirModalCargar(modo) {
    setModoCargar(modo);
    setHorasSeleccionadas({});
    setMostrarTodasHoras(false);
    setErrCargar("");
    if (modo === "live") {
      const tag = relojSistema().tag;
      const sec = secciones.find(
        (s) => (s.tag || "").toLowerCase() === tag.toLowerCase()
      );
      const filas = (sec?.items || [])
        .filter((x) => x.kind === "tiro" && x.raw)
        .map((x) => x.raw);
      const cuerpo = filas.length ? filas.join("\n") + "\n" : "";
      setTextoLive(`${tag}\n${cuerpo}`);
    }
    setModalCargarLive(true);
  }

  async function confirmarCargarLive() {
    const t = textoLive.trim();
    if (!t) return;
    setBusyCargar(true);
    setErrCargar("");
    try {
      const r = await pedir("/api/extraccion/cargar-live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: t }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) {
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      if (Array.isArray(j.lineas)) {
        setLineas(sanitizarLineasExtraccion(j.lineas));
      }
      setModalCargarLive(false);
      onCargarLive?.(t, j);
    } catch (e) {
      setErrCargar(String(e.message || e));
    } finally {
      setBusyCargar(false);
    }
  }

  async function syncDesdeCinta(tag) {
    if (!tag) return;
    setBusySync(true);
    setMsgSync("");
    setErr("");
    try {
      const r = await pedir("/api/extraccion/sync-cinta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) {
        throw new Error(j.error || `HTTP ${r.status}`);
      }
      if (Array.isArray(j.lineas)) {
        setLineas(sanitizarLineasExtraccion(j.lineas));
      }
      setMsgSync(
        `${tag}: ${j.n_tramos} tramos restaurados desde la cinta oficial.`
      );
    } catch (e) {
      setMsgSync(String(e.message || e));
    } finally {
      setBusySync(false);
    }
  }

  function elegirHora(tag) {
    const tip = seccionesTodas[0]?.tag;
    seguirVivo.current = Boolean(tip && tag === tip);
    setHoraVista(tag);
  }

  function abrirDetalle(t) {
    const min = minutoDe(t.a);
    const hits =
      t.color === "G" && min != null
        ? aciertosSobreLuz(min, lineasChips)
        : [];
    setDetalleTiro({
      ...t,
      minuto: min,
      hora: horaActivaTag,
      hits,
    });
  }

  return (
    <section className="ex-panel">
      <header className="ex-top">
        <div className="ex-top-brand">
          <h2 className="ex-title">Extracción</h2>
          <span
            className={`ex-estado-pill ex-estado-${estado}${
              corriendo ? " grabando" : ""
            }`}
          >
            <i aria-hidden="true" />
            {estadoTxt}
          </span>
        </div>

        <div className="ex-toolbar" role="toolbar" aria-label="Controles de extracción">
          <button
            type="button"
            className={`ex-power${corriendo ? " stop" : " go"}${
              busy ? " busy" : ""
            }`}
            disabled={busy}
            onClick={corriendo ? detener : comenzar}
            title={corriendo ? "Detener captura" : "Iniciar captura"}
            aria-label={corriendo ? "Detener captura" : "Iniciar captura"}
          >
            {corriendo ? <IconDetener /> : <IconGrabar />}
          </button>

          {corriendo ? (
            <button
              type="button"
              className={`ex-pause-btn${pausado ? " pausado" : ""}${
                busy ? " busy" : ""
              }`}
              disabled={busy}
              onClick={alternarPausa}
              title={
                pausado
                  ? "Sala en pausa manual. Clic para reanudar extracción"
                  : "Pausar extracción (sala física detenida o respin)"
              }
              aria-label={pausado ? "Reanudar extracción" : "Pausar extracción"}
            >
              {pausado ? "▶ Reanudar" : "⏸ Pausar"}
            </button>
          ) : null}

          <span className="ex-top-kpis" aria-label="Hora activa">
            <span className="ex-kpi-box ex-g-box" title="G en esta hora">
              {nGActiva}
            </span>
            <span
              className="ex-kpi-box ex-acum-box"
              title="Luz acumulada en esta hora"
            >
              {acumBrilloActiva > 0 ? acumBrilloActiva : "—"}
            </span>
          </span>
          <button
            type="button"
            className={`ex-kpi-icon ex-r-toggle${ocultarR ? "" : " r-visible"}`}
            onClick={() => setOcultarR((v) => !v)}
            title={ocultarR ? "Mostrar rondas R" : "Ocultar rondas R"}
            aria-label={ocultarR ? "Mostrar rondas R" : "Ocultar rondas R"}
            aria-pressed={!ocultarR}
          >
            <IconRToggle tachado={!ocultarR} />
          </button>
          <button
            type="button"
            className="ex-kpi-icon"
            onClick={() => abrirModalCargar("live")}
            title="Cargar live"
            aria-label="Cargar live"
          >
            <IconLive />
          </button>
          <button
            type="button"
            className="ex-kpi-icon accent"
            disabled={!lineas.length}
            onClick={() => abrirModalCargar("cinta")}
            title="Ingesta"
            aria-label="Ingesta"
          >
            <IconCinta />
          </button>
        </div>
      </header>

      {mensajeBanner ? (
        <div className={`ex-banner${err ? " err" : ""}`}>{mensajeBanner}</div>
      ) : null}

      <div className="ex-stats ex-hora-meta">
        {seccionesVisibles.length ? (
          <div
            className={`ex-horas-rail${hayHistoricoHoras ? " con-historico" : ""}`}
            role="tablist"
            aria-label="Horas capturadas"
          >
            {seccionesVisibles.map((s, i) => {
              const on = s.tag === horaActivaTag;
              const stats = statsSeccion(s.items);
              const statsTxt = textoStatsSeccion(stats);
              const vivo = i === 0;
              const esIngesta =
                ultimaIngerida &&
                s.tag.toLowerCase() === String(ultimaIngerida).toLowerCase();
              return (
                <button
                  key={s.tag}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  className={`ex-hora-tab${on ? " on" : ""}${
                    vivo ? " live" : ""
                  }${esIngesta ? " ingesta" : ""}`}
                  onClick={() => elegirHora(s.tag)}
                  title={esIngesta ? "Última ingesta" : undefined}
                  aria-label={
                    esIngesta ? `${s.tag} · última ingesta` : undefined
                  }
                >
                  <strong>{s.tag}</strong>
                  <small>
                    {[
                      vivo ? "ahora" : "",
                      vivo && statsTxt ? " · " : "",
                      statsTxt || (vivo ? "" : "vacía"),
                    ].join("")}
                  </small>
                </button>
              );
            })}
            {hayHistoricoHoras ? (
              <button
                type="button"
                role="tab"
                aria-selected={horaEnHistorico || modalHistoricoHoras}
                className={`ex-hora-tab ex-hora-tab-historico${
                  horaEnHistorico ? " on" : ""
                }`}
                onClick={() => setModalHistoricoHoras(true)}
                title={`${seccionesHistorico.length} horas anteriores`}
              >
                <strong>Histórico</strong>
                <small>
                  {horaEnHistorico && horaActivaTag ? (
                    <>
                      <span className="ex-historico-tag">{horaActivaTag}</span>
                      {seccionesHistorico.length} horas
                    </>
                  ) : (
                    `${seccionesHistorico.length} horas`
                  )}
                </small>
              </button>
            ) : null}
          </div>
        ) : null}

        {!esHoraEnVivo && horaActivaTag && esHoraIngesta ? (
          <div className="ex-hora-acciones">
            <button
              type="button"
              className="ex-volver-vivo ex-sync-cinta"
              disabled={busySync}
              onClick={() => syncDesdeCinta(horaActivaTag)}
            >
              {busySync ? "Reingestando…" : "Reingesta"}
            </button>
          </div>
        ) : null}
      </div>

      <div
        ref={feedRef}
        className="ex-feed ex-feed-hora"
        onScroll={alScrollear}
        role="log"
        aria-live={esHoraEnVivo ? "polite" : "off"}
        aria-label={
          horaActivaTag ? `Tiros de ${horaActivaTag}` : "Captura en vivo"
        }
      >
        {!seccionActiva ? (
          <div className="ex-empty">
            <p>Sin captura todavía</p>
            <span>
              Tocá <b>Rec</b> y abrí Jokers Wheel en Chrome.
            </span>
          </div>
        ) : !tirosActivos.length && !vivoActivo ? (
          <div className="ex-empty">
            <p>Sin tiros en {horaActivaTag}</p>
            <span>Cuando salga una ronda, aparece acá.</span>
          </div>
        ) : (
          <>
            <div className="ex-minutos">
              {tirosVisibles.map((t, idx) => {
                const min = minutoDe(t.a);
                const hits =
                  t.color === "G" && min != null
                    ? aciertosSobreLuz(min, lineasChips)
                    : [];
                const cobrada = hits.length > 0;
                return (
                  <div key={`${t.a}-${t.b}-${idx}`} className="ex-min-wrap">
                    <button
                      type="button"
                      className={`ex-min ${t.color === "G" ? "g" : "r"}${
                        cobrada ? " hit" : ""
                      }`}
                      title={`${t.a}–${t.b}${
                        cobrada ? " · cobrada" : ""
                      }${t.lumen ? ` · ${t.lumen}` : ""}`}
                      onClick={() => abrirDetalle(t)}
                    >
                      <b>{minutoPad(t.a)}</b>
                      <em>{t.color === "G" ? `G${t.tipo || ""}` : "R"}</em>
                      {t.lumen ? <small>{t.lumen}</small> : null}
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {detalleTiro ? (
        <div className="modal-back" role="presentation">
          <div
            className="modal modal-ex-detalle"
            role="dialog"
            aria-label="Detalle del tiro"
          >
            <h2>
              Minuto {detalleTiro.minuto != null ? pad(detalleTiro.minuto) : "—"}
            </h2>
            <p className="ex-det-meta">
              <span className={`ex-badge ${detalleTiro.color === "G" ? "g" : "r"}`}>
                {detalleTiro.color === "G"
                  ? `G${detalleTiro.tipo || ""}`
                  : "R"}
              </span>
              <span>
                {detalleTiro.a}–{detalleTiro.b}
              </span>
              {detalleTiro.lumen ? (
                <span className="ex-det-lumen">{detalleTiro.lumen}</span>
              ) : null}
              {detalleTiro.hora ? (
                <span className="ex-det-hora">{detalleTiro.hora}</span>
              ) : null}
            </p>
            {detalleTiro.color !== "G" ? (
              <p className="hint">Ronda R · no es luz G.</p>
            ) : detalleTiro.hits.length === 0 ? (
              <p className="hint">Nadie cobró esta luz (ni exacto ni ±1).</p>
            ) : (
              <ul className="ex-det-hits">
                {detalleTiro.hits.map((h) => (
                  <li key={`${h.id}-${h.chip}-${h.clase}`}>
                    <strong>{h.nombre}</strong>
                    <span className={`ex-det-clase ${h.clase}`}>
                      {h.clase === "exacto"
                        ? "exacto"
                        : h.delta > 0
                          ? `+${h.delta}`
                          : `${h.delta}`}
                    </span>
                    <span className="ex-det-chip">ficha {pad(h.chip)}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="row">
              <button
                type="button"
                className="ghost"
                onClick={() => setDetalleTiro(null)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modalHistoricoHoras ? (
        <div
          className="modal-back"
          onClick={() => setModalHistoricoHoras(false)}
          role="presentation"
        >
          <div
            className="modal modal-horas modal-ex-historico"
            role="dialog"
            aria-labelledby="ex-historico-titulo"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="ex-historico-titulo">Histórico de captura</h2>
            <p className="hint horas-hint">
              Horas anteriores a las {HORAS_VISIBLES} recientes. Tocá una para
              ver sus tiros.
            </p>
            <div className="horas-lista">
              {seccionesHistorico.map((s) => {
                const on = s.tag === horaActivaTag;
                const statsTxt = textoStatsSeccion(statsSeccion(s.items));
                const esIngesta =
                  ultimaIngerida &&
                  s.tag.toLowerCase() === String(ultimaIngerida).toLowerCase();
                return (
                  <button
                    key={s.tag}
                    type="button"
                    className={`hora-card hora-card-btn${on ? " on" : ""}${
                      esIngesta ? " ingesta" : ""
                    }`}
                    onClick={() => {
                      elegirHora(s.tag);
                      setModalHistoricoHoras(false);
                    }}
                    title={esIngesta ? "Última ingesta" : undefined}
                  >
                    <span className="hora-card-body">
                      <strong className="hora-card-tag">{s.tag}</strong>
                      <span className="hora-card-meta">
                        {statsTxt || "vacía"}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="row horas-acciones">
              <button
                className="ghost"
                type="button"
                onClick={() => setModalHistoricoHoras(false)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modal ? (
        <div className="modal-back" role="presentation">
          <div className="modal modal-ex-toast" role="dialog">
            <h2>Conectado a Jokers</h2>
            <p>La captura ya está corriendo. Las rondas van a aparecer abajo.</p>
            <div className="row">
              <button type="button" onClick={() => setModal(false)}>
                Entendido
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {modalCargarLive ? (
        <div className="modal-back" role="presentation">
          <div
            className={`modal modal-horas${
              modoCargar === "live" ? " modal-live-texto" : ""
            }`}
            role="dialog"
            aria-labelledby="horas-titulo"
          >
            <h2 id="horas-titulo">
              {modoCargar === "cinta" ? "Agregar a la cinta" : "Cargar live"}
            </h2>
            {modoCargar === "live" ? (
              <>
                <p className="hint horas-hint">
                  Pegá la hora en curso (tag + tramos). Horas pasadas ya en
                  cinta: usá «Reingesta» en esa hora.
                </p>
                <textarea
                  className="ex-live-box"
                  autoFocus
                  spellCheck={false}
                  rows={12}
                  value={textoLive}
                  onChange={(e) => setTextoLive(e.target.value)}
                  placeholder={`h14-250826\n00:05-01:12 R\n01:13-02:40 G2 30`}
                  aria-label="tiros de la hora en curso"
                />
                {errCargar ? <p className="err">{errCargar}</p> : null}
                <div className="row horas-acciones">
                  <button
                    type="button"
                    disabled={!textoLive.trim() || busyCargar}
                    onClick={confirmarCargarLive}
                  >
                    {busyCargar ? "Cargando…" : "Cargar"}
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    disabled={busyCargar}
                    onClick={() => setModalCargarLive(false)}
                  >
                    Cancelar
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="hint horas-hint">
                  Más reciente arriba. La hora en curso no aparece: va al live.
                </p>
                <div className="horas-lista">
                  {bloquesVisibles.length ? (
                    bloquesVisibles.map((b, i) => {
                      const on = Boolean(horasSeleccionadas[b.header]);
                      const n = b.filas.length;
                      return (
                        <label
                          key={b.header}
                          className={`hora-card${on ? " on" : ""}`}
                        >
                          <input
                            type="checkbox"
                            checked={on}
                            onChange={(e) =>
                              setHorasSeleccionadas((prev) => ({
                                ...prev,
                                [b.header]: e.target.checked,
                              }))
                            }
                          />
                          <span className="hora-card-body">
                            <strong className="hora-card-tag">
                              {b.header}
                            </strong>
                            <span className="hora-card-meta">
                              {i === 0 && !mostrarTodasHoras
                                ? "más reciente · "
                                : ""}
                              {n} tiro{n === 1 ? "" : "s"}
                            </span>
                          </span>
                        </label>
                      );
                    })
                  ) : (
                    <p className="hint">
                      {bloques.length
                        ? "Solo está la hora en curso: cerrala primero o esperá."
                        : "Todavía no hay horas capturadas."}
                    </p>
                  )}
                </div>
                {hayMasHoras ? (
                  <button
                    type="button"
                    className="horas-mas"
                    onClick={() => setMostrarTodasHoras((v) => !v)}
                  >
                    {mostrarTodasHoras
                      ? "Ver solo las últimas 4"
                      : `Ver ${
                          bloquesElegibles.length - HORAS_VISIBLES
                        } anteriores`}
                  </button>
                ) : null}
                <div className="row horas-acciones">
                  <button
                    type="button"
                    disabled={!Object.values(horasSeleccionadas).some(Boolean)}
                    onClick={() => {
                      const textoElegido = [...bloquesElegibles]
                        .filter((b) => horasSeleccionadas[b.header])
                        .sort((a, b) => tagKey(a.header) - tagKey(b.header))
                        .map((b) => [b.header, ...b.filas].join("\n"))
                        .join("\n\n");
                      setModalCargarLive(false);
                      setMostrarTodasHoras(false);
                      onAgregarCinta?.(textoElegido);
                    }}
                  >
                    Agregar
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => {
                      setModalCargarLive(false);
                      setMostrarTodasHoras(false);
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
