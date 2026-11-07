import { useEffect, useMemo, useRef, useState } from "react";
import { andenFrase, andenRango, cobraFicha, pad } from "./mesa.js";
import {
  ETAPAS,
  anteriorTag,
  analizarEtapa,
  liveEstado,
  lucesDe,
  parseTag,
  parseTiro,
  relojSistema,
} from "./live.js";
import {
  tipSiguienteG,
  minutoLivePlayhead,
  enZonaPool7,
} from "./tipProxima.js";
import {
  diagnosticarGo,
  diagnosticarApostador,
  esGoSequia,
  minutosGoAcierto,
} from "./sequiaGo.js";
import { diagnosticarFuerza } from "./fuerzaInfo.js";
import { FuerzaBtn } from "./FuerzaBtn.jsx";
import { AlarmaGoBtn } from "./AlarmaGoBtn.jsx";
import { costuraH15Info } from "./pasoLiveInfo.js";
import { IconTip } from "./MesaOficialModales.jsx";
import {
  buildBrilloLectura,
  brilloTagBody,
  brilloTooltipTitle,
} from "./brilloInfo.js";
import { colaGTagLive, buildColaLectura } from "./colaGInfo.js";
import { tipsFlacaActivos } from "./opacidadInfo.js";
import { buildEcoLectura } from "./ecoInfo.js";
import {
  buildCalendarioLectura,
  calendarioTooltipTitle,
} from "./calendarioInfo.js";
import { buildCierreAbierto } from "./cierreAbiertoInfo.js";
import { buildBloquePerfil } from "./bloquePerfilInfo.js";
import { buildOlaPostSnLectura } from "./olaPostSnInfo.js";
import { buildGestoEsperado } from "./gestoInfo.js";
import { buildLamparaLectura } from "./lamparaInfo.js";
import BrilloModal, { IconBrillo } from "./BrilloModal.jsx";
import CalendarioModal, { IconCalendario } from "./CalendarioModal.jsx";
import RecordsModal, { IconRecords } from "./RecordsModal.jsx";
import SupernovaModal, { IconSupernova } from "./SupernovaModal.jsx";
import ColaModal from "./ColaModal.jsx";
import {
  actualizarRegistroBloques,
  buildSupernovaLectura,
  supernovaTooltipTitle,
} from "./supernovaInfo.js";
import { fingerprintLineas, tailLineasHoras } from "./cintaParse.js";
import { crearPollVisibilidad } from "./pollVisibilidad.js";
import LiveRelojTick from "./LiveRelojTick.jsx";

const RE_HEADER = /^h\d{1,2}-\d{6}$/i;
const RE_TRAMO = /^\d{1,2}:\d{2}-\d{1,2}:\d{2}\s+(R|G\d?)/i;

/** Tramos cerrados de una hora: corta al próximo header (no mezcla horas). */
function tramosCerradosDeHora(lineas, tag) {
  if (!tag) return [];
  const needle = tag.trim().toLowerCase();
  const idx = (lineas || []).findIndex(
    (l) => (l || "").trim().toLowerCase() === needle
  );
  if (idx < 0) return [];
  const out = [];
  for (let i = idx + 1; i < lineas.length; i += 1) {
    const s = (lineas[i] || "").trim();
    if (!s) continue;
    if (RE_HEADER.test(s)) break;
    if (RE_TRAMO.test(s)) out.push(s);
  }
  return out;
}

/** Une tramos captura + manual. Mismo MM:SS de inicio → gana el manual (Cargar live). */
function mergeTramos(...listas) {
  const byStart = new Map();
  for (const lista of listas) {
    for (const l of lista || []) {
      const s = (l || "").trim();
      if (!s || !RE_TRAMO.test(s)) continue;
      const m = /^(\d{1,2}):(\d{1,2})/.exec(s);
      if (!m) continue;
      const k = `${Number(m[1])}:${Number(m[2])}`;
      byStart.set(k, s);
    }
  }
  const out = [...byStart.values()];
  out.sort((a, b) => {
    const ma = /^(\d{1,2}):(\d{2})/.exec(a);
    const mb = /^(\d{1,2}):(\d{2})/.exec(b);
    if (!ma || !mb) return 0;
    return Number(ma[1]) * 60 + Number(ma[2]) - (Number(mb[1]) * 60 + Number(mb[2]));
  });
  return out;
}

function colaHora(lineas) {
  let tag = "";
  let nCerrados = 0;
  let ultimo = "";
  let vivo = "";
  for (const l of lineas || []) {
    const s = (l || "").trim();
    if (!s) continue;
    if (RE_HEADER.test(s)) {
      tag = s.toLowerCase();
      nCerrados = 0;
      ultimo = "";
      vivo = "";
      continue;
    }
    if (RE_TRAMO.test(s)) {
      nCerrados += 1;
      ultimo = s;
      continue;
    }
    if (/en juego/i.test(s) && !/interrumpido/i.test(s)) vivo = s;
  }
  return { tag, nCerrados, ultimo, vivo };
}

/** Lectura a medias del .txt → no pisar estado bueno. Si la hora viva avanzó, aceptar. */
function pareceCintaTruncada(prev, next) {
  if (!prev?.length || !next?.length) return false;
  if (next.length >= prev.length) return false;
  const a = colaHora(prev);
  const b = colaHora(next);
  if (b.tag && b.nCerrados > a.nCerrados) return false;
  if (b.tag && a.tag && b.tag !== a.tag) return false;
  if (b.ultimo && b.ultimo !== a.ultimo) return false;
  if (b.vivo && b.vivo !== a.vivo) return false;
  if (prev.length - next.length < 3) return false;
  const prev0 = (prev[0] || "").trim().toLowerCase();
  const next0 = (next[0] || "").trim().toLowerCase();
  if (prev0 !== next0 && next.length >= 40) return false;
  return true;
}

