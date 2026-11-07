import { memo } from "react";

/** Icono rayo de fuerza / potencia. */
export function IconFuerza({ className = "" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="14"
      height="14"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth="0.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

export function FuerzaBtn({ lectura, className = "" }) {
  const activo = Boolean(lectura?.activo);
  const tipo = lectura?.tipo || "standby";

  return (
    <button
      type="button"
      className={`v2-fuerza-btn${activo ? " activo blink" : " standby"} tipo-${tipo}${
        className ? ` ${className}` : ""
      }`}
      title={lectura?.tooltip || "Fuerza"}
      aria-label={lectura?.motivo || "Fuerza"}
    >
      <IconFuerza />
    </button>
  );
}

export default memo(FuerzaBtn);
