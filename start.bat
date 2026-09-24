@echo off
title RPG Fitness Bot
color 0A

@echo off
echo ==============================================
echo  Spor Botu Baslatiliyor...
echo ==============================================

echo Gerekli kutuphaneler kontrol ediliyor...
pip install pyTelegramBotAPI google-generativeai matplotlib numpy >nul 2>&1

echo.
cd /d "%~dp0\Bot"

:loop
echo Bot calistiriliyor... (Kapatmak icin bu pencereyi kapatin)
python bot.py
echo Bot cÃ¶ktÃ¼ veya durdu. 5 saniye icinde yeniden baslatiliyor...
timeout /t 5 /nobreak >nul
goto loop
