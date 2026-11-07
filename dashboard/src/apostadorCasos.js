/**
 * Casos de la pastilla Apostador (silla, no color).
 * node src/apostadorCasos.js
 */
import { diagnosticarApostador } from "./sequiaGo.js";

function g(m0, extra = {}) {
  return {
    color: "G",
    m0,
    s0: 0,
    m1: (m0 + 1) % 60,
    s1: 10,
    ...extra,
  };
}

function r(m0) {
  return { color: "R", m0, s0: 0, m1: (m0 + 1) % 60, s1: 10 };
}

function expect(name, got, want) {
  const ok = got === want;
  console.log(`${ok ? "OK" : "FAIL"}  ${name}: ${got}${ok ? "" : ` (esperado ${want})`}`);
  if (!ok) process.exitCode = 1;
}

const sinG = diagnosticarApostador({
  tiros: [r(5), r(6)],
  tipProx: { tip: 10 },
});
expect("sin G → No", sinG.estado, "no");

const gap1 = diagnosticarApostador({
  tiros: [g(10)],
  tipProx: { tip: 11 },
});
expect("G gap1 normal → Pasa", gap1.estado, "pasa");

const silla = diagnosticarApostador({
  tiros: [g(10), r(11)],
  tipProx: { tip: 12 },
});
expect("G+R gap2 m_est en tip → Sí", silla.estado, "si");

const fuera = diagnosticarApostador({
  tiros: [g(10), r(11)],
  tipProx: { tip: 40 },
});
expect("gap2 fuera tip → No", fuera.estado, "no");

const sequia = diagnosticarApostador({
  tiros: [g(10), r(11), r(12), r(13), r(14)],
  tipProx: { tip: 15 },
});
expect("4R (gap≥5) → No", sequia.estado, "no");

const trenSi = diagnosticarApostador({
  tiros: [g(10), g(11)],
  tipProx: { tip: 12 },
});
expect("Tren gap1 silla → Sí (no Pasa)", trenSi.estado, "si");

const trenNo = diagnosticarApostador({
  tiros: [g(10), g(11)],
  tipProx: { tip: 40 },
});
expect("Tren gap1 fuera tip → No (no Pasa)", trenNo.estado, "no");

if (process.exitCode) {
  console.error("apostadorCasos: falló");
  process.exit(1);
}
console.log("apostadorCasos: ok");
