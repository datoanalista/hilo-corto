/** Poll con pausa si la pestaña está en background. */
export function crearPollVisibilidad(tick, ms = 2000) {
  let vivo = true;
  let id = null;

  function correr() {
    if (!vivo || document.hidden) return;
    tick();
  }

  function armar() {
    correr();
    id = setInterval(correr, ms);
  }

  function onVisibilidad() {
    if (!vivo || document.hidden) return;
    correr();
  }

  armar();
  document.addEventListener("visibilitychange", onVisibilidad);

  return () => {
    vivo = false;
    if (id) clearInterval(id);
    document.removeEventListener("visibilitychange", onVisibilidad);
  };
}
