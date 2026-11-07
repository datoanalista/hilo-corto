@echo off
cd /d "%~dp0"
title vigilar-servir · jokerbets-mesa
echo Watchdog servir.py — no cerrar esta ventana.
echo Log: %~dp0vigilar-servir.log
python vigilar-servir.py
pause
