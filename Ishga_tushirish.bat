@echo off
cd /d "%~dp0"
set "PY=%~dp0python\python.exe"
set "PYTHONPATH=%~dp0vendor;%~dp0"
if not exist "%PY%" (
  set "LEGACY=%~dp0..\EksportMonitor"
  set "PY=%~dp0..\EksportMonitor\python\python.exe"
  set "PYTHONPATH=%~dp0vendor;%~dp0..\EksportMonitor\vendor;%~dp0..\EksportMonitor;%~dp0"
)
if not exist "%PY%" (
  echo Python topilmadi: %~dp0python\python.exe
  echo Mustaqil_qilish.bat ni bir marta ishga tushiring.
  pause
  exit /b 1
)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
title Eksport Monitor - AppWin
echo Eksport Monitor (AppWin) ishga tushmoqda...
"%PY%" -m appwin.server
if errorlevel 1 (
  echo.
  echo Xatolik yuz berdi. Yuqoridagi matnni nusxalab yuboring.
)
pause
