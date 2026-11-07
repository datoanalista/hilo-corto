"""Motor: informe de banda (G y +-1), no Jaccard.

El juez de esta caja es la BANDA d<=1. +-2 se trata como fuera.
El dardo que cubre esa banda por hilo es la casilla de H-1
(persist = exacto; ambos vecinos = score). No se sienta el vecino
como si fuera un exacto distinto: no hay senal de lado.

Costura (cierre largo) es el unico tiro SEGURO exacto (~95%).
No se rellenan huecos con tiros frios. Jaccard no entra.
"""

from __future__ import annotations

from statistics import median

from .estado import Estado, VENTANA_CILINDRO, siguiente_tag

ENCABEZADO = (
    "NO ES AZAR. La cinta nombra. Los nombres de las sillas, no.\n"
    "\n"
    "Pruebas (519 h, h10-230726, nucleo Venus):\n"
    "1) Cierre LARGO: el primer tiro de la proxima es G el 94.8% "
    "(145/153). Un sombrero de 1 silla acierta el 1.7%. Eso no es un dado.\n"
    "2) Cierre CORTO: ese dardo no existe. El mismo oficio predice la ausencia.\n"
    "3) Las luces casi no se sientan pegadas (fermion). Un sombrero de 10 "
    "sillas las pegaria mas.\n"
    "4) Jaccard / copiar la foto: ~azar. Persist ~16.8% = densidad (nG/60). "
    "Por eso el entregable NO persigue el minuto exacto como mapa.\n"
    "5) El 45% de las G caen a d<=1 de H-1 porque ese anillo PINTA ~27 "
    "sillas de 60. Un sombrero del mismo tamano pinta lo mismo (lift 1.00). "
    "Eso es techo de AREA, no atraccion magica.\n"
    "\n"
    "El producto lo evidencia: SEGURO solo cuando la cinta nombra (cierre largo). "
    "TIBIO = isla de H-1, cobra la banda, no finge 95%. "
    "LIVE (desde 2026-08-30): boleto = INTER2 · acuerdo exacto ≥2 de P0–P5. "
    "P0 clásico (islas+costura) queda en sombra como Pool 9. "
    "El 55% restante (semillas / +-2) no tiene padron en la foto previa.\n"
    "Juez: banda d<=1. +-2 = fuera. Jaccard no entra. Cero LIVE."
)

ANDENES = (
    ("temprano", 0, 19),
    ("medio", 20, 39),
    ("tarde", 40, 59),
)


def dist_anillo(a: int, b: int) -> int:
    d = abs(a - b) % 60
    return min(d, 60 - d)


def min_dist_a_conjunto(m: int, ocupadas: set[int]) -> int:
    if not ocupadas:
        return 99
    return min(dist_anillo(m, x) for x in ocupadas)


def nG_clima(estado: Estado) -> int:
    cola = estado.cola(VENTANA_CILINDRO)
    if not cola:
        return 10
    return int(max(7, min(13, round(median(h.nG for h in cola)))))


