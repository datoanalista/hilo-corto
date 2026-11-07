/**
 * Cierre abierto INFO — lab-alerta-costura 2026-08-31.
 * Solo señal hacia h+1 (no cola 58-59 sola en hN):
 *   · @55-59 hN: G en 50-54 + apertura 0-9 (olor predictivo)
 *   · @0-3 hN+1: G en apertura = cruce confirmado
 * Sin icono = cierre cerrado. No boleto.
 */
import { perfilAperturaHora } from "./intraHoraInfo.js";

const ALERT_MIN = 55;
const COLA_MIN = 50;
const COLA_MAX = 54;
const SEGMENTO_CIERRE_MAX = 59;
const SEGMENTO_APERTURA_MAX = 3;

function lumenOf(t) {
  if (t?.lumen != null && !Number.isNaN(Number(t.lumen))) return Number(t.lumen);
  if (t?.vecino != null && !Number.isNaN(Number(t.vecino))) return Number(t.vecino);
  return null;
}

function gsDeTiros(tiros = [], maxMin = null) {
  let gs = (tiros || []).filter(
    (t) => t && String(t.color || "").toUpperCase().startsWith("G") && lumenOf(t) != null
  );
  if (maxMin != null) gs = gs.filter((t) => t.m0 <= maxMin);
  return gs;
}

/**
 * @returns {null | { ok, estado, parpadea, titulo, lineas, fingerprint }}
 */
export function buildCierreAbierto({ tiros = [], minuto = 0 } = {}) {
  const T = Math.min(59, Math.max(0, Number(minuto) || 0));
  const gs = gsDeTiros(tiros, T);
  const gEnCola5054 = gs.some(
    (g) => g.m0 >= COLA_MIN && g.m0 <= Math.min(COLA_MAX, T)
  );
  const gAperturaH1 = T <= SEGMENTO_APERTURA_MAX && gs.some((g) => g.m0 <= 3);

  // h+1: G en 0-3 = actividad cruzó (cola del pulso anterior u otra)
  if (gAperturaH1) {
    return {
      ok: true,
      estado: "confirmado",
      parpadea: T <= SEGMENTO_APERTURA_MAX,
      titulo: "Cierre abierto",
      lineas: [
        "Actividad en la hora nueva (min 0-3).",
        "Señal de cruce desde la hora anterior.",
        "INFO — no es boleto ni minuto exacto.",
      ],
      fingerprint: `h1|${T}|${gs.filter((g) => g.m0 <= 3).length}`,
    };
  }

  // hN @55-59: olor solo si hay cola 50-54 y la hora abrió (predicción h+1)
  if (T >= ALERT_MIN && T <= SEGMENTO_CIERRE_MAX) {
    const perfil = perfilAperturaHora({ tiros, T, enCurso: true });
    if (gEnCola5054 && !perfil.sinEarly) {
      return {
        ok: true,
        estado: "olor",
        parpadea: true,
        titulo: "Cierre abierto",
        lineas: [
          "Luz en cola (50-54) y la hora abrió temprano.",
          "Olor de actividad hacia la hora siguiente.",
          "INFO — no es boleto ni minuto exacto.",
        ],
        fingerprint: `olor|${T}|1|${perfil.sinEarly ? 0 : 1}`,
      };
    }
  }

  return null;
}

export function cierreAbiertoTooltip(lectura) {
  if (!lectura?.ok) return "";
  return [lectura.titulo, ...(lectura.lineas || [])].join("\n");
}
