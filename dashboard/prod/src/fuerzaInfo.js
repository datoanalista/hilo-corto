/**
 * Diagnóstico de Fuerza para señal de entrada / apuesta fuerte.
 *
 * Condiciones de Fuerza:
 * 1. Costura SEGURO (~94.8% histórico de G en tiro 1 de la hora).
 * 2. Confluencia Go! + Pool 7 (tiro en ventana caliente Y coincidiendo en minuto tip ±1).
 * 3. Go! ⚡ Tren (2+ G consecutivas pegadas, compuerta abierta al máximo).
 * 4. Go! ⏱ Estirada (bonus largo previo ≥100s, compuerta extendida).
 */

export function diagnosticarFuerza({
  goDiag = null,
  zonaP7 = false,
  tipP7 = null,
  cierre = null,
  enCurso = null,
} = {}) {
  // 1. Costura SEGURO
  if (cierre?.seguro || cierre?.estado === "seguro") {
    return {
      activo: true,
      tipo: "costura",
      nivel: "seguro",
      label: "Costura SEGURO",
      badge: "95%",
      motivo: "Costura SEGURO: cierre largo en hora previa. 94.8% histórico de G en este tiro.",
      tooltip: [
        "[⚡ FUERZA · Costura SEGURO (~95%)]",
        "• Condición: Cierre largo previo (≥70s)",
        "• Probabilidad: ~94.8% de G en tiro 1",
        "• Recomendación: Máxima fuerza de entrada",
      ].join("\n"),
    };
  }

  // 2. Confluencia Go! + Pool 7
  if (goDiag?.activo && zonaP7) {
    const tipTxt = tipP7 != null ? String(tipP7).padStart(2, "0") : "—";
    const sub = goDiag.subtitulo || goDiag.etiqueta || "Go!";
    return {
      activo: true,
      tipo: "confluencia",
      nivel: "maxima",
      label: "Go! + Pool 7",
      badge: "Confluencia",
      motivo: `Confluencia: ${sub} coincidiendo en zona tip Pool 7 (${tipTxt} ±1). Máxima precisión en banda.`,
      tooltip: [
        "[⚡ FUERZA · Confluencia Go! + Pool 7]",
        `• Estado Go: ${goDiag.etiqueta || "Go!"} (${sub})`,
        `• Zona Pool 7: Minuto ${tipTxt} ±1 (tiro en juego: ${enCurso || "—"})`,
        "• Puntería: Cruce de ventana caliente con minuto objetivo",
        "• Recomendación: Entrada fuerte recomendada",
      ].join("\n"),
    };
  }

  // 3. Tren activo (2+ G consecutivas)
  if (goDiag?.activo && goDiag?.tipo === "tren") {
    return {
      activo: true,
      tipo: "tren",
      nivel: "alta",
      label: "Tren ⚡",
      badge: `${goDiag.gConsecutivas || 2} G`,
      motivo: `Tren activo: ${goDiag.gConsecutivas || 2} G seguidas. Inercia: el pegado sí entra (excepción a la poda +1).`,
      tooltip: [
        `[⚡ FUERZA · Tren de Gs (${goDiag.gConsecutivas || 2} seguidas)]`,
        "• Diagnóstico: Inercia · el pegado sí entra",
        "• Excepción a la poda +1 (Go! alineado a Next 3)",
        "• Recomendación: Sí jugar este tiro",
      ].join("\n"),
    };
  }

  // 4. Compuerta estirada (durG >= 100s)
  if (goDiag?.activo && goDiag?.tipo === "estirada") {
    return {
      activo: true,
      tipo: "estirada",
      nivel: "alta",
      label: "Estirada ⏱",
      badge: `${goDiag.durG || "100+"}s`,
      motivo: `Estirada: bonus largo previo (${goDiag.durG || 100}s). Inercia: el pegado sí entra (excepción a la poda +1).`,
      tooltip: [
        `[⚡ FUERZA · Estirada (${goDiag.durG || 100}s)]`,
        "• Diagnóstico: Inercia · el pegado sí entra",
        "• Excepción a la poda +1 (Go! alineado a Next 3)",
        "• Recomendación: Sí jugar este tiro",
      ].join("\n"),
    };
  }

  // Standby (sin fuerza activa en este momento)
  return {
    activo: false,
    tipo: "standby",
    nivel: "neutral",
    label: "Fuerza",
    badge: "Standby",
    motivo: "En espera: se activa con Go! + Zona Pool 7, Tren de Gs o Costura SEGURO.",
    tooltip: [
      "[⚡ FUERZA · Standby]",
      "• Estado: Esperando condiciones de fuerza",
      "• Se activa cuando confluyen:",
      "  1. Go! + Zona Pool 7 (minuto objetivo)",
      "  2. Tren de Gs consecutivas",
      "  3. Compuerta estirada (bonus largo)",
      "  4. Costura SEGURO (~95%)",
    ].join("\n"),
  };
}
