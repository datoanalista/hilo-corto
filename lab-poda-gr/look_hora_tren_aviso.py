# -*- coding: utf-8 -*-
"""
LOOK: ¿el acortadero se ve ANTES del tren?
Y la cola de esa actividad: cuántos minutos, no un saco.
Forma: sequía (≥10 R) se cierra → ¿queda rato de racimo?
No Jaccard. No %. Película + minutos.
Cero cable.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout
from look_hora_secuencia import atom_r, es_nucleo
from look_hora_tren_frase import huecos_y_g, linea_g, trenes_en

OUT = LAB / "reports" / "LOOK_HORA_TREN_AVISO.txt"
LARGO = 10


def min_de(g) -> int:
    return int(getattr(g, "m0", 0) or 0) % 60


def tren_desde(hues, g_idx):
    """Si G[g_idx] abre un tren ≥3, largo en G. Si no, 0."""
    if g_idx >= len(hues) or hues[g_idx] != 0:
        return 0
    n = 1
    j = g_idx
    while j < len(hues) and hues[j] == 0:
        n += 1
        j += 1
    return n if n >= 3 else 0


def prox_tren(hues, desde_g):
    """Primer tren ≥3 que empiece en G[k] con k >= desde_g, antes de otro hueco ≥10."""
    k = desde_g
    while k < len(hues):
        if hues[k] >= LARGO:
            return None
        n = tren_desde(hues, k)
        if n >= 3:
            return k, n
        k += 1
    # tren que empieza en la última G (sin hueco a la derecha): no
    return None


def eventos_sequia(gs, hues):
    """Cada sequía cerrada: G[i] —≥10R— G[i+1]."""
    out = []
    for i, r in enumerate(hues):
        if r >= LARGO:
            out.append(i)
    return out


def analizar_hora(h):
    tiros = list(h.tiros or [])
    _, gs, hues = huecos_y_g(tiros)
    rows = []
    for i in eventos_sequia(gs, hues):
        cierra = i + 1  # G que cierra la sequía
        if cierra >= len(gs):
            continue
        tag = str(h.tag)
        r_seq = hues[i]
        m_cierra = min_de(gs[cierra])
        # hueco que abre DESPUÉS de cerrar la sequía
        if cierra >= len(hues):
            rows.append(
                {
                    "tag": tag,
                    "clase": "fin_hora",
                    "seq": r_seq,
                    "m_cierra": m_cierra,
                    "line": (
                        f"  {tag:<12} S{r_seq} cierra @{m_cierra:02d}  "
                        f"{linea_g(gs[cierra])}  · se acaba la hora"
                    ),
                }
            )
            continue

        primero = hues[cierra]
        n_pegado = tren_desde(hues, cierra)
        if n_pegado >= 3:
            m_fin = min_de(gs[cierra + n_pegado - 1])
            dur = (m_fin - m_cierra) % 60
            rows.append(
                {
                    "tag": tag,
                    "clase": "pegada",
                    "seq": r_seq,
                    "m_cierra": m_cierra,
                    "mins_tren": dur,
                    "n_g": n_pegado,
                    "line": (
                        f"  {tag:<12} S{r_seq} @{m_cierra:02d} → T{n_pegado} "
                        f"pegado (sin hueco corto)  tren {m_cierra:02d}–{m_fin:02d} "
                        f"({dur} min)  {linea_g(gs[cierra])}…{linea_g(gs[cierra + n_pegado - 1])}"
                    ),
                }
            )
            continue

        if primero >= LARGO:
            rows.append(
                {
                    "tag": tag,
                    "clase": "otra_sequia",
                    "seq": r_seq,
                    "m_cierra": m_cierra,
                    "line": (
                        f"  {tag:<12} S{r_seq} @{m_cierra:02d} → otra S{primero}  "
                        f"no hay acortadero"
                    ),
                }
            )
            continue

        # primera corta: se cierra en G[cierra+1]
        aviso = cierra + 1
        m_aviso = min_de(gs[aviso])
        espera = (m_aviso - m_cierra) % 60
        hit = prox_tren(hues, aviso)
        if hit is None:
            rows.append(
                {
                    "tag": tag,
                    "clase": "aviso_seco",
                    "seq": r_seq,
                    "m_cierra": m_cierra,
                    "m_aviso": m_aviso,
                    "espera": espera,
                    "primero": primero,
                    "line": (
                        f"  {tag:<12} S{r_seq} @{m_cierra:02d} → {primero}R @{m_aviso:02d} "
                        f"(+{espera} min)  aviso y NO tren después"
                    ),
                }
            )
            continue

        t0, n_g = hit
        m_t0 = min_de(gs[t0])
        m_t1 = min_de(gs[t0 + n_g - 1])
        cola = (m_t0 - m_aviso) % 60
        tren_min = (m_t1 - m_t0) % 60
        total = (m_t1 - m_cierra) % 60
        if t0 == aviso:
            clase = "aviso_es_tren"
            nota = "el aviso ES la 1ª G del tren"
        else:
            clase = "aviso_antes"
            nota = f"tren {m_t0:02d}–{m_t1:02d} · cola aviso→tren {cola} min"
        rows.append(
            {
                "tag": tag,
                "clase": clase,
                "seq": r_seq,
                "m_cierra": m_cierra,
                "m_aviso": m_aviso,
                "m_t0": m_t0,
                "m_t1": m_t1,
                "espera": espera,
                "cola": cola,
                "tren_min": tren_min,
                "total": total,
                "primero": primero,
                "n_g": n_g,
                "line": (
                    f"  {tag:<12} S{r_seq} @{m_cierra:02d} → {primero}R:{atom_r(primero)} "
                    f"@{m_aviso:02d} (+{espera} min)  T{n_g} {m_t0:02d}–{m_t1:02d} "
                    f"({tren_min} min)  {nota}  actividad {total} min"
                ),
            }
        )
    return rows


def tally_mins(rows, campo, tope=12):
    xs = [r[campo] for r in rows if r.get(campo) is not None]
    c = Counter(xs)
    if not xs:
        return "    (ninguna)"
    bits = [f"{k}min×{c[k]}" for k in sorted(c) if k <= tope]
    extra = sum(v for k, v in c.items() if k > tope)
    if extra:
        bits.append(f">{tope}min×{extra}")
    return "    " + "  ".join(bits)


def bloque(w, titulo, rows):
    w(f"════ {titulo} · {len(rows)} sequías ≥{LARGO}R cerradas ════")
    por = {}
    for r in rows:
        por.setdefault(r["clase"], []).append(r)
    orden = (
        "aviso_antes",
        "aviso_es_tren",
        "aviso_seco",
        "pegada",
        "otra_sequia",
        "fin_hora",
    )
    nombres = {
        "aviso_antes": "AVISO y el tren viene DESPUÉS (sí se ve antes)",
        "aviso_es_tren": "AVISO = 1ª G del tren (la corta cierra y ya pega)",
        "aviso_seco": "AVISO y no hay tren: se acortó y se apagó",
        "pegada": "SEQUÍA PEGADA al tren (no hay aviso)",
        "otra_sequia": "cierra S y sigue otra S",
        "fin_hora": "cierra S y se acaba la hora",
    }
    for k in orden:
        xs = por.get(k) or []
        if not xs:
            continue
        w(f"  — {nombres[k]} · {len(xs)} películas —")
        tope = 24 if k in ("aviso_antes", "aviso_es_tren", "pegada") else 10
        for r in xs[:tope]:
            w(r["line"])
        if len(xs) > tope:
            w(f"    … +{len(xs) - tope} películas")
        if k == "aviso_antes":
            w("  minutos CIERRE→AVISO (esperar la primera corta):")
            w(tally_mins(xs, "espera"))
            w("  minutos AVISO→1ª G del tren (la cola útil):")
            w(tally_mins(xs, "cola"))
            w("  minutos del tren mismo:")
            w(tally_mins(xs, "tren_min"))
            w("  minutos CIERRE→última G del tren (toda la actividad):")
            w(tally_mins(xs, "total"))
        if k == "aviso_es_tren":
            w("  minutos CIERRE→1ª G del tren (= la corta):")
            w(tally_mins(xs, "espera"))
            w("  minutos del tren mismo (eso es la cola):")
            w(tally_mins(xs, "tren_min"))
        if k == "pegada":
            w("  minutos del tren pegado (no hubo aviso):")
            w(tally_mins(xs, "mins_tren"))
        w("")


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    rt, rh = [], []
    for h in train:
        rt.extend(analizar_hora(h))
    for h in hold:
        rh.extend(analizar_hora(h))

    buf = []
    w = buf.append
    w("LOOK · aviso del acortadero · cola en minutos")
    w("Aviso = se cerró una sequía ≥10 R y el SIGUIENTE hueco ya no es sequía.")
    w("Esa G (la que cierra la corta) es el reloj del aviso.")
    w("Cola útil = minutos desde ese aviso hasta la 1ª G del tren.")
    w("No Jaccard. No saco. Cero cable.")
    w(f"Cinta {len(horas)} h  {horas[0].tag} → {horas[-1].tag}")
    w("")
    bloque(w, "TRAIN", rt)
    bloque(w, "HOLD 72 h", rh)
    w("Lectura:")
    w("  Si aviso_antes dura 2–5 min, hay cola corta para sentarse.")
    w("  Si aviso_es_tren: no viste el tren venir; lo estás pisando.")
    w("  Si pegada: no hay identificación previa.")
    w("  aviso_seco: el acortadero no promete tren.")
    w("  Cero cable.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT, "train", len(rt), "hold", len(rh))


if __name__ == "__main__":
    main()
