/**
 * Casos de la lámpara (INFO · no tip).
 * node src/lamparaCasos.js
 */
import { tipSiguienteG } from "./tipProxima.js";
import { buildLamparaLectura } from "./lamparaInfo.js";

function g(m0, extra = {}) {
  return { color: "G", tipo: 1, m0, s0: 0, m1: m0, s1: 40, ...extra };
}
function r(m0 = 0) {
  return { color: "R", m0 };
}

function expect(name, got, want) {
  const ok = Object.is(got, want);
  console.log(`${ok ? "OK" : "FAIL"}  ${name}: ${got}${ok ? "" : ` (esperado ${want})`}`);
  if (!ok) process.exitCode = 1;
}

function tipDe(luces) {
  return tipSiguienteG({ luces, minutoAhora: null });
}

const corto = tipDe([6, 11]);
expect("p30 corto no enciende", buildLamparaLectura({
  tiros: [g(6), r(), r(), g(11), r(), r()],
  tipProx: corto,
}), null);

const largo = tipDe([6, 17]);
expect("p30 largo medGap ≥9", Number(largo.medGap) >= 9, true);

const puertaOk = [g(6), ...Array.from({ length: 10 }, () => r()), g(17), r(), r()];
const lamp = buildLamparaLectura({ tiros: puertaOk, tipProx: largo });
expect("puerta + p30 largo → se pasa", lamp?.pill, "se pasa");
expect("no mueve tip", lamp?.tip, largo.tip);

const sequia = [g(6), ...Array.from({ length: 10 }, () => r()), g(17), r(), r(), r(), r()];
expect("sequía · puerta cerrada → apagada", buildLamparaLectura({
  tiros: sequia,
  tipProx: largo,
}), null);

const pegado = [g(6), ...Array.from({ length: 10 }, () => r()), g(17)];
expect("pegado sin tren → apagada", buildLamparaLectura({
  tiros: pegado,
  tipProx: largo,
}), null);

if (process.exitCode) {
  console.error("lamparaCasos: falló");
  process.exit(1);
}
console.log("lamparaCasos: ok");
