import { memo, useEffect, useMemo, useState } from "react";
import {
  avisoCerca,
  estadoFicha,
  pad,
  yaPaso,
} from "./mesa.js";
import { relojSistema } from "./live.js";
import {
  bloqueDeMinuto,
  chipNearCercaWindow,
  cortesBloques,
  minutoAPct,
} from "./v2Layout.js";

function estadoChip(m, tiros, oficiales, marcas, T) {
  const tiro =
    (tiros || []).find((t) => t.minuto === m) || {
      minuto: m,
      flag: "TIBIO",
    };
  return estadoFicha(m, { T, oficiales, tiro, marca: marcas?.[m] });
}

function marcaEtiqueta(m, est) {
  const n = pad(m);
  if (est.clave !== "cobro" || est.etiqueta === "exacto") return n;
  const tok = String(est.etiqueta || "")
    .trim()
    .split("\n")[0]
    .trim();
  if (tok.startsWith("-")) return `-${n}`;
  if (tok.startsWith("+")) return `${n}+`;
  return n;
}

const V2Mark = memo(function V2Mark({
  m,
  T,
  bloqueado,
  tiros,
  oficiales,
  marcas,
  enfocado,
  atenuado,
  esDiff,
  esHuerfanoP8,
  enExpandido,
  left,
  verdesPorMinuto,
  onShowTip,
  onHideTip,
}) {
  const needCercaTick = useMemo(
    () => !bloqueado && chipNearCercaWindow(m, T) && !yaPaso(m, T),
    [bloqueado, m, T]
  );
  const [segundo, setSegundo] = useState(0);

  useEffect(() => {
    if (!needCercaTick) return undefined;
    setSegundo(relojSistema().segundo);
    const id = setInterval(() => {
      setSegundo(relojSistema().segundo);
    }, 5000);
    return () => clearInterval(id);
  }, [needCercaTick, T, m]);

  const est = estadoChip(m, tiros, oficiales, marcas, T);
  const acerto = est.clave === "cobro";
  const exacto = acerto && est.etiqueta === "exacto";
  const vecino = acerto && !exacto;
  const fallo = est.etiqueta === "tiro fallido";
  const cerca =
    !bloqueado && avisoCerca(m, T, needCercaTick ? segundo : 0);

  return (
    <button
      type="button"
      role="listitem"
      disabled={bloqueado}
      className={`v2-mark${exacto || vecino ? " ok" : ""}${
        exacto ? " exacto" : ""
      }${vecino ? " vecino" : ""}${fallo ? " fallo" : ""}${
        cerca ? " cerca" : ""
      }${esDiff ? " diff" : ""}${esHuerfanoP8 ? " orphan-p8" : ""}${
        enfocado ? " foco" : ""
      }${atenuado ? " dim" : ""}${enExpandido ? " wide" : " tight"}`}
      style={{ left }}
      aria-label={`Minuto ${pad(m)}${esHuerfanoP8 ? " · fuera RC" : ""}`}
      title={
        esHuerfanoP8
          ? "Pool 8 fijo · minuto fuera del set RC"
          : undefined
      }
      onMouseEnter={onShowTip}
      onMouseLeave={onHideTip}
      onFocus={onShowTip}
      onBlur={onHideTip}
      onClick={(e) => {
        e.preventDefault();
        if (bloqueado) return;
        onShowTip();
      }}
    >
      <span className="v2-mark-num">{marcaEtiqueta(m, est)}</span>
      {enfocado ? (
        <span className="v2-mark-tip" role="tooltip">
          {fallo ? (
            <span className="v2-mark-tip-fallo">Tiro fallido</span>
          ) : est.hits?.length ? (
            est.hits.map((g) => {
              const info = verdesPorMinuto.get(g);
              const gLabel = info?.tipo != null ? `G${info.tipo}` : "G";
              const res =
                info?.vecino != null && info.vecino !== ""
                  ? `${info.vecino}x`
                  : "";
              const tramo =
                info?.inicio && info?.fin
                  ? `${info.inicio}-${info.fin}`
                  : null;
              return (
                <span key={g} className="v2-mark-tip-g">
                  {tramo ? (
                    <span className="v2-mark-tip-tramo">{tramo}</span>
                  ) : (
                    <span className="v2-mark-tip-tramo">{pad(g)}</span>
                  )}
                  <span className="v2-mark-tip-res">
                    {gLabel}
                    {res ? ` ${res}` : ""}
                  </span>
                </span>
              );
            })
          ) : (
            <span className="v2-mark-tip-vacio">Sin resultado aún</span>
          )}
        </span>
      ) : null}
    </button>
  );
});