def nombre_clima(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "rica"
    return "normal"


def _anden_de(m: int) -> str:
    if m <= 19:
        return "temprano"
    if m <= 39:
        return "medio"
    return "tarde"


def paso_sombra(foto: list[int]) -> int:
    """Mediana huecos entre islas H-1 (1..20). Fallback 4."""
    xs = sorted({m % 60 for m in (foto or [])})
    if len(xs) < 2:
        return 4
    gaps = []
    for i in range(len(xs) - 1):
        gaps.append((xs[i + 1] - xs[i]) % 60)
    gaps.append((xs[0] + 60 - xs[-1]) % 60)
    gaps = [g for g in gaps if 1 <= g <= 20]
    if not gaps:
        return 4
    return int(round(median(gaps)))


def proponer_som02_chip(
    foto: list[int],
    ocupadas: set[int],
    clima: int,
) -> tuple[int | None, int, str]:
    """SOM02 lab → prod. Devuelve (cand, paso, motivo)."""
    if not foto:
        return None, 4, "sin_foto_H-1"
    bs = set(ocupadas)
    if len(bs) >= clima:
        return None, paso_sombra(foto), "cupo_lleno_k>=clima"
    paso = paso_sombra(foto)
    cand = (max(foto) + paso) % 60
    if cand == 1:
        return None, paso, "veto_minuto_01"
    if cand in bs:
        return None, paso, "ya_en_boleto"
    if min_dist_a_conjunto(cand, bs) < 2:
        return None, paso, "fermion_d<2"
    return cand, paso, "ok"


def _cruces(h1: set[int]) -> list[int]:
    """Minutos que son +-1 de dos o mas islas. Orilla caliente, no chip extra."""
    votos: dict[int, int] = {}
    for s in h1:
        for d in (-1, 1):
            m = (s + d) % 60
            votos[m] = votos.get(m, 0) + 1
    return sorted(m for m, n in votos.items() if n >= 2)


def _resto_de(h1: set[int]) -> dict:
    """Skip ±2 y puentes (islas a dist 4). Se NOMBRAN, no se sientan."""
    if not h1:
        return {"skip": [], "puentes": []}
    skip: set[int] = set()
    for s in h1:
        for d in (2, -2):
            m = (s + d) % 60
            if m not in h1:
                skip.add(m)
    puentes: list[int] = []
    xs = sorted(h1)
    n = len(xs)
    for i, a in enumerate(xs):
        b = xs[(i + 1) % n]
        if (b - a) % 60 == 4:
            mid = (a + 2) % 60
            if mid not in h1:
                puentes.append(mid)
    return {"skip": sorted(skip), "puentes": sorted(set(puentes))}


def _racimos(h1: list[int]) -> list[dict]:
    """Tramos de islas con hueco <=4. Forma: zona con N intercaladas."""
    if not h1:
        return []
    xs = sorted(set(h1))
    grupos: list[list[int]] = [[xs[0]]]
    for m in xs[1:]:
        if dist_anillo(m, grupos[-1][-1]) <= 4:
            grupos[-1].append(m)
        else:
            grupos.append([m])
    # wrap 59..0
    if len(grupos) >= 2 and dist_anillo(grupos[0][0], grupos[-1][-1]) <= 4:
        grupos[0] = grupos[-1] + grupos[0]
        grupos.pop()
    out = []
    for g in grupos:
        if len(g) < 3:
            continue
        a, b = g[0], g[-1]
        out.append(
            {
                "desde": a,
                "hasta": b,
                "n_islas": len(g),
                "flag": "CALIENTE" if len(g) >= 5 else "TIBIA",
                "nota": f"entre {a:02d} y {b:02d} H-1 trajo {len(g)} islas intercaladas (zona a mirar)",
            }
        )
    return out


def construir_informe(estado: Estado, tope: int | None = None) -> dict:
    cola = estado.cola(VENTANA_CILINDRO)
    if not cola:
        return {
            "tiros": [],
            "zonas": [],
            "orillas": [],
            "boleto": [],
            "foto": [],
            "resto": {"skip": [], "puentes": []},
        }

    ultima = cola[-1]
    h1 = sorted(set(ultima.nucleo))
    h1s = set(h1)
    cas0 = int(ultima.t0_proxima) // 60
    prev_largo = bool(ultima.last_largo)
    clima = nG_clima(estado)
    clima_nom = nombre_clima(clima)
    tope_uso = clima if tope is None else tope

    tiros: list[dict] = []
    usados: set[int] = set()

    def push(tiro: dict) -> None:
        m = tiro["minuto"] % 60
        if m in usados:
            return
        usados.add(m)
        tiro["minuto"] = m
        tiros.append(tiro)

    if prev_largo:
        push(
            {
                "minuto": cas0,
                "flag": "SEGURO",
                "apunta": "EXACTO",
                "lado": None,
                "cubre": [cas0],
                "rol": "costura",
                "nota": "cierre largo: primer tiro de la proxima es G",
            }
        )

    # Islas de H-1: un chip por casilla. Cubre persist y ambos +-1.
    # No se inventan minutos. Si hay mas islas que el clima, se quedan
    # las mas aisladas (fermion / islas, no Jaccard).
    islas = list(h1)
    if len(islas) > tope_uso - len(tiros):
        cupo = max(0, tope_uso - len(tiros))
        islas = sorted(
            islas,
            key=lambda s: (-min_dist_a_conjunto(s, h1s - {s}), s),
        )[:cupo]

    for s in sorted(islas):
        if s in usados:
            # ya es costura: se queda SEGURO, la banda la cubre igual
            continue
        push(
            {
                "minuto": s,
                "flag": "TIBIO",
                "apunta": "BANDA",
                "lado": "ambos",
                "cubre": [(s - 1) % 60, s, (s + 1) % 60],
                "rol": "isla",
                "nota": "casilla de H-1; el score vive en persist y en +-1",
            }
        )

    som02_cand, som02_paso, som02_motivo = proponer_som02_chip(h1, usados, tope_uso)
    if som02_cand is not None:
        push(
            {
                "minuto": som02_cand,
                "flag": "TIBIO",
                "apunta": "BANDA",
                "lado": "ambos",
                "cubre": [
                    (som02_cand - 1) % 60,
                    som02_cand,
                    (som02_cand + 1) % 60,
                ],
                "rol": "sombra",
                "nota": (
                    f"SOM02: max(H-1)+paso ~{som02_paso}; "
                    "chip sombra (lab Δscore +0.10 train)"
                ),
            }
        )

    cupos = []
    for nom, a, b in ANDENES:
        n = sum(1 for m in h1 if a <= m <= b)
        flag = "NORMAL"
        if clima_nom == "floja" and nom == "temprano":
            flag = "FRIA"
        elif clima_nom == "rica" and nom == "temprano":
            flag = "HINCHADA"
        elif n == 0:
            flag = "VACIA"
        elif n >= 5:
            flag = "CUPOSA"
        cupos.append(
            {
                "anden": nom,
                "rango": [a, b],
                "islas_H1": n,
                "esperadas": n,
                "flag": flag,
                "nota": "cupo visto en H-1, no pronostico de la proxima",
            }
        )

    orillas = []
    for m in _cruces(h1s):
        padres = sorted(s for s in h1s if dist_anillo(m, s) == 1)
        lados = []
        for s in padres:
            lados.append("+1" if (s + 1) % 60 == m else "-1")
        orillas.append(
            {
                "minuto": m,
                "flag": "CALIENTE",
                "apunta": "BANDA",
                "lado": "/".join(lados),
                "padres": padres,
                "nota": "orilla de dos islas; no es chip extra",
            }
        )

    boleto = sorted(t["minuto"] for t in tiros)
    return {
        "tiros": sorted(tiros, key=lambda t: t["minuto"]),
        "zonas_anden": cupos,
        "zonas_racimo": _racimos(h1),
        "orillas": orillas,
        "boleto": boleto,
        "foto": list(h1),
        "resto": _resto_de(h1s),
        "clima": clima_nom,
        "nG_clima": clima,
        "prev_largo": prev_largo,
        "casilla_arranque": cas0,
        "n_islas_h1": len(h1),
        "som02": {
            "cand": som02_cand,
            "paso": som02_paso,
            "motivo": som02_motivo,
            "entrada": som02_cand is not None,
        },
    }


def _fmt_min(m: int) -> str:
    return f"{m % 60:02d}"


def _cubre_de(m: int) -> tuple[int, int, int]:
    return (m - 1) % 60, m % 60, (m + 1) % 60


def _tramos_cubiertos(minutos: list[int]) -> list[tuple[int, int]]:
    if not minutos:
        return []
    s: set[int] = set()
    for m in minutos:
        a, c, b = _cubre_de(m)
        s.update((a, c, b))
    xs = sorted(s)
    out = []
    a = prev = xs[0]
    for x in xs[1:]:
        if x == prev + 1:
            prev = x
            continue
        out.append((a, prev))
        a = prev = x
    out.append((a, prev))
    return out


def _txt_tramo(a: int, b: int) -> str:
    if a == b:
        return _fmt_min(a)
    return f"{_fmt_min(a)}-{_fmt_min(b)}"


def _bloques_fichas(boleto: list[int]) -> dict[str, list[int]]:
    b: dict[str, list[int]] = {"00-19": [], "20-39": [], "40-59": []}
    for m in sorted(set(boleto)):
        if m <= 19:
            b["00-19"].append(m)
        elif m <= 39:
            b["20-39"].append(m)
        else:
            b["40-59"].append(m)
    return b


def _lista_mins(xs: list[int]) -> str:
    if not xs:
        return ""
    if len(xs) == 1:
        return _fmt_min(xs[0])
    if len(xs) == 2:
        return f"{_fmt_min(xs[0])} y {_fmt_min(xs[1])}"
    return ", ".join(_fmt_min(x) for x in xs[:-1]) + f" y {_fmt_min(xs[-1])}"


def _hueco_mayor(cub: set[int]) -> tuple[int, int, int] | None:
    if not cub or len(cub) >= 60:
        return None
    vacio = [i not in cub for i in range(60)]
    runs: list[tuple[int, int, int]] = []
    i = 0
    while i < 60:
        if not vacio[i]:
            i += 1
            continue
        j = i
        while j < 60 and vacio[j]:
            j += 1
        runs.append((i, j - 1, j - i))
        i = j
    if len(runs) >= 2 and vacio[0] and vacio[59]:
        n = runs[0][2] + runs[-1][2]
        a, b = runs[-1][0], runs[0][1]
        runs = runs[1:-1] + [(a, b, n)]
    if not runs:
        return None
    return max(runs, key=lambda t: t[2])


def texto_informe(doc: dict) -> str:
    """Log en lengua de mesa de apuestas. Mismo boleto. Sin Jaccard."""
    if not doc.get("based_on"):
        return "No hay hora cerrada: no hay informe."

    destino = doc.get("for") or "?"
    origen = doc.get("based_on") or "?"
    meta = doc.get("meta") or {}
    largo = meta.get("prev_largo")
    if largo is None:
        largo = doc.get("prev_largo")
    cas0 = meta.get("casilla_arranque", doc.get("casilla_arranque"))
    try:
        cas0 = int(cas0) % 60 if cas0 is not None else None
    except (TypeError, ValueError):
        cas0 = None

    joker = list(doc.get("boleto") or [])
    tiros = doc.get("tiros") or []
    if not joker and tiros:
        joker = [int(t["minuto"]) % 60 for t in tiros]
    joker = sorted(set(int(m) % 60 for m in joker))

    nisl = meta.get("n_islas_h1")
    if nisl is None:
        nisl = doc.get("n_islas_h1")
    if nisl is None:
        nisl = len([t for t in tiros if t.get("rol") == "isla"])

    lineas = [
        f"Mesa {destino}",
        f"(en la anterior, {origen}, ya se vieron las luces)",
        "",
    ]

    lineas.append("1) Número seguro")
    if largo and cas0 is not None:
        lineas.append(
            f"Sí: el {_fmt_min(cas0)}. Es la única apuesta a pleno. "
            "Si el cierre anterior fue largo, ese minuto casi siempre paga."
        )
        if cas0 not in joker:
            joker = sorted(set(joker + [cas0]))
    else:
        lineas.append(
            "No hay. El cierre anterior fue corto: nadie tiene un pleno. "
            "Todas las fichas de abajo cobran solo si sale el minuto o el de al lado."
        )
    lineas.append("")

    lineas.append("2) ¿Te sentás a esta mesa?")
    if nisl <= 0 and not (largo and cas0 is not None):
        lineas.append(
            "No. La mesa anterior no dejó minutos para copiar. "
            "Sin ese mapa, la mitad de estas mesas se van en blanco. "
            "Plantate: no gastar fichas acá es acierto."
        )
        lineas.append("")
        lineas.append("No hay lista de apuestas.")
        return "\n".join(lineas) + "\n"
    if nisl <= 2 and not largo:
        lineas.append(
            "Mejor no. La anterior dejó muy poco. Estas mesas se caen "
            "más de lo normal. Si no estás seguro, no vayas: conservás las fichas."
        )
    elif nisl <= 2 and largo and cas0 is not None:
        lineas.append(
            f"Sí, con poco: el pleno {_fmt_min(cas0)} y lo que quedó de la "
            "mesa anterior. Si eso no cobra, plantate. No persigas el resto del reloj."
        )
    else:
        n = len(joker)
        palabra = "ficha" if n == 1 else "fichas"
        lineas.append(
            f"Sí. Ponemos {n} {palabra}: son los minutos que "
            "prendieron la vez anterior. No agregues de más."
        )
    lineas.append("")

    if not joker:
        lineas.append("No hay fichas.")
        return "\n".join(lineas) + "\n"

    lineas.append("3) Tus fichas")
    lineas.append(
        "Cada una cobra si sale ESE minuto o el de al lado "
        "(tres números pegados). No es pleno, salvo el seguro de arriba."
    )
    for m in joker:
        a, c, b = _cubre_de(m)
        nota = ""
        if largo and cas0 is not None and m == cas0:
            nota = "  ← pleno"
        lineas.append(
            f"  {_fmt_min(m)}  cobra {_fmt_min(a)}, {_fmt_min(c)} y {_fmt_min(b)}{nota}"
        )

    trs = _tramos_cubiertos(joker)
    if trs:
        bits = [_txt_tramo(a, b) for a, b in trs]
        lineas.append("Tramos que quedan cubiertos: " + ", ".join(bits) + ".")
    for a, b in trs:
        largo_t = (b - a + 1) if a <= b else (60 - a + b + 1)
        if largo_t < 5:
            continue
        if a <= b:
            chips = [m for m in joker if a <= m <= b]
        else:
            chips = [m for m in joker if m >= a or m <= b]
        if len(chips) >= 2:
            lineas.append(
                f"{_lista_mins(chips)} cubren el tramo {_txt_tramo(a, b)}: "
                "si la luz cae ahí, cobrás de vecino."
            )
    lineas.append("")

    bl = _bloques_fichas(joker)
    lineas.append("4) Mientras corre la mesa")
    primero, medio, final = bl["00-19"], bl["20-39"], bl["40-59"]
    if primero:
        lineas.append(
            f"Del 00 al 19 están {_lista_mins(primero)}. "
            "Si llega el minuto 20 y no cobraste ninguna, no persigas "
            "el hueco del medio."
            + (
                f" Queda {_lista_mins(final)} al final, o plantate."
                if final
                else " Plantate."
            )
        )
    else:
        lineas.append(
            "En el primer tercio (00-19) no tenemos ficha. "
            "Si de 00 a 19 no cae ninguna luz en la mesa, suele venir corta: "
            "no agregues, esperá tus minutos o plantate."
        )
    lineas.append(
        "Señal más fuerte: si de 00 a 19 no cayó NINGUNA luz "
        "(ni las tuyas ni otras), no sigas tirando. Esas mesas suelen ser cortas."
    )
    lineas.append(
        "Al minuto 20 se cierra ese tercio: 0 luces → plantate; "
        "1 → a menudo corta, no agregues; 2 o más → seguí el plan. "
        "No llenes el reloj aunque se vea viva: el último tercio no se hincha."
    )
    lineas.append(
        "Al minuto 40: si el medio (20-39) quedó en blanco, otra vez corta. "
        "No persigas. Un solo aviso a los 30 lava el plantate: el corte útil es 20 y 40."
    )
    lineas.append(
        "El hueco no se carga (cómo VA la hora, no cómo se viene). "
        "Ejemplo: si cayó el 12 y van 6 minutos sin otra, el 18 no está "
        "más caliente que el 13. No pongas ficha nueva porque “ya toca”."
    )
    lineas.append(
        "Si la mesa ya prendió varias y ahora hay un hueco, no fiche un extra: "
        "viva no te debe una de más. Van 4 luces no apaga ni enciende la próxima. "
        "Si viene flaca y cae una suelta en el hueco, se nombra; no es ficha nueva."
    )
    lineas.append(
        "El final del reloj no calienta. Ejemplo: un tiro que empieza en el 55 "
        "tiene la misma chance que uno a las 10. Lo gordo es el que cruza la hora "
        "(está partido), no “los últimos minutos”."
    )
    lineas.append(
        "Una luz pinta de más: ocupa varios minutos. El del medio no es otra luz; "
        "no lo fiche. El +2 de la última tampoco es orilla de la foto."
    )
    lineas.append(
        "Si una ficha ya cobró (ese minuto o el de al lado), "
        "no persigas los otros dos de esa tripleta: "
        "nueve de diez veces no hay segunda luz ahí."
    )
    if len(primero) >= 2 and (primero[2:] or medio or final):
        a, b = primero[0], primero[1]
        resto_p = primero[2:]
        if resto_p:
            extra = (
                f" Las otras de ese tramo ({_lista_mins(resto_p)}) siguen; "
                "no las retires."
            )
        elif medio or final:
            extra = " Las fichas de más tarde siguen; no las retires."
        else:
            extra = " Si nadie cobró, plantate."
        lineas.append(
            f"Si {_fmt_min(a)} y {_fmt_min(b)} no cobran ni de vecino, no es motivo "
            f"para cancelar toda la mesa.{extra}"
        )
    if medio and primero:
        lineas.append(
            f"En el medio están {_lista_mins(medio)}. "
            "Solo si el primer tercio cobró o la mesa no está en blanco."
        )
    if final and (primero or medio):
        lineas.append(
            f"Al final: {_lista_mins(final)}. "
            "Si venís sin cobrar y la mesa no está seca, es la última carta. "
            "Si venís en blanco desde el 00, plantate antes."
        )
    lineas.append("")

    lineas.append("5) Qué no jugar")
    cub: set[int] = set()
    for m in joker:
        aa, cc, bb = _cubre_de(m)
        cub.update((aa, cc, bb))
    hueco = _hueco_mayor(cub)
    if hueco and hueco[2] >= 8:
        a, b, n = hueco
        lineas.append(
            f"No pongas fichas entre {_fmt_min(a)} y {_fmt_min(b)} "
            f"({n} minutos sin cobertura). La mesa anterior no los nombró."
        )
    lineas.append(
        "No apuestes el minuto de al lado de una luz que YA salió: "
        "casi no se pegan dos luces juntas."
    )
    lineas.append("No agregues minutos que no están en la lista de arriba.")
    lineas.append(
        "Si una ficha ya cobró, no persigas los otros dos de ESA ficha "
        "(nueve de diez no hay segunda luz ahí). Eso no es lo mismo que "
        "una luz lejos de tus fichas: si caen dos juntas en un hueco, "
        "tampoco persigas la compañera."
    )
    lineas.append(
        "Si acaba de caer una luz, no pongas ficha dos minutos más "
        "adelante como si fuera orilla de la foto."
    )
    lineas.append(
        "No cuelgues minutos extra. La próxima mesa no se llena con estas cuatro."
    )
    lineas.append("")

    resto = doc.get("resto") or (meta.get("resto") if isinstance(meta, dict) else None) or {}
    skip = list(resto.get("skip") or [])
    puentes = list(resto.get("puentes") or [])
    lineas.append("6) El resto se lee, no se apuesta")
    if skip:
        muestra = skip[:8]
        cola = f" …(+{len(skip) - 8})" if len(skip) > 8 else ""
        lineas.append(
            "A dos minutos de las islas de la mesa anterior hay orillas: "
            + ", ".join(_fmt_min(m) for m in muestra)
            + cola
            + ". Se nombran; no las fichés. Se llenan como cualquier silla vacía."
        )
    else:
        lineas.append(
            "Esta mesa no dejó orillas a dos minutos (o no hay foto). "
            "Igual: no agregues minutos que no están arriba."
        )
    if puentes:
        lineas.append(
            "Puente (orilla entre dos islas cercanas): "
            + ", ".join(_fmt_min(m) for m in puentes[:6])
            + ". También se nombra, no se ficha."
        )
    lineas.append(
        "Las luces que nazcan lejos de tus fichas se nombran al caer "
        "(sueltas, de a dos o en grupo). No son ficha nueva."
    )
    return "\n".join(lineas) + "\n"


def construir_foto(estado: Estado, tope: int | None) -> tuple[list[int], list[str]]:
    inf = construir_informe(estado, tope)
    mins = inf["boleto"]
    roles = []
    by_m = {t["minuto"]: t["rol"] for t in inf["tiros"]}
    for m in mins:
        roles.append(by_m.get(m, "isla"))
    return mins, roles


def emitir_boleto(estado: Estado, k: int | None = None) -> dict:
    ultima = estado.ultima()
    if ultima is None:
        return {
            "based_on": None,
            "for": None,
            "boleto": [],
            "tiros": [],
            "lectura": "No hay hora cerrada: no hay informe.",
            "meta": {"maquina": "hilo-corto", "nota": "estado vacio: no hay hora cerrada"},
        }

    inf = construir_informe(estado, k)
    mix: dict[str, int] = {}
    for t in inf["tiros"]:
        mix[t["rol"]] = mix.get(t["rol"], 0) + 1

    out = {
        "based_on": ultima.tag,
        "for": siguiente_tag(ultima.tag),
        "boleto": inf["boleto"],
        "tiros": inf["tiros"],
        "zonas_anden": inf["zonas_anden"],
        "zonas_racimo": inf["zonas_racimo"],
        "orillas": inf["orillas"],
        "foto": inf.get("foto") or [],
        "resto": inf.get("resto") or {"skip": [], "puentes": []},
        "meta": {
            "maquina": "hilo-corto",
            "k_efectivo": len(inf["boleto"]),
            "nG_clima": inf["nG_clima"],
            "clima": inf["clima"],
            "mix": mix,
            "t0_s": ultima.t0_proxima,
            "casilla_arranque": inf["casilla_arranque"],
            "prev_largo": inf["prev_largo"],
            "n_islas_h1": inf.get("n_islas_h1", 0),
            "som02": inf.get("som02") or {},
            "columnas": estado.calentamiento(),
            "n_cerradas": estado.n_cerradas(),
            "calentamiento": estado.calentamiento() < 2,
            "nota": (
                "juez = banda d<=1. Isla de H-1 = chip TIBIO (cubre persist y +-1). "
                "SOM02 = chip sombra si cupo/fermión. "
                "Costura = SEGURO exacto. Orillas se informan, no se disparan. "
                "Lado +1/-1: sin senal (no se nombra). Jaccard no entra."
            ),
        },
    }
    out["lectura"] = texto_informe(out)
    return out
