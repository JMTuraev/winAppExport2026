@echo off
cd /d "%~dp0"
set "LEGACY=%~dp0..\EksportMonitor"
if not exist "%LEGACY%\python\python.exe" (
  echo EksportMonitor papkasi topilmadi: %LEGACY%
  echo AppWin papkasi "D:\2026 export\" ichida, EksportMonitor yonida turishi kerak.
  pause
  exit /b 1
)
set "PYTHONPATH=%LEGACY%\vendor;%LEGACY%;%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
title Eksport Monitor - AppWin
echo Eksport Monitor (AppWin) ishga tushmoqda...
"%LEGACY%\python\python.exe" -m appwin.server
if errorlevel 1 (
  echo.
  echo Xatolik yuz berdi. Yuqoridagi matnni nusxalab yuboring.
)
pause
