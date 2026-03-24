@echo off
setlocal

if not exist .venv (
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ScanDiego.spec del /q ScanDiego.spec

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name ScanDiego ^
  --add-data "data;data" ^
  --add-data "logs;logs" ^
  main.py

echo.
echo Fertig. Portable Build liegt in dist\ScanDiego\
endlocal
