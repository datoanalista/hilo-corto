import { olaPostSnTooltip } from "./olaPostSnInfo.js";

/** Icono ola — ondas (cola post-SN). */
export function IconOlaPostSn({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M3 14c2.5-3 4.5-3 7 0s4.5 3 7 0 4.5-3 7 0" />
      <path d="M3 18c2.5-3 4.5-3 7 0s4.5 3 7 0 4.5-3 7 0" opacity="0.65" />
    </svg>
  );
}

export default function OlaPostSnBtn({ lectura, className = "" }) {
  if (!lectura?.ok) return null;
  return (
    <button
      type="button"
      className={`v2-ola-post-sn-btn${
        lectura.parpadea ? " blink" : " fijo"
      } fase-${lectura.fase || "alerta"}${className ? ` ${className}` : ""}`}
      title={olaPostSnTooltip(lectura)}
      aria-label={
        lectura.ola
          ? `Ola post-SN confirmada al min ${lectura.ola.m0}`
          : `Olor de cola post-SN tras supernova min ${lectura.minSn}`
      }
    >
      <IconOlaPostSn />
    </button>
  );
}
