@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Conversor AFD

echo Conferindo bibliotecas...
py -3 -m pip install -q -r requirements.txt
if errorlevel 1 python -m pip install -q -r requirements.txt

echo Abrindo no navegador...
py -3 -m streamlit run streamlit_app.py --server.headless false
if errorlevel 1 python -m streamlit run streamlit_app.py --server.headless false
if errorlevel 1 (
  echo.
  echo Nao consegui abrir. Confira se o Python esta instalado.
  pause
)
