@echo off
title RPG Fitness Bot
color 0A

@echo off
echo ==============================================
echo  Spor Botu Baslatiliyor...
echo ==============================================

echo Gerekli kutuphaneler kontrol ediliyor...
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
	echo Proje Python ortami bulunamadi.
	echo Once su komutu calistirin: python -m venv .venv
	pause
	exit /b 1
)

echo.
cd /d "%~dp0"

:loop
echo Bot calistiriliyor... (Kapatmak icin bu pencereyi kapatin)
"%PYTHON%" bot.py
echo Bot cÃ¶ktÃ¼ veya durdu. 5 saniye icinde yeniden baslatiliyor...
timeout /t 5 /nobreak >nul
goto loop