/** La captura de Extracción sigue la hora del reloj (aunque ingesta vaya atrás). */
function capturaSigueReloj(lineas, tagReloj) {
  if (!tagReloj || !(lineas || []).length) return false;
  const tag = tagReloj.trim().toLowerCase();
  const prev = anteriorTag(tagReloj);
  if (
    tramosCerradosDeHora(lineas, tagReloj).length ||
    horaTiroEnCurso(lineas, tagReloj)
  ) {
    return true;
  }
  if (prev && horaTiroEnCurso(lineas, prev)) return true;
  return (lineas || []).some((l) => (l || "").trim().toLowerCase() === tag);
}

/** HH:MM:SS del tiro abierto de la hora (estático hasta el próximo). */
function horaTiroEnCurso(lineas, tag) {
  if (!tag) return null;
  const needle = tag.trim().toLowerCase();
  const idx = (lineas || []).findIndex(
    (l) => (l || "").trim().toLowerCase() === needle
  );
  if (idx < 0) return null;
  let inicio = null;
  for (let i = idx + 1; i < lineas.length; i += 1) {
    const s = (lineas[i] || "").trim();
    if (!s) continue;
    if (RE_HEADER.test(s)) break;
    if (/en juego/i.test(s) && !/interrumpido/i.test(s)) {
      const m = /^(\d{1,2}):(\d{2})/.exec(s);
      if (m) inicio = { mm: Number(m[1]), ss: Number(m[2]) };
    }
  }
  if (!inicio) return null;
  const t = parseTag(tag);
  if (!t) return `${pad(inicio.mm)}:${pad(inicio.ss)}`;
  return `${pad(t.hora)}:${pad(inicio.mm)}:${pad(inicio.ss)}`;
}

