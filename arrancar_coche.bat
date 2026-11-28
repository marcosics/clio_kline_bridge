@echo off
rem Modo coche: registro continuo + IA. Conecta antes el portatil a la zona wifi del movil.
rem Con el cable ELM cambia bridge:auto por elm:COM5 (tu puerto).
cd /d %~dp0
start "" http://localhost:8080
python tools\clio_web.py --lan --auto bridge:auto --drive --otras "28:A0;26:80" --ia-auto 30
pause
