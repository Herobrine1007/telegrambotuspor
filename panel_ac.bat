@echo off
echo =========================================
echo  Savasci Analiz Paneli Baslatiliyor...
echo =========================================
echo Tarayicida localhost:8080 aciliyor...
echo.
cd /d "%~dp0"
start http://localhost:8080/Web/analiz.html
python -m http.server 8080
