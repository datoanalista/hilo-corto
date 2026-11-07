# quick eval r3 extra rules
import sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent))
from core_gc import load_horas, split_holdout, metrics_binary
from run_lab_r3 import perfilar_horas

EXTRA = Path(__file__).resolve().parents[1] / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
horas = load_horas(EXTRA)
perfiles = perfilar_horas(horas)
train_h, test_h = split_holdout(horas, 72)
train_tags = {h.tag for h in train_h}
train_p = [p for p in perfiles if p.h.tag in train_tags]
test_p = [p for p in perfiles if p.h.tag not in train_tags]
by_day = defaultdict(list)
for p in perfiles:
    by_day[p.h.tag.split("-")[1]].append(p)

def dia_ya_cola(p):
    day = p.h.tag.split("-")[1]
    hod = p.h.hod
    return any(x.h.hod < hod and x.tiene_cola500 for x in by_day[day])

rules = [
    ("dia_caliente", dia_ya_cola),
    ("generosa nG8 mean75 @39", lambda p: p.st39["nG"] >= 8 and p.st39["meanG"] >= 75 and p.st39["n500"] == 0),
    ("generosa nG7 mean72 @39", lambda p: p.st39["nG"] >= 7 and p.st39["meanG"] >= 72 and p.st39["n500"] == 0),
]
for name, fn in rules:
    for label, split in [("train", train_p), ("holdout", test_p)]:
        y = [p.tiene_cola500 for p in split]
        m = metrics_binary(y, [fn(p) for p in split])
        print(name, label, "base", round(100*m["base"], 1), "prec", round(100*m["prec"], 1),
              "rec", round(100*m["rec"]), "tp", m["tp"], "fp", m["fp"])
