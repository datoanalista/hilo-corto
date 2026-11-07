/** POST /api/jokerbets/apuesta-manual â€” compartido Cuentas + tablero v2. */

export const MANUAL_MONTO_STORAGE_KEY = "jokerbetsManualMonto";
export const MANUAL_MONTO_DEFAULT = 50;

export function leerMontoManualPreferido() {
  try {
    const v = Number(localStorage.getItem(MANUAL_MONTO_STORAGE_KEY));
    if (v >= 50 && v <= 1000 && v % 50 === 0) return v;
  } catch {
    /* ignore */
  }
  return MANUAL_MONTO_DEFAULT;
}

export function guardarMontoManualPreferido(monto) {
  try {
    localStorage.setItem(MANUAL_MONTO_STORAGE_KEY, String(monto));
  } catch {
    /* ignore */
  }
}

export async function fetchCuentasEstado() {
  const r = await fetch("/api/jokerbets/cuentas/estado", { credentials: "include" });
  if (r.status === 401) return { ok: false, auth: false };
  const j = await r.json();
  return j;
}

export async function postApuestaManual(body) {
  const r = await fetch("/api/jokerbets/apuesta-manual", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok || !j.ok) {
    const err = new Error(j.error || `HTTP ${r.status}`);
    err.response = j;
    throw err;
  }
  return j;
}

export async function dispararApuestaManualX3(montoPorBono = leerMontoManualPreferido()) {
  return postApuestaManual({ disparar: true, montoPorBono });
}

export async function cancelarApuestaManualX3() {
  return postApuestaManual({ cancelar: true });
}