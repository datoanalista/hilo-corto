import { cierreAbiertoTooltip } from "./cierreAbiertoInfo.js";

export function IconCierreAbierto({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <line
        x1="12"
        y1="5"
        x2="12"
        y2="19"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M5 12h4M15 12h4M7 10l-2 2 2 2M17 10l2 2-2 2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Icono cierre abierto — sin render = cierre cerrado. */
export function CierreAbiertoBtn({ lectura, className = "" }) {
  if (!lectura?.ok) return null;
  return (
    <button
      type="button"
      className={`live-cierre-btn v2-cierre-btn${
        lectura.parpadea ? " blink" : ""
      } estado-${lectura.estado || "olor"}${className ? ` ${className}` : ""}`}
      title={cierreAbiertoTooltip(lectura)}
      aria-label={lectura.titulo}
    >
      <IconCierreAbierto />
    </button>
  );
}