export default function LiveAvance({
  horaViva,
  ultimaIngerida,
  chips = [],
  mesasChips = [],
  showSiguienteG = false,
  onAvance,
  onTips,
  tipsAbierto = false,
  modalAbierto,
  setModalAbierto,
  onCajaOnChange,
  textoInicial,
  liveManualTexto = "",
}) {
  const [texto, setTexto] = useState("");
  const [ahora, setAhora] = useState(() => relojSistema());
  const [err, setErr] = useState("");
  const [etapa, setEtapa] = useState(0);
  const [locked, setLocked] = useState([]);
  const [pendiente, setPendiente] = useState(null);
  const [extraLineas, setExtraLineas] = useState([]);
  const [extraccionCorriendo, setExtraccionCorriendo] = useState(false);
  const [extraccionPausada, setExtraccionPausada] = useState(false);
  const [expandido, setExpandido] = useState(false);
  const [brilloAbierto, setBrilloAbierto] = useState(false);
  const [brilloLeidoFp, setBrilloLeidoFp] = useState("");
  const [tipsLeidoFp, setTipsLeidoFp] = useState("");
  const [supernovaAbierto, setSupernovaAbierto] = useState(false);
  const [colaAbierto, setColaAbierto] = useState(false);
  const [calendarioAbierto, setCalendarioAbierto] = useState(false);
  const [recordsAbierto, setRecordsAbierto] = useState(false);
  const [registroBloques, setRegistroBloques] = useState([]);
  const supernovaParpadeabaRef = useRef(false);
  const supernovaAlertaPrevRef = useRef(null);
  const cronistaEnviado = useRef(new Set());
  const extraLineasFpRef = useRef("");
  const extraPollBusy = useRef(false);

  useEffect(() => {
    function syncReloj() {
      const r = relojSistema();
      setAhora((prev) => {
        if (
          prev.tag === r.tag &&
          prev.hora === r.hora &&
          prev.minuto === r.minuto &&
          prev.fecha === r.fecha
        ) {
          return prev;
        }
        return r;
      });
    }
    syncReloj();
    const id = setInterval(syncReloj, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    return crearPollVisibilidad(async () => {
      if (extraPollBusy.current) return;
      extraPollBusy.current = true;
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 15000);
        try {
          const r = await fetch("/api/extraccion/estado", {
            credentials: "include",
            signal: ctrl.signal,
          });
          if (r.status === 401) return;
          const j = await r.json();
          if (!j.ok) return;
          const lineas = j.lineas || [];
          const fp = j.lineas_fp || fingerprintLineas(lineas);
          setExtraccionCorriendo(Boolean(j.corriendo));
          setExtraccionPausada(Boolean(j.pausado));
          if (fp === extraLineasFpRef.current) return;
          setExtraLineas((prev) => {
            if (pareceCintaTruncada(prev, lineas)) return prev;
            extraLineasFpRef.current = fp;
            return lineas;
          });
        } finally {
          clearTimeout(timer);
        }
      } catch (_) {
        // silencioso: el próximo poll reintenta
      } finally {
        extraPollBusy.current = false;
      }
    }, 2000);
  }, []);

  const estado = liveEstado(ahora, ultimaIngerida);
  const disponible = estado.disponible;
  const ingestaAlDia = estado.razon === "curso" || estado.razon === "ya";
  const tagReloj = ahora.tag;

  const extraLineasFp = useMemo(
    () => fingerprintLineas(extraLineas),
    [extraLineas]
  );

  /** Solo últimas horas para tips (cola, opacidad, costura) — evita OOM. */
  const lineasTips = useMemo(
    () => tailLineasHoras(extraLineas, 32),
    [extraLineasFp]
  );
  const lineasTipsFp = useMemo(
    () => fingerprintLineas(lineasTips),
    [lineasTips]
  );

  const capturaViva = useMemo(
    () =>
      extraccionCorriendo && capturaSigueReloj(extraLineas, tagReloj),
    [extraccionCorriendo, extraLineasFp, tagReloj, extraLineas]
  );
  const cabeceraOnline = ingestaAlDia || capturaViva;

  // Luces live = hora del reloj. Solo nos quedamos en H-1 si esa ronda
  // sigue "en juego". El boleto viejo no pinta G de otra hora.
  const tagHora = useMemo(() => {
    const prev = anteriorTag(tagReloj);
    if (prev && horaTiroEnCurso(extraLineas, prev)) return prev;
    return tagReloj;
  }, [tagReloj, extraLineasFp, extraLineas]);

  const sosteniendoHora = tagHora.toLowerCase() !== tagReloj.toLowerCase();
  const liveActivo = ingestaAlDia || sosteniendoHora || capturaViva;

  useEffect(() => {
    cronistaEnviado.current = new Set();
  }, [tagHora]);

  useEffect(() => {
    setEtapa(0);
    setLocked([]);
    setPendiente(null);
    setTexto("");
    setErr("");
    setExpandido(false);
    setBrilloAbierto(false);
    setBrilloLeidoFp("");
    setTipsLeidoFp("");
    setSupernovaAbierto(false);
    setRegistroBloques([]);
    supernovaParpadeabaRef.current = false;
    supernovaAlertaPrevRef.current = null;
  }, [tagHora]);
  const meta = ETAPAS[etapa] || null;
  // Fuera = cinta atrasada más de 1 hora. El playhead sigue el reloj en curso/ya.
  // Si sostenemos la hora anterior por la última ronda, no cortar el score.
  const fueraReloj =
    estado.razon === "espera" && !sosteniendoHora && !capturaViva;

  // Tramos reales de la hora en curso (captura + Cargar live manual).
  const lineasHoraActual = useMemo(() => {
    const deCaptura = tramosCerradosDeHora(extraLineas, tagHora);
    const deManual = liveManualTexto
      ? tramosCerradosDeHora(
          liveManualTexto.split(/\r?\n/),
          tagHora
        )
      : [];
    // Si el pegado no trae header de esta hora, aceptar tramos sueltos del texto.
    let manualExtra = deManual;
    if (!manualExtra.length && liveManualTexto) {
      const lineas = liveManualTexto.split(/\r?\n/);
      const tieneOtroHeader = lineas.some(
        (l) =>
          RE_HEADER.test((l || "").trim()) &&
          (l || "").trim().toLowerCase() !== tagHora.toLowerCase()
      );
      if (!tieneOtroHeader) {
        manualExtra = lineas
          .map((l) => (l || "").trim())
          .filter((s) => RE_TRAMO.test(s));
      }
    }
    return mergeTramos(deCaptura, manualExtra);
  }, [extraLineasFp, tagHora, liveManualTexto]);

  const tiroEnCurso = useMemo(() => {
    const cur = horaTiroEnCurso(extraLineas, tagHora);
    if (cur) return cur;
    if (tagHora.toLowerCase() !== tagReloj.toLowerCase()) {
      return horaTiroEnCurso(extraLineas, tagReloj);
    }
    return null;
  }, [extraLineasFp, tagHora, tagReloj, extraLineas]);

  const tirosRealesHoraActual = useMemo(
    () => lineasHoraActual.map((l) => parseTiro(l)).filter(Boolean),
    [lineasHoraActual]
  );
  const manualTodos = useMemo(
    () => pendiente?.todos || locked,
    [pendiente?.todos, locked]
  );
  const tirosHoraActual = useMemo(
    () => [...manualTodos, ...tirosRealesHoraActual],
    [manualTodos, tirosRealesHoraActual]
  );
  const tirosKey = useMemo(
    () =>
      tirosHoraActual
        .map((t) => `${t.m0}:${t.lumen ?? t.vecino ?? ""}:${t.color}`)
        .join("|"),
    [tirosHoraActual]
  );
  const verdesHoraActual = useMemo(
    () =>
      tirosHoraActual
        .filter((t) => t.color === "G")
        .map((t) => ({
          minuto: t.m0,
          tipo: t.tipo,
          vecino: t.vecino,
          lumen: t.lumen ?? t.vecino,
          inicio: `${pad(t.m0)}:${pad(t.s0)}`,
          fin: `${pad(t.m1)}:${pad(t.s1)}`,
        })),
    [tirosHoraActual]
  );

  const minutoScore = sosteniendoHora
    ? tirosHoraActual.at(-1)?.m1 ?? 59
    : ahora.minuto;

  const brilloLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildBrilloLectura({
      tiros: tirosHoraActual,
      minuto: minutoScore,
      tag: tagHora,
      cintaLineas: lineasTips,
    });
  }, [
    liveActivo,
    tagHora,
    minutoScore,
    lineasTipsFp,
    tirosKey,
  ]);

  const cierreLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildCierreAbierto({
      tiros: tirosHoraActual,
      minuto: minutoScore,
    });
  }, [liveActivo, minutoScore, tirosKey]);

  const bloquePerfilLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildBloquePerfil({
      tiros: tirosHoraActual,
      minuto: minutoScore,
    });
  }, [liveActivo, minutoScore, tirosKey]);

  const olaPostSnLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildOlaPostSnLectura({
      tiros: tirosHoraActual,
      minuto: minutoScore,
      tag: tagHora,
      horaCerrada: sosteniendoHora,
      brillo: brilloLectura,
    });
  }, [
    liveActivo,
    minutoScore,
    tirosKey,
    tagHora,
    sosteniendoHora,
    brilloLectura?.fingerprint,
  ]);

  const brilloNuevo =
    Boolean(brilloLectura?.fingerprint) &&
    brilloLectura.fingerprint !== brilloLeidoFp;
  const brilloTag = useMemo(
    () => brilloTagBody(brilloLectura),
    [brilloLectura]
  );
  const costuraAlerta = Boolean(
    brilloLectura?.costuras?.some((c) => c.alerta && c.ok) ||
      brilloLectura?.costura?.alerta
  );
  const colaAlerta = Boolean(
    brilloLectura?.tipsColaG?.some((t) => t.alerta || t.tono === "confirmada")
  );
  const colaTag = useMemo(
    () => colaGTagLive(brilloLectura?.tipsColaG),
    [brilloLectura?.tipsColaG]
  );
  const colaLectura = useMemo(() => {
    if (!colaTag || !brilloLectura) return null;
    return buildColaLectura({
      brillo: brilloLectura,
      cintaLineas: lineasTips,
    });
  }, [colaTag, brilloLectura, lineasTipsFp]);
  const flacaAlerta = Boolean(
    brilloLectura?.tipsOpacidad?.some((t) => t.id === "flaca-cierre-perfil") ||
      brilloLectura?.tipsIntraHora?.some((t) => t.id === "flaca-olor-20")
  );
  const brilloEsOpaco = useMemo(() => {
    if (!brilloLectura) return false;
    if (brilloLectura.tone === "opaco") return true;
    const banda = `${brilloLectura.pill || ""} ${brilloLectura.bandaTotal || ""}`;
    return /opac|apagad/i.test(banda);
  }, [brilloLectura]);
  const colaEnHeader = useMemo(() => {
    if (!colaTag) return false;
    const activa = colaTag === "Cola · activa";
    if (activa) return true;
    return !brilloEsOpaco;
  }, [colaTag, brilloEsOpaco]);
  const tipsLabHay = useMemo(() => {
    if (!brilloLectura) return false;
    const flaca = tipsFlacaActivos(
      brilloLectura.tipsOpacidad,
      brilloLectura.tipsIntraHora
    );
    return (brilloLectura.tipsColaG?.length || 0) + flaca.length > 0;
  }, [brilloLectura]);

  const ecoLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildEcoLectura({
      tiros: tirosHoraActual,
      minuto: minutoScore,
      tag: tagHora,
      lineas: lineasTips,
    });
  }, [
    liveActivo,
    tagHora,
    minutoScore,
    tirosKey,
    lineasTipsFp,
  ]);

  const calendarioLectura = useMemo(
    () =>
      buildCalendarioLectura({
        reloj: ahora,
        tagHora,
        ecoLectura,
        brilloLectura,
      }),
    [ahora.tag, tagHora, ecoLectura, brilloLectura]
  );

  const tipsFp = useMemo(() => {
    if (!liveActivo) return "";
    const flaca = tipsFlacaActivos(
      brilloLectura?.tipsOpacidad,
      brilloLectura?.tipsIntraHora
    );
    const colaIds = (brilloLectura?.tipsColaG || [])
      .map((t) => `${t.id}:${t.alerta ? 1 : 0}`)
      .join(",");
    const flacaIds = flaca
      .map((t) => `${t.id}:${t.alerta ? 1 : 0}`)
      .join(",");
    return [
      brilloLectura?.fingerprint || "",
      ecoLectura?.fingerprint || "",
      colaIds,
      flacaIds,
    ].join("|");
  }, [liveActivo, brilloLectura, ecoLectura]);

  const tipsNuevo = Boolean(tipsFp) && tipsFp !== tipsLeidoFp;

  useEffect(() => {
    if (!liveActivo) return;
    setRegistroBloques((prev) => {
      const { cerrados } = actualizarRegistroBloques(prev, {
        tiros: tirosHoraActual,
        minuto: minutoScore,
        tag: tagHora,
      });
      if (cerrados.length === prev.length) return prev;
      return cerrados;
    });
  }, [
    liveActivo,
    tagHora,
    minutoScore,
    tirosKey,
  ]);

  const supernovaMinuto = sosteniendoHora ? 59 : minutoScore;

  const supernovaLectura = useMemo(() => {
    if (!liveActivo) return null;
    const { enCurso } = actualizarRegistroBloques(registroBloques, {
      tiros: tirosHoraActual,
      minuto: supernovaMinuto,
      tag: tagHora,
    });
    const lectura = buildSupernovaLectura({
      tiros: tirosHoraActual,
      minuto: supernovaMinuto,
      tag: tagHora,
      registroBloques,
      lineas: lineasTips,
      horaCerrada: sosteniendoHora,
      brillo: brilloLectura,
      alertaPrev: {
        ...supernovaAlertaPrevRef.current,
        parpadeaba: supernovaParpadeabaRef.current,
      },
    });
    return { ...lectura, bloqueEnCurso: enCurso };
  }, [
    liveActivo,
    tagHora,
    supernovaMinuto,
    registroBloques,
    lineasTipsFp,
    brilloLectura?.fingerprint,
    tirosKey,
  ]);

  useEffect(() => {
    if (!supernovaLectura) return;
    if (supernovaLectura.parpadea) supernovaParpadeabaRef.current = true;
    if (supernovaLectura.alerta?.pasada) supernovaParpadeabaRef.current = false;
    supernovaAlertaPrevRef.current = supernovaLectura.alerta;
  }, [supernovaLectura?.fingerprint, supernovaLectura?.parpadea, supernovaLectura?.alerta?.pasada]);

  const supernovaVisible =
    liveActivo && brilloLectura;

  useEffect(() => {
    if (brilloAbierto && brilloLectura?.fingerprint) {
      setBrilloLeidoFp(brilloLectura.fingerprint);
    }
  }, [brilloAbierto, brilloLectura?.fingerprint]);

  useEffect(() => {
    if (tipsAbierto && tipsFp) {
      setTipsLeidoFp(tipsFp);
    }
  }, [tipsAbierto, tipsFp]);

  const verdesKey = useMemo(
    () => verdesHoraActual.map((v) => v.minuto).join(","),
    [verdesHoraActual]
  );

  const goHitsSet = useMemo(
    () => new Set(liveActivo ? minutosGoAcierto(tirosHoraActual) : []),
    [liveActivo, tirosKey]
  );

  const ultimoMinutoCierre = useMemo(() => {
    const manual =
      pendiente?.ultimoMinuto ?? (manualTodos.at(-1)?.m1 ?? null);
    const real = tirosRealesHoraActual.at(-1)?.m1 ?? null;
    return manual ?? real;
  }, [pendiente?.ultimoMinuto, manualTodos, tirosRealesHoraActual]);

  const tipProx = useMemo(() => {
    if (!showSiguienteG || !liveActivo) return null;
    const luces = verdesHoraActual.map((v) => v.minuto);
    const listas =
      mesasChips?.length > 0
        ? mesasChips
        : chips?.length
          ? [chips]
          : [];
    const minutoAhora = minutoLivePlayhead({
      reloj: ahora,
      tiroEnCurso,
      ultimoCierre: ultimoMinutoCierre,
    });
    return tipSiguienteG({
      mesasChips: listas,
      luces,
      minutoAhora,
    });
  }, [
    showSiguienteG,
    liveActivo,
    mesasChips,
    chips,
    verdesKey,
    ahora.minuto,
    tiroEnCurso,
    ultimoMinutoCierre,
  ]);

  /** Alarma MP3: solo zona Pool-7 (tip ±1) con tiro en curso (ignora reloj PC). */
  const alarmaPool7 = useMemo(() => {
    if (!liveActivo) return false;
    return enZonaPool7(tiroEnCurso, tipProx?.tip);
  }, [liveActivo, tiroEnCurso, tipProx?.tip]);

  /** Apostador: silla de minuto (SOLO_ZONA). No es color. No remonta Next 3. */
  const apostadorDiag = useMemo(() => {
    if (!liveActivo) return null;
    return diagnosticarApostador({
      tiros: tirosHoraActual,
      tiroEnCurso,
      tipProx,
    });
  }, [liveActivo, tirosKey, tiroEnCurso, tipProx]);

  const gestoLectura = useMemo(() => {
    if (!liveActivo) return null;
    return buildGestoEsperado({ tiros: tirosHoraActual });
  }, [liveActivo, tirosKey]);

  const lamparaLectura = useMemo(() => {
    if (!liveActivo || !showSiguienteG) return null;
    return buildLamparaLectura({ tiros: tirosHoraActual, tipProx });
  }, [liveActivo, showSiguienteG, tirosKey, tipProx]);

  /** Diagnóstico de Fuerza: señal para entrar / apostar fuerte (confluencia Go+P7, tren, estirada o costura). */
  const fuerzaLectura = useMemo(() => {
    if (!liveActivo) return null;
    return diagnosticarFuerza({
      goDiag: diagnosticarGo(tirosHoraActual),
      zonaP7: alarmaPool7,
      tipP7: tipProx?.tip,
      cierre: cierreLectura,
      enCurso: tiroEnCurso,
    });
  }, [
    liveActivo,
    tirosKey,
    alarmaPool7,
    tipProx?.tip,
    cierreLectura,
    tiroEnCurso,
  ]);

  /** Todos los tips resueltos (exact/±1/miss) → cronista. */
  const tipResoluciones = useMemo(() => {
    if (!showSiguienteG || !liveActivo) return [];
    const luces = verdesHoraActual.map((v) => v.minuto);
    const listas =
      mesasChips?.length > 0
        ? mesasChips
        : chips?.length
          ? [chips]
          : [];
    if (luces.length < 1) return [];
    const out = [];
    for (let i = 0; i < luces.length; i += 1) {
      const prev = tipSiguienteG({
        mesasChips: listas,
        luces: luces.slice(0, i),
        minutoAhora: null,
      });
      const real = luces[i];
      const delta = prev.tip == null ? null : prev.tip - real;
      out.push({
        tip: prev.tip,
        real,
        delta,
        paso: i + 1,
        why: prev.why || "",
        key: `${tagHora}:${i + 1}:${real}`,
      });
    }
    return out;
  }, [
    showSiguienteG,
    liveActivo,
    mesasChips,
    chips,
    tagHora,
    verdesKey,
  ]);

  const tipResolucionesKey = tipResoluciones.map((h) => h.key).join("|");

  const costuraH15 = useMemo(() => {
    if (!liveActivo || !tagHora) return null;
    return costuraH15Info(tagHora, extraLineas);
  }, [liveActivo, tagHora, extraLineasFp]);

  // Persistencia cronista: solo tips nuevos (idempotente en servidor).
  useEffect(() => {
    if (!showSiguienteG || !liveActivo || !tipResoluciones.length) return;
    let cancel = false;
    (async () => {
      for (const h of tipResoluciones) {
        if (cancel || cronistaEnviado.current.has(h.key)) continue;
        try {
          const r = await fetch("/api/tips/cronista", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tag: tagHora,
              paso: h.paso,
              tip: h.tip,
              luz: h.real,
              why: h.why,
              algo: "LC-01",
            }),
          });
          if (!r.ok) continue;
          const j = await r.json().catch(() => ({}));
          if (j.ok) cronistaEnviado.current.add(h.key);
        } catch (_) {
          // silencioso: el próximo tip nuevo reintenta
        }
      }
    })();
    return () => {
      cancel = true;
    };
  }, [showSiguienteG, liveActivo, tagHora, tipResolucionesKey]);

  // Cada G nueva reabre el detalle solo, aunque el usuario lo haya colapsado antes.
  useEffect(() => {
    if (verdesHoraActual.length > 0) setExpandido(true);
  }, [verdesHoraActual.length]);

  const liveSyncKey = useMemo(() => {
    const confirmadoManual =
      liveActivo && etapa >= 1 ? ETAPAS[Math.min(etapa, 3) - 1].b : -1;
    const confirmadoReal =
      liveActivo && tirosRealesHoraActual.length
        ? tirosRealesHoraActual[tirosRealesHoraActual.length - 1].m0
        : -1;
    const ultimoMinutoManual =
      pendiente?.ultimoMinuto ?? (manualTodos.at(-1)?.m1 ?? null);
    const ultimoMinutoReal = tirosRealesHoraActual.at(-1)?.m1 ?? null;
    return [
      tagHora,
      tagReloj,
      sosteniendoHora ? 1 : 0,
      fueraReloj ? 1 : 0,
      liveActivo ? 1 : 0,
      tirosKey,
      minutoScore,
      tiroEnCurso || "",
      tipProx?.estado,
      tipProx?.label,
      apostadorDiag?.estado,
      apostadorDiag?.mEst,
      cierreLectura?.fingerprint,
      bloquePerfilLectura?.fingerprint,
      olaPostSnLectura?.fingerprint,
      brilloLectura?.fingerprint,
      ecoLectura?.fingerprint,
      costuraH15?.pill,
      fuerzaLectura?.tipo,
      fuerzaLectura?.activo ? 1 : 0,
      gestoLectura?.fingerprint,
      lamparaLectura?.fingerprint,
      disponible ? 1 : 0,
      capturaViva ? 1 : 0,
      horaViva,
      etapa,
      Math.max(confirmadoManual, confirmadoReal),
      ultimoMinutoManual ?? ultimoMinutoReal ?? "",
      ahora.minuto,
    ].join("|");
  }, [
    tagHora,
    tagReloj,
    sosteniendoHora,
    fueraReloj,
    liveActivo,
    tirosKey,
    minutoScore,
    tiroEnCurso,
    tipProx,
    apostadorDiag?.estado,
    apostadorDiag?.mEst,
    cierreLectura?.fingerprint,
    bloquePerfilLectura?.fingerprint,
    olaPostSnLectura?.fingerprint,
    brilloLectura?.fingerprint,
    ecoLectura?.fingerprint,
    costuraH15?.pill,
    fuerzaLectura?.tipo,
    gestoLectura?.fingerprint,
    lamparaLectura?.fingerprint,
    disponible,
    capturaViva,
    horaViva,
    etapa,
    pendiente?.ultimoMinuto,
    manualTodos,
    tirosRealesHoraActual,
    ahora.minuto,
  ]);

  useEffect(() => {
    const confirmadoManual =
      liveActivo && etapa >= 1 ? ETAPAS[Math.min(etapa, 3) - 1].b : -1;
    const confirmadoReal =
      liveActivo && tirosRealesHoraActual.length
        ? tirosRealesHoraActual[tirosRealesHoraActual.length - 1].m0
        : -1;
    const ultimoMinutoManual =
      pendiente?.ultimoMinuto ?? (manualTodos.at(-1)?.m1 ?? null);
    const ultimoMinutoReal = tirosRealesHoraActual.at(-1)?.m1 ?? null;
    onAvance({
      tag: tagHora,
      tagReloj,
      sosteniendoHora,
      luces: liveActivo ? lucesDe(tirosHoraActual) : [],
      verdes: liveActivo ? verdesHoraActual : [],
      totalG: liveActivo ? verdesHoraActual.length : null,
      cierre: liveActivo ? cierreLectura : null,
      bloquePerfil: liveActivo ? bloquePerfilLectura : null,
      olaPostSn: liveActivo ? olaPostSnLectura : null,
      brillo: liveActivo ? brilloLectura : null,
      eco:
        liveActivo && ecoLectura
          ? {
              pill: ecoLectura.pill,
              lineas: ecoLectura.lineas,
              tone: ecoLectura.tone,
              fingerprint: ecoLectura.fingerprint,
            }
          : null,
      ultimoMinuto: liveActivo
        ? ultimoMinutoManual ?? ultimoMinutoReal
        : null,
      cerrado: false,
      reloj: liveActivo ? ahora : null,
      fuera: fueraReloj,
      horaViva: horaViva || "",
      confirmadoHasta: Math.max(confirmadoManual, confirmadoReal),
      habilitado: disponible || capturaViva,
      extraccionPausada,
      enCurso: liveActivo ? tiroEnCurso : null,
      goSequia: liveActivo ? esGoSequia(tirosHoraActual) : null,
      goDiag: liveActivo ? diagnosticarGo(tirosHoraActual) : null,
      apostador: liveActivo ? apostadorDiag : null,
      goHits: liveActivo ? minutosGoAcierto(tirosHoraActual) : [],
      fuerza: liveActivo ? fuerzaLectura : null,
      tipProx:
        showSiguienteG && liveActivo && tipProx ? tipProx : null,
      gesto: liveActivo ? gestoLectura : null,
      lampara: liveActivo ? lamparaLectura : null,
      costuraH15: liveActivo ? costuraH15 : null,
    });
  }, [liveSyncKey, onAvance]);

  function analizar() {
    setErr("");
    const r = analizarEtapa({
      texto,
      tagHora,
      etapa,
      locked,
      minutoAhora: ahora.minuto,
    });
    if (!r.ok) {
      setPendiente(null);
      setErr(r.error);
      return;
    }
    setPendiente(r);
  }

  function confirmar() {
    if (!pendiente) return;
    setLocked(pendiente.todos);
    setPendiente(null);
    setTexto("");
    setErr("");
    setEtapa((e) => e + 1);
  }

  function rectificar() {
    setPendiente(null);
    setErr("");
  }

  function reingresar() {
    setPendiente(null);
    setTexto("");
    setErr("");
  }

  const cajaOn = disponible && etapa < 3 && !pendiente;

  useEffect(() => {
    onCajaOnChange?.(cajaOn);
  }, [cajaOn, onCajaOnChange]);

  // Texto traído desde "Cargar live" en la pestaña Extracción.
  useEffect(() => {
    if (modalAbierto && textoInicial) {
      setTexto(textoInicial);
      setPendiente(null);
      setErr("");
    }
  }, [modalAbierto, textoInicial]);

  return (
    <section
      className={`live-avance${
        disponible ? "" : estado.razon === "espera" ? " espera" : " fuera"
      }`}
    >
      <header className="live-top">
        <div
          className={`live-top-main${
            expandido ? " expandido" : ""
          }${verdesHoraActual.length ? " expandible" : ""}`}
          role={verdesHoraActual.length ? "button" : undefined}
          tabIndex={verdesHoraActual.length ? 0 : undefined}
          aria-expanded={verdesHoraActual.length ? expandido : undefined}
          onClick={
            verdesHoraActual.length
              ? () => setExpandido((v) => !v)
              : undefined
          }
          onKeyDown={
            verdesHoraActual.length
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setExpandido((v) => !v);
                  }
                }
              : undefined
          }
        >
          <span className={`live-status${extraccionPausada ? " pausado" : ""}`}>
            <i
              className={`live-dot${
                extraccionPausada
                  ? " pausado"
                  : disponible || capturaViva
                    ? " on"
                    : ""
              }`}
            />
            {extraccionPausada
              ? "Pausado"
              : cabeceraOnline
                ? "Online"
                : "Offline"}
          </span>
          <span
            className="live-alarma-slot"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <AlarmaGoBtn
              alarmaActiva={alarmaPool7}
              enCurso={liveActivo ? tiroEnCurso || "" : ""}
            />
          </span>
          {liveActivo ? (
            <span
              className="live-fuerza-slot"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <FuerzaBtn lectura={fuerzaLectura} />
            </span>
          ) : null}

          <LiveRelojTick className="live-reloj" />

          {supernovaVisible && supernovaLectura ? (
            <button
              type="button"
              className={`live-header-sn-btn${
                supernovaLectura.parpadea ? " blink blink-fuerte" : ""
              }${supernovaAbierto ? " activo" : ""} tono-${supernovaLectura.tone || "reposo"}`}
              title={supernovaTooltipTitle(supernovaLectura)}
              aria-label="Supernova — alerta de luz excepcional"
              onClick={(e) => {
                e.stopPropagation();
                setSupernovaAbierto(true);
              }}
            >
              <IconSupernova />
            </button>
          ) : null}

          {brilloTag ? (
            <button
              type="button"
              className={`live-brillo-tag tono-${brilloLectura?.tone || "mute"}${
                brilloAbierto ? " activo" : ""
              }`}
              title={brilloTooltipTitle(brilloLectura, {
                nuevo: brilloNuevo,
              })}
              aria-label={`Brillo · ${brilloTag}`}
              onClick={(e) => {
                e.stopPropagation();
                setBrilloAbierto(true);
                if (brilloLectura?.fingerprint) {
                  setBrilloLeidoFp(brilloLectura.fingerprint);
                }
              }}
            >
              <IconBrillo
                className={`live-brillo-tag-icon${
                  brilloNuevo ? " blink" : ""
                }`}
              />
              <span>{brilloTag}</span>
            </button>
          ) : null}

          <button
            type="button"
            className={`live-calendario-tag tono-${calendarioLectura?.tone || "mute"}${
              calendarioAbierto ? " activo" : ""
            }${calendarioLectura?.celda ? " con-celda" : ""}`}
            title={calendarioTooltipTitle(calendarioLectura)}
            aria-label={`Calendario · ${calendarioLectura?.pill || "INFO"}`}
            onClick={(e) => {
              e.stopPropagation();
              setCalendarioAbierto(true);
            }}
          >
            <IconCalendario className="live-calendario-tag-icon" />
            {calendarioLectura?.pill && calendarioLectura.pill !== "Cal" ? (
              <span>{calendarioLectura.pill}</span>
            ) : null}
          </button>

          <button
            type="button"
            className={`live-records-tag${recordsAbierto ? " activo" : ""}`}
            title="Records — catálogo de bonos G1–G4"
            aria-label="Records"
            onClick={(e) => {
              e.stopPropagation();
              setRecordsAbierto(true);
            }}
          >
            <IconRecords className="live-records-tag-icon" />
          </button>

          <div className="live-g-tips">
            {liveActivo ? (
              <span
                className="live-total-g"
                title={`${verdesHoraActual.length} luces G en la hora`}
                aria-label={`${verdesHoraActual.length} luces G en la hora`}
              >
                {verdesHoraActual.length}
              </span>
            ) : null}
            <button
              type="button"
              className={`live-stats-btn tips-hora-btn${
                tipsNuevo ? " tips-alerta blink" : ""
              }${tipsLabHay || ecoLectura ? " tips-vivo" : ""}`}
              title={
                tipsNuevo
                  ? "Tips de la hora — hay novedad"
                  : tipsLabHay
                    ? "Tips de la hora — lab + mesa"
                    : "Tips de la hora"
              }
              aria-label="Tips de la hora"
              onClick={(e) => {
                e.stopPropagation();
                if (tipsFp) setTipsLeidoFp(tipsFp);
                onTips?.();
              }}
            >
              <IconTip />
            </button>
          </div>

          {colaEnHeader ? (
            <button
              type="button"
              className={`live-cola-tag${
                colaAlerta ? " alerta" : ""
              }${brilloLectura?.tipsColaG?.some((t) => t.id === "cola-confirmada") ? " confirmada" : ""}`}
              title="Cola G — abrir lectura"
              aria-label={`${colaTag} — abrir lectura`}
              onClick={(e) => {
                e.stopPropagation();
                setColaAbierto(true);
              }}
            >
              {colaTag}
            </button>
          ) : null}
        </div>
      </header>
      <BrilloModal
        abierto={brilloAbierto}
        lectura={brilloLectura}
        onCerrar={() => {
          setBrilloAbierto(false);
          if (brilloLectura?.fingerprint) {
            setBrilloLeidoFp(brilloLectura.fingerprint);
          }
        }}
      />
      <CalendarioModal
        abierto={calendarioAbierto}
        lectura={calendarioLectura}
        onCerrar={() => setCalendarioAbierto(false)}
      />
      <RecordsModal
        abierto={recordsAbierto}
        onCerrar={() => setRecordsAbierto(false)}
      />
      <SupernovaModal
        abierto={supernovaAbierto}
        lectura={supernovaLectura}
        onCerrar={() => setSupernovaAbierto(false)}
      />
      <ColaModal
        abierto={colaAbierto}
        lectura={colaLectura}
        onCerrar={() => setColaAbierto(false)}
      />
      {expandido && verdesHoraActual.length ? (
        <div className="live-verdes-strip">
          <div className="verdes-lista">
            {verdesHoraActual.map((v, i) => {
              const acerto = Boolean(cobraFicha(v.minuto, chips).length);
              const goHit = goHitsSet.has(v.minuto);
              return (
                <span
                  key={`${v.minuto}-${i}`}
                  className={`verde-item${acerto ? " acerto" : ""}${
                    goHit ? " go-hit" : ""
                  }`}
                >
                  <span className="verde-min">{pad(v.minuto)}:</span>
                  <b className="verde-g">G{v.tipo ?? ""}</b>
                  {v.vecino != null ? (
                    <span className="verde-x">{v.vecino}x</span>
                  ) : null}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}

      {modalAbierto ? (
        <div
          className="modal-back"
          onClick={() => setModalAbierto(false)}
          role="presentation"
        >
          <div
            className="modal modal-live"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Cargar resultados en vivo</h2>
            {disponible ? (
              <p className="live-estado">
                En curso · listo para recibir {tagHora} · minuto{" "}
                {pad(ahora.minuto)} · {andenFrase(ahora.minuto)} (
                {andenRango(ahora.minuto)})
                {ultimaIngerida
                  ? ` · última hora ingerida ${ultimaIngerida}`
                  : ""}
              </p>
            ) : estado.razon === "ya" ? (
              <p className="live-espera">
                En espera. {tagHora} ya está en la cinta.
                {ultimaIngerida
                  ? ` Última hora ingerida ${ultimaIngerida}.`
                  : ""}
              </p>
            ) : (
              <p className="live-espera">
                Agregá las horas en vivo.
                {ultimaIngerida
                  ? ` Última hora ingerida ${ultimaIngerida}.`
                  : ""}
              </p>
            )}

            {disponible && locked.length ? (
              <pre className="live-lock">
                {`${tagHora}\n${locked.map((t) => t.cruda).join("\n")}`}
              </pre>
            ) : null}

            {disponible && meta && etapa < 3 ? (
              <p className="hint">
                {pendiente
                  ? `Revisá ${meta.rango}: ${pendiente.nNuevos} tiro${
                      pendiente.nNuevos === 1 ? "" : "s"
                    }. ¿Son esos mismos?`
                  : `Ahora van ${meta.rango} (${meta.nombre}). La hora se llena sola: no pegues otra.`}
              </p>
            ) : null}

            {disponible && etapa >= 3 ? (
              <p className="ok">
                {tagHora} está completa en live. Cerrala en Agregar a la cinta.
              </p>
            ) : null}

            <div className="live-fila">
              <textarea
                className="live-box"
                rows={3}
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                placeholder={
                  meta ? `${tagHora}\nMM:SS-MM:SS R\nMM:SS-MM:SS G2 30` : ""
                }
                spellCheck={false}
                aria-label="tiros de la hora en vivo"
              />
              {pendiente ? (
                <div className="live-acciones">
                  <button type="button" onClick={confirmar}>
                    Confirmar {meta?.rango}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={rectificar}
                  >
                    Rectificar
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={reingresar}
                  >
                    Volver a ingresar
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="live-cargar"
                  disabled={!texto.trim()}
                  onClick={analizar}
                >
                  cargar live
                </button>
              )}
            </div>
            {err ? <p className="err">{err}</p> : null}
            <div className="row">
              <button
                type="button"
                className="ghost"
                onClick={() => setModalAbierto(false)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
