import { bloquePerfilTooltip } from "./bloquePerfilInfo.js";

/** Icono silueta de perfil (bloques 00–19 / 20–39). */
export function IconBloquePerfil({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="8"
        r="3.25"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path
        d="M6 20c0-3.2 2.7-5.5 6-5.5s6 2.3 6 5.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function BloquePerfilBtn({ lectura, className = "" }) {
  if (!lectura?.ok) return null;
  return (
    <button
      type="button"
      className={`live-perfil-btn v2-perfil-btn${
        lectura.parpadea ? " blink" : " fijo"
      } fase-${lectura.fase || "bloque1"}${className ? ` ${className}` : ""}`}
      title={bloquePerfilTooltip(lectura)}
      aria-label={
        lectura.fase === "bloque2"
          ? `Perfil de hora — ${lectura.titulo}`
          : `Perfil de hora — bloque 00–19 · ${lectura.titulo}`
      }
    >
      <IconBloquePerfil />
    </button>
  );
}
