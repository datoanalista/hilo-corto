import { enZonaPool7 } from "./tipProxima.js";
import { detalleFormaG } from "./formaGInfo.js";

const MEDIA_ON = 68;
const MEDIA_OFF = 40;
const SUMA_COLA = 850;
const MINUTO_LATE = 40;

const PILLS_APAGADA = new Set([
  "muy apagado",
  "opaco",
  "sesgo opaco",
  "tendencia opaca",
]);

/** @returns {'OFF'|'ALERTA'|'ON'} */
export function evaluarInterruptor(live) {
  const det = detallePuertaA(live);
  return det.interruptor;
}

/** Estado de las 3 tarjetas (misma bandera global en ronda A). */
export function estadoTarjetas(live) {
  const det = detallePuertaA(live);
  return {
    global: det.estadoTarjeta,
    interruptor: det.interruptor,
    detalle: det,
  };
}

export function detallePuertaA(live) {
  const vacio = {
    interruptor: "OFF",
    estadoTarjeta: "ESPERANDO",
    puertaA: false,
    puertaAFase: null,
    formaG: null,
    formaGLabel: null,
    enZona: false,
    tip: null,
    motivos: ["Sin live activo"],
    checks: {},
  };

  if (!live?.habilitado) {
    return { ...vacio, motivos: ["Mesa no habilitada o sin sesión live"] };
  }

  const b = live.brillo;
  if (!b) {
    return { ...vacio, motivos: ["Esperando lectura de Brillo"] };
  }

  const T = live.reloj?.minuto ?? b.T ?? 0;
  const nG = b.nG ?? 0;
  const meanG = b.meanG;
  const acum = b.acum ?? 0;
  const tip = live.tipProx?.tip ?? null;
  const enZona = enZonaPool7(live.enCurso, tip);

  const techo = (b.costuras || []).some((c) => c.id === "techo" && c.alerta);
  const cola = acum >= SUMA_COLA && T >= MINUTO_LATE;
  const tarde = cola;
  const pocaG = nG < 2;
  const mediaBaja = meanG != null && meanG < MEDIA_OFF;
  const mediaNormal =
    meanG != null && meanG >= MEDIA_OFF && meanG < MEDIA_ON;
  const apagada =
    PILLS_APAGADA.has(b.pill) ||
    b.bandaMean === "muy apagado" ||
    b.bandaMean === "opaco";
  const unSoloGordo = nG === 1 && (b.maxG ?? meanG ?? 0) >= 85;

  const checks = {
    nG,
    meanG,
    acum,
    minuto: T,
    techo,
    cola,
    apagada,
    enZona,
    tip,
  };

  const motivos = [];

  if (techo) motivos.push("Techo: hora tras pico fuerte/muy fuerte/supernova");
  if (tarde) motivos.push("Cola: suma ≥850 y minuto ≥40");
  if (pocaG) motivos.push("Menos de 2 G — sin media fiable");
  if (mediaBaja) motivos.push("Media G <40");
  if (apagada && !mediaNormal && nG < 2)
    motivos.push("Hora apagada/opaca (Brillo)");
  if (unSoloGordo) motivos.push("Un solo G gordo — resto no levanta");

  const puertaAClasica =
    !techo &&
    !tarde &&
    nG >= 2 &&
    meanG != null &&
    meanG >= MEDIA_ON &&
    T < MINUTO_LATE &&
    acum < SUMA_COLA &&
    !(apagada && meanG < MEDIA_ON);

  if (puertaAClasica) {
    return {
      interruptor: "ON",
      estadoTarjeta: "EN RACHA",
      puertaA: true,
      puertaAFase: "media68",
      formaG: null,
      formaGLabel: null,
      enZona,
      tip,
      motivos: ["Puerta A cumplida — resto de hora en zona tip±1"],
      checks,
    };
  }

  const alerta =
    (T < 15 && nG < 2) ||
    mediaNormal ||
    (nG === 1 && !unSoloGordo) ||
    (nG >= 2 && meanG != null && meanG >= MEDIA_OFF && meanG < MEDIA_ON);

  const alertaOk = alerta && !techo && !tarde && !mediaBaja;

  if (alertaOk) {
    const alertMotivos = [];
    if (T < 15) alertMotivos.push("Apertura 00–15 — armando tercio");
    if (mediaNormal) alertMotivos.push("Media 40–67 — olor a normal");
    if (nG === 1) alertMotivos.push("Solo 1 G — falta compañía");
    if (nG >= 2 && meanG != null && meanG < MEDIA_ON)
      alertMotivos.push(`Media ${Math.round(meanG)} — falta ≥68 o forma`);

    const stubAlerta = {
      interruptor: "ALERTA",
      estadoTarjeta: "ALERTA",
      puertaA: false,
      enZona,
      tip,
      motivos: alertMotivos,
      checks,
    };
    const forma = detalleFormaG(live, stubAlerta);
    if (forma.apuestaOk) {
      return {
        interruptor: "ALERTA",
        estadoTarjeta: "PUERTA A",
        puertaA: true,
        puertaAFase: "formaG",
        formaG: forma.id,
        formaGLabel: forma.label,
        ultimosGForma: forma.ultimosG,
        enZona,
        tip,
        motivos: forma.motivos.length ? forma.motivos : [forma.label],
        checks,
      };
    }

    return {
      interruptor: "ALERTA",
      estadoTarjeta: "ALERTA",
      puertaA: false,
      puertaAFase: null,
      formaG: forma.id,
      formaGLabel: forma.label,
      ultimosGForma: forma.ultimosG,
      enZona,
      tip,
      motivos: alertMotivos.length ? alertMotivos : ["Observando régimen"],
      checks,
    };
  }

  if (!motivos.length) motivos.push("Puerta A apagada");

  return {
    interruptor: "OFF",
    estadoTarjeta: "ESPERANDO",
    puertaA: false,
    puertaAFase: null,
    formaG: null,
    formaGLabel: null,
    enZona,
    tip,
    motivos,
    checks,
  };
}
