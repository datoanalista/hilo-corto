const fs = require('fs');
const path = require('path');

const MANUAL_FILE = path.join(__dirname, 'jokerbets-manual.json');

function defaultManual() {
  return {
    pendiente: false,
    disparada: false,
    disparadaAt: null,
    ultimoResultado: null,
    montoPorBono: 50,
  };
}

function normalizarMontoPorBono(n) {
  const x = Math.round(Number(n) / 50) * 50;
  if (!Number.isFinite(x) || x < 50) return 50;
  if (x > 1000) return 1000;
  return x;
}

function leerManual() {
  try {
    if (!fs.existsSync(MANUAL_FILE)) return defaultManual();
    const j = JSON.parse(fs.readFileSync(MANUAL_FILE, 'utf-8'));
    return { ...defaultManual(), ...j };
  } catch (_) {
    return defaultManual();
  }
}

function guardarManual(p) {
  try {
    fs.writeFileSync(
      MANUAL_FILE,
      JSON.stringify({ ...defaultManual(), ...p }, null, 2) + '\n',
      'utf-8'
    );
  } catch (_) {}
}

/** Un clic en botón UI = un disparo en las 3 cuentas. */
function armarDisparo(montoPorBono = 50) {
  const monto = normalizarMontoPorBono(montoPorBono);
  guardarManual({
    pendiente: true,
    disparada: false,
    disparadaAt: null,
    ultimoResultado: null,
    montoPorBono: monto,
    armadoAt: new Date().toISOString(),
  });
}

/** Nuevo clic en UI: reinicia sesión aunque quedara pendiente. */
function rearmarDisparo(montoPorBono = 50) {
  armarDisparo(montoPorBono);
}

function permitirTick(m) {
  m = m || leerManual();
  return Boolean(m.pendiente && !m.disparada);
}

function marcarDisparada(notas) {
  const m = leerManual();
  m.pendiente = false;
  m.disparada = true;
  m.disparadaAt = new Date().toISOString();
  if (notas) m.ultimoResultado = String(notas).slice(0, 280);
  guardarManual(m);
}

module.exports = {
  MANUAL_FILE,
  defaultManual,
  leerManual,
  guardarManual,
  armarDisparo,
  permitirTick,
  marcarDisparada,
  normalizarMontoPorBono,
};
