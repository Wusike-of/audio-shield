@echo off
title AUDIO SHIELD - DSP PHASE CLOAKER ENGINE
color 0b
cls
echo ============================================================
echo       AUDIO SHIELD - DSP PHASE CLOAKER (STANDALONE)
echo ============================================================
echo [*] Iniciando servidor dedicado na porta 8090...
echo [*] Acesse no navegador: http://localhost:8090
echo ============================================================
start http://localhost:8090
python app.py
pause
