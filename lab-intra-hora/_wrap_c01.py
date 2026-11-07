# -*- coding: utf-8
"""H2: L wrap y 1er G — replica C01 bitacora."""
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta

cinta, _, _ = cargar_ingesta("")
wrap_L = 0
no_wrap = 0
first_g_mins_wrap = []
first_g_mins_nowrap = []
n_hours = 0

for tag in cinta.orden:
    h = cinta.get(tag)
    tiros = h.tiros_nucleo or []
    gs = [t for t in tiros if t.color == "G" and t.lumen]
    if not gs:
        continue
    n_hours += 1
    first_g = min(gs, key=lambda t: (t.m0, t.s0))
    # L wrap: algun L con m1>=60 o cruza :00 — proxy: ultimo R/L antes del 1er G termina en 59 o arranca antes de :00
    before_first = [t for t in tiros if (t.m0 < first_g.m0) or (t.m0 == first_g.m0 and t.s0 < first_g.s0)]
    wrapped = False
    for t in before_first:
        if t.m1 > t.m0 or (t.m0 == 59 and t.m1 == 0) or t.start_s + t.dur_s >= 3540:
            wrapped = True
            break
    # simpler: last tiro before first G has m0>=58 or spans hour
    if before_first:
        last_b = before_first[-1]
        if last_b.m0 >= 58 or last_b.m1 < last_b.m0:
            wrapped = True
    if wrapped:
        wrap_L += 1
        first_g_mins_wrap.append(first_g.m0)
    else:
        no_wrap += 1
        first_g_mins_nowrap.append(first_g.m0)

print("=== L WRAP vs 1er G (proxy C01) ===")
print(f"horas n={n_hours}")
print(f"  wrap proxy: {wrap_L} ({100*wrap_L/n_hours:.0f}%)")
print(f"  no wrap: {no_wrap}")
if first_g_mins_wrap:
    print(f"  1er G min si wrap: med={median(first_g_mins_wrap):.0f}  pct 0-3={100*sum(1 for m in first_g_mins_wrap if m<=3)/len(first_g_mins_wrap):.0f}%")
if first_g_mins_nowrap:
    print(f"  1er G min sin wrap: med={median(first_g_mins_nowrap):.0f}  pct 0-3={100*sum(1 for m in first_g_mins_nowrap if m<=3)/len(first_g_mins_nowrap):.0f}%")

# G en 58-59 de la hora
late_g = 0
for tag in cinta.orden:
    h = cinta.get(tag)
    gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
    if any(t.m0 >= 58 for t in gs):
        late_g += 1
print(f"\nhoras con al menos 1 G m0>=58: {late_g}/{n_hours} ({100*late_g/n_hours:.0f}%)")

# Perfil "solo cola": sin G 0-9 Y con G 58+
solo_cola = 0
solo_apertura = 0
for tag in cinta.orden:
    h = cinta.get(tag)
    gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
    if not gs:
        continue
    e = any(t.m0 <= 9 for t in gs)
    l = any(t.m0 >= 58 for t in gs)
    if l and not e:
        solo_cola += 1
    if e and not l:
        solo_apertura += 1
print(f"solo cola (G 58+ sin G 0-9): {solo_cola} ({100*solo_cola/n_hours:.0f}%)")
print(f"solo apertura (G 0-9 sin G 58+): {solo_apertura} ({100*solo_apertura/n_hours:.0f}%)")