function V2PoolRowInner({
  f,
  T,
  bloqueado,
  oficiales,
  oficialChips,
  chipsLiveRcSet,
  pesos,
  bloqueExpandido,
  posMap,
  railBg,
  cortes,
  focoActivo,
  filaActiva,
  modoOrden,
  verdesPorMinuto,
  poolsExpandidos = false,
  onTogglePoolsExpand,
  onAbrirMesa,
  onFilaEnter,
  onFilaLeave,
  onShowTip,
  onHideTip,
}) {
  const activa = filaActiva === f.id;
  const valorTotal = f.liveSt.scoreLive;
  const metaTitle = `k${f.chips.length} · total ${valorTotal} (${f.liveSt.exacto}✓ + ${f.liveSt.vecino}±) · ${f.liveSt.fallo}×`;
  const tono =
    f.panel.inter2 || f.id === "inter2"
      ? "inter2"
      : f.panel.liveRc || f.id === "live-rc"
        ? "live-rc"
        : f.panel.pool9 || f.panel.classic || f.id === "pool-9"
          ? "classic"
          : f.panel.lc || f.id === "lc-01"
            ? "lc"
            : "pool";

  const hayCerca = useMemo(() => {
    if (bloqueado) return false;
    return f.chips.some(
      (m) => chipNearCercaWindow(m, T) && avisoCerca(m, T, 0)
    );
  }, [bloqueado, f.chips, T]);

  const esPool7 = f.id === "lc-01" || f.panel?.lc;

  return (
    <article
      className={`v2-row tono-${tono}${activa ? " activa" : ""}${
        hayCerca ? " hay-cerca" : ""
      }${esPool7 && poolsExpandidos ? " pools-open" : ""}`}
      title={metaTitle}
      onMouseEnter={() => onFilaEnter(f.id)}
      onMouseLeave={() => onFilaLeave(f.id)}
    >
      <div className="v2-head">
        {esPool7 && onTogglePoolsExpand ? (
          <button
            type="button"
            className="v2-name"
            onClick={onTogglePoolsExpand}
            title={
              poolsExpandidos
                ? "Clic: ocultar otros pools"
                : "Clic: mostrar todos los pools"
            }
            aria-expanded={poolsExpandidos}
            aria-label={
              poolsExpandidos
                ? `${f.etiqueta} · ocultar otros pools`
                : `${f.etiqueta} · mostrar todos los pools`
            }
          >
            {f.etiqueta}
          </button>
        ) : onAbrirMesa && !f.panel.lc && !f.panel.liveRc ? (
          <button
            type="button"
            className="v2-name"
            onClick={() => onAbrirMesa(f.id)}
            title={`Abrir ${f.etiqueta}`}
          >
            {f.etiqueta}
          </button>
        ) : (
          <strong className="v2-name static">{f.etiqueta}</strong>
        )}

        <span
          className="v2-kpi"
          title={`Total ${valorTotal} (${f.liveSt.exacto} G + ${f.liveSt.vecino} ±1)`}
        >
          {valorTotal}
        </span>
      </div>

      <div
        className={`v2-rail${bloqueado ? " off" : ""}`}
        style={{ "--v2-rail-bg": railBg }}
        role="list"
        aria-label={`Fichas ${f.etiqueta}`}
      >
        {cortes.slice(1).map((c) => (
          <i
            key={c}
            className="v2-rail-div"
            style={{ left: `${c}%` }}
            aria-hidden="true"
          />
        ))}

        {f.chips.length === 0 ? (
          <span className="v2-empty">sin fichas</span>
        ) : (
          f.chips.map((m) => {
            const enfocado = focoActivo?.id === f.id && focoActivo?.m === m;
            const atenuado = focoActivo != null && !enfocado;
            const esDiff =
              f.panel.beta && !f.panel.lc && !oficialChips.has(m);
            const esHuerfanoP8 =
              (f.id === "inter2" || f.panel.inter2) &&
              !chipsLiveRcSet.has(m);
            const left = `${posMap?.get(m) ?? minutoAPct(m, pesos)}%`;
            const enExpandido = bloqueDeMinuto(m) === bloqueExpandido;

            return (
              <V2Mark
                key={m}
                m={m}
                T={T}
                bloqueado={bloqueado}
                tiros={f.tiros}
                oficiales={oficiales}
                marcas={f.marcas}
                enfocado={enfocado}
                atenuado={atenuado}
                esDiff={esDiff}
                esHuerfanoP8={esHuerfanoP8}
                enExpandido={enExpandido}
                left={left}
                verdesPorMinuto={verdesPorMinuto}
                onShowTip={() => onShowTip(f.id, m)}
                onHideTip={() => onHideTip(f.id, m)}
              />
            );
          })
        )}
      </div>
    </article>
  );
}

function rowPropsEqual(prev, next) {
  if (prev.f !== next.f) return false;
  if (prev.T !== next.T) return false;
  if (prev.bloqueado !== next.bloqueado) return false;
  if (prev.oficiales !== next.oficiales) return false;
  if (prev.focoActivo !== next.focoActivo) return false;
  if (prev.filaActiva !== next.filaActiva) return false;
  if (prev.bloqueExpandido !== next.bloqueExpandido) return false;
  if (prev.railBg !== next.railBg) return false;
  if (prev.posMap !== next.posMap) return false;
  if (prev.pesos !== next.pesos) return false;
  if (prev.verdesPorMinuto !== next.verdesPorMinuto) return false;
  if (prev.oficialChips !== next.oficialChips) return false;
  if (prev.chipsLiveRcSet !== next.chipsLiveRcSet) return false;
  if (prev.poolsExpandidos !== next.poolsExpandidos) return false;
  return true;
}

const V2PoolRow = memo(V2PoolRowInner, rowPropsEqual);

export default V2PoolRow;
