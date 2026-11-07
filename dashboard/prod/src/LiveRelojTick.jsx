import { useEffect, useRef } from "react";
import { pad } from "./mesa.js";
import { relojSistema } from "./live.js";

/** Reloj HH:MM:SS en header live — tick local sin re-render del árbol. */
export default function LiveRelojTick({ className }) {
  const ref = useRef(null);

  useEffect(() => {
    function tick() {
      const r = relojSistema();
      if (ref.current) {
        ref.current.textContent = `${pad(r.hora)}:${pad(r.minuto)}:${pad(r.segundo)}`;
      }
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return <time ref={ref} className={className} aria-live="off" />;
}
