import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  loadAlarmaGoPrefs,
  playAlarmaGo,
  saveAlarmaGoPrefs,
  setAlarmaGoEnabled,
  stopAlarmaGo,
} from "./alarmaGo.js";

function IconAlarma({ muted = false, className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <path
        d="M6.5 10.5a5.5 5.5 0 0 1 11 0v3.2l1.4 2.1H5.1l1.4-2.1v-3.2z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path
        d="M10 18.2a2 2 0 0 0 4 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      {muted ? (
        <line
          x1="4"
          y1="4"
          x2="20"
          y2="20"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}

/**
 * Alarma Pool-7 — suena en zona tip ±1 y en cada tiro nuevo mientras siga.
 * (MP3 desde 3:45 · 38 s · fade-out).
 * Popover en portal (fixed) para no quedar recortado por overflow de la barra.
 */
export function AlarmaGoBtn({
  alarmaActiva = false,
  enCurso = "",
  className = "",
}) {
  const [prefs, setPrefs] = useState(() => {
    const p = loadAlarmaGoPrefs();
    setAlarmaGoEnabled(p.on === true);
    if (!p.on) stopAlarmaGo();
    return p;
  });
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const lastPlayedKey = useRef("");
  const wrapRef = useRef(null);
  const btnRef = useRef(null);
  const popRef = useRef(null);

  function aplicarPrefs(next) {
    setAlarmaGoEnabled(next.on === true);
    saveAlarmaGoPrefs(next);
    setPrefs(next);
    if (!next.on) {
      stopAlarmaGo();
      lastPlayedKey.current = "";
    }
  }

  useEffect(() => {
    const curso = String(enCurso || "");
    if (!prefs.on || !alarmaActiva || !curso) {
      stopAlarmaGo();
      lastPlayedKey.current = "";
      return undefined;
    }

    const key = `p7|${curso}`;
    if (lastPlayedKey.current === key) return undefined;
    lastPlayedKey.current = key;
    playAlarmaGo(prefs.vol);

    return () => {
      stopAlarmaGo();
      if (lastPlayedKey.current === key) lastPlayedKey.current = "";
    };
  }, [alarmaActiva, enCurso, prefs.on, prefs.vol]);

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return undefined;
    function place() {
      const r = btnRef.current.getBoundingClientRect();
      const width = 160;
      const left = Math.min(
        Math.max(8, r.left),
        window.innerWidth - width - 8
      );
      setPos({ top: r.bottom + 6, left });
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    function onDoc(e) {
      const t = e.target;
      if (wrapRef.current?.contains(t)) return;
      if (popRef.current?.contains(t)) return;
      setOpen(false);
    }
    // click (no pointerdown): evita cerrar en el mismo gesto que abre
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [open]);

  useEffect(() => () => stopAlarmaGo(), []);

  const muted = !prefs.on || prefs.vol <= 0.01;

  function stopBubble(e) {
    e.stopPropagation();
  }

  const pop =
    open && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={popRef}
            className="v2-alarma-pop v2-alarma-pop-portal"
            role="dialog"
            aria-label="Alarma Pool 7"
            style={{ top: pos.top, left: pos.left }}
            onClick={stopBubble}
            onPointerDown={stopBubble}
          >
            <button
              type="button"
              className={`v2-alarma-toggle${prefs.on ? " on" : ""}`}
              onClick={(e) => {
                stopBubble(e);
                aplicarPrefs({ ...prefs, on: !prefs.on });
              }}
            >
              {prefs.on ? "Activa" : "Apagada"}
            </button>
            <label className="v2-alarma-vol">
              <span>Vol</span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(prefs.vol * 100)}
                disabled={!prefs.on}
                onClick={stopBubble}
                onPointerDown={stopBubble}
                onChange={(e) => {
                  const vol = Number(e.target.value) / 100;
                  aplicarPrefs({ ...prefs, vol });
                }}
              />
            </label>
          </div>,
          document.body
        )
      : null;

  return (
    <div
      className={`v2-alarma-wrap${className ? ` ${className}` : ""}`}
      ref={wrapRef}
      onClick={stopBubble}
      onPointerDown={stopBubble}
    >
      <button
        ref={btnRef}
        type="button"
        className={`v2-alarma-btn${prefs.on ? " on" : " off"}${
          alarmaActiva && prefs.on ? " armed" : ""
        }`}
        title={
          prefs.on
            ? `Alarma Pool-7 ON · clic apaga · vol ${Math.round(prefs.vol * 100)}%`
            : "Alarma Pool-7 OFF · clic enciende · clic derecho: volumen"
        }
        aria-label={prefs.on ? "Alarma Pool 7 activa" : "Alarma Pool 7 desactivada"}
        aria-expanded={open}
        onClick={(e) => {
          stopBubble(e);
          aplicarPrefs({ ...prefs, on: !prefs.on });
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          stopBubble(e);
          setOpen((o) => !o);
        }}
      >
        <IconAlarma muted={muted} />
      </button>
      {pop}
    </div>
  );
}
