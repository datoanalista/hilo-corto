const fs = require('fs');
const path = require('path');

const PRUEBA_FILE = path.join(__dirname, 'jokerbets-prueba.json');

function defaultPrueba() {
  return {
    activa: false,
    cuenta: 'verde',
    gDetectada: null,
    disparada: false,
    disparadaAt: null,
  };
}

function leerPrueba() {
  try {
    if (!fs.existsSync(PRUEBA_FILE)) return defaultPrueba();
    const j = JSON.parse(fs.readFileSync(PRUEBA_FILE, 'utf-8'));
    return { ...defaultPrueba(), ...j };
  } catch (_) {
    return defaultPrueba();
  }
}

function guardarPrueba(p) {
  try {
    fs.writeFileSync(
      PRUEBA_FILE,
      JSON.stringify({ ...defaultPrueba(), ...p }, null, 2) + '\n',
      'utf-8'
    );
  } catch (_) {}
}

function onGrupoG(label, valor) {
  const p = leerPrueba();
  if (!p.activa || p.disparada || p.gDetectada) return;
  p.gDetectada = {
    label: String(label || ''),
    valor: valor != null ? valor : null,
    ts: new Date().toISOString(),
  };
  guardarPrueba(p);
}

function marcarDisparada(notas) {
  const p = leerPrueba();
  p.disparada = true;
  p.disparadaAt = new Date().toISOString();
  p.activa = false;
  if (notas) p.ultimoResultado = String(notas).slice(0, 240);
  guardarPrueba(p);
}

function permitirTickPrueba(p) {
  p = p || leerPrueba();
  return Boolean(p.activa && p.gDetectada && !p.disparada);
}

function cuentaParticipaPrueba(colorCuenta, p) {
  p = p || leerPrueba();
  const c = String(p.cuenta || 'verde').toLowerCase();
  if (c === 'todas') return true;
  return c === String(colorCuenta || '').toLowerCase();
}

module.exports = {
  PRUEBA_FILE,
  defaultPrueba,
  leerPrueba,
  guardarPrueba,
  onGrupoG,
  marcarDisparada,
  permitirTickPrueba,
  cuentaParticipaPrueba,
};
