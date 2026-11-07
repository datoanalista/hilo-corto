#!/usr/bin/env python3
"""
Watchdog de servir.py (Windows).

Arranca servir.py, hace ping a http://127.0.0.1:PORT/api/sesion y, si
falla N veces seguidas o el proceso muere, lo mata y lo vuelve a levantar.

Uso (desde la carpeta del proyecto):
  python vigilar-servir.py

Variables opcionales:
  PORT=8765
  VIGILAR_INTERVALO_S=8
  VIGILAR_FALLOS=3
  VIGILAR_COOLDOWN_S=15
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVIR = ROOT / "servir.py"
LOG = ROOT / "vigilar-servir.log"

PORT = int(os.environ.get("PORT", "8765"))
INTERVALO_S = float(os.environ.get("VIGILAR_INTERVALO_S", "10"))
FALLOS_MAX = int(os.environ.get("VIGILAR_FALLOS", "5"))
COOLDOWN_S = float(os.environ.get("VIGILAR_COOLDOWN_S", "20"))
URL = f"http://127.0.0.1:{PORT}/api/sesion"
# Timeout holgado: con túnel/remoto servir a veces tarda >5s sin estar muerto.
TIMEOUT_S = float(os.environ.get("VIGILAR_TIMEOUT_S", "12"))


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def health_ok() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(URL, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            code = getattr(r, "status", None) or r.getcode()
            if code == 200:
                return True, f"HTTP {code}"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        # 401/403 igual prueba que el listener acepta
        if e.code in (401, 403, 404):
            return True, f"HTTP {e.code} (listener vivo)"
        return False, f"HTTPError {e.code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def matar_solo_servir(pid: int) -> None:
    """Mata SOLO el proceso servir.py.

    Nunca usar taskkill /T: la extracción Node + Chrome Playwright son hijos
    de servir; /T cerraba las 3 mesas al reiniciar el API.
    """
    if pid <= 0:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def liberar_puerto() -> None:
    """Último recurso en Win si quedó un servir zombie en PORT (sin /T)."""
    if sys.platform != "win32":
        return
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return
    needle = f":{PORT}"
    pids: set[int] = set()
    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    for pid in pids:
        if pid == os.getpid():
            continue
        log(f"Liberando PID {pid} en puerto {PORT} (solo ese PID, sin árbol)")
        matar_solo_servir(pid)


def arrancar() -> subprocess.Popen:
    if not SERVIR.is_file():
        raise SystemExit(f"No está {SERVIR}")
    env = os.environ.copy()
    env.setdefault("PORT", str(PORT))
    creation = 0
    kwargs: dict = {
        "cwd": str(ROOT),
        "env": env,
        "stdout": None,
        "stderr": None,
    }
    if sys.platform == "win32":
        creation = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        kwargs["creationflags"] = creation
    else:
        kwargs["start_new_session"] = True
    log(f"Arrancando: {sys.executable} {SERVIR.name} · puerto {PORT}")
    return subprocess.Popen([sys.executable, str(SERVIR)], **kwargs)


def main() -> None:
    log(
        f"Watchdog ON · ping {URL} cada {INTERVALO_S}s · "
        f"reinicio tras {FALLOS_MAX} fallos"
    )
    proc: subprocess.Popen | None = None
    fallos = 0
    try:
        while True:
            if proc is None or proc.poll() is not None:
                code = None if proc is None else proc.poll()
                if proc is not None:
                    log(f"servir.py terminó (exit={code}) · reinicio (Chrome/extracción intactos)")
                    matar_solo_servir(proc.pid)
                    liberar_puerto()
                    time.sleep(COOLDOWN_S)
                proc = arrancar()
                fallos = 0
                time.sleep(min(5.0, COOLDOWN_S))
                continue

            ok, detalle = health_ok()
            if ok:
                if fallos:
                    log(f"OK de nuevo tras {fallos} fallo(s) · {detalle}")
                fallos = 0
            else:
                fallos += 1
                log(f"Fallo health {fallos}/{FALLOS_MAX} · {detalle}")
                if fallos >= FALLOS_MAX:
                    log(
                        "Reiniciando SOLO servir.py (sin matar extracción/Chrome) · "
                        + detalle
                    )
                    matar_solo_servir(proc.pid)
                    liberar_puerto()
                    proc = None
                    fallos = 0
                    time.sleep(COOLDOWN_S)
                    continue

            time.sleep(INTERVALO_S)
    except KeyboardInterrupt:
        log("Watchdog detenido (Ctrl+C)")
    finally:
        if proc is not None and proc.poll() is None:
            log(f"Cerrando solo servir.py pid={proc.pid} (extracción no se toca)")
            matar_solo_servir(proc.pid)


if __name__ == "__main__":
    main()
