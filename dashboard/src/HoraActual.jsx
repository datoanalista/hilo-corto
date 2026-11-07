import { useEffect, useState } from "react";
import { pad } from "./mesa.js";

function formatear(d = new Date()) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export default function HoraActual() {
  const [txt, setTxt] = useState(() => formatear());
  useEffect(() => {
    const id = setInterval(() => setTxt(formatear()), 250);
    return () => clearInterval(id);
  }, []);
  return (
    <p className="hora-actual" aria-live="polite">
      {txt}
    </p>
  );
}
