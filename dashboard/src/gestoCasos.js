/**
 * Casos del gesto entre G (badge = este hueco).
 * node src/gestoCasos.js
 */
import { atomDeR, buildGestoEsperado } from "./gestoInfo.js";

function g(extra = {}) {
  return { color: "G", tipo: 1, m0: 0, ...extra };
}
function r() {
  return { color: "R", m0: 0 };
}

function expect(name, got, want) {
  const ok = got === want;
  console.log(`${ok ? "OK" : "FAIL"}  ${name}: ${got}${ok ? "" : ` (esperado ${want})`}`);
  if (!ok) process.exitCode = 1;
}

expect("atom 0 → tren", atomDeR(0), "T");
expect("atom 3 → corto", atomDeR(3), "k");
expect("atom 8 → medio", atomDeR(8), "m");
expect("atom 9 → cola", atomDeR(9), "L");
expect("atom 16 → sequía", atomDeR(16), "S");

expect("sin G → null", buildGestoEsperado({ tiros: [r(), r()] }), null);

const cero = buildGestoEsperado({ tiros: [g()] });
expect("0 R → badge 0", cero?.pill, "Gesto: 0 R");

const tres = buildGestoEsperado({ tiros: [g(), r(), r(), r()] });
expect("3 R → corto 3", tres?.pill, "Gesto: corto 3");
expect("3 R tono", tres?.tono, "corto");

const ocho = buildGestoEsperado({ tiros: [g(), ...Array.from({ length: 8 }, r)] });
expect("8 R → medio 8", ocho?.pill, "Gesto: medio 8");
expect("8 R tono", ocho?.tono, "medio");
expect("8 R tooltip tipo", (ocho?.tooltip || "").includes("medio"), true);

const colaAbierta = buildGestoEsperado({
  tiros: [g(), ...Array.from({ length: 10 }, r)],
});
expect("10 R → cola 10", colaAbierta?.pill, "Gesto: cola 10");
expect("10 R tono", colaAbierta?.tono, "este-largo");

const cerrada = buildGestoEsperado({
  tiros: [g(), ...Array.from({ length: 12 }, r), g()],
});
expect("tras cola cerrado → 0 R", cerrada?.pill, "Gesto: 0 R");
expect("tras cola tooltip no otra", (cerrada?.tooltip || "").includes("no otra cola"), true);

const extra = buildGestoEsperado({
  tiros: [g(), { color: "G", tipo: 5 }, r(), r()],
});
expect("extra no ancla · 3 tiros hueco", extra?.pill, "Gesto: corto 3");

if (process.exitCode) {
  console.error("gestoCasos: falló");
  process.exit(1);
}
console.log("gestoCasos: ok");
