@echo off
cd /d "%~dp0"
chcp 65001 >nul
title AppWin - mustaqil qilish
set "SRC=%~dp0..\EksportMonitor"
echo.
echo AppWin ni EksportMonitor papkasidan mustaqil qilish (bir marta).
echo Ko'chiriladi: app\  python\  vendor\ (faqat yetishmaganlari)
echo Manba: %SRC%
echo.
if not exist "%SRC%\python\python.exe" (echo EksportMonitor\python topilmadi: %SRC% & pause & exit /b 1)
if not exist "%SRC%\app\server.py" (echo EksportMonitor\app topilmadi: %SRC% & pause & exit /b 1)
tasklist /fi "imagename eq pythonw.exe" 2>nul | find /i "pythonw.exe" >nul && (echo AVVAL Eksport Monitor oynasini yoping, keyin qayta ishga tushiring. & pause & exit /b 1)

echo [1/4] app\ ...
robocopy "%SRC%\app" "%~dp0app" /E /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo app ko'chirishda xato & pause & exit /b 1)
echo [2/4] python\ ...
robocopy "%SRC%\python" "%~dp0python" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo python ko'chirishda xato & pause & exit /b 1)
echo [3/4] vendor\ (openpyxl, xlrd ...) ...
robocopy "%SRC%\vendor" "%~dp0vendor" /E /XO /XN /XC /XD __pycache__ /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo vendor ko'chirishda xato & pause & exit /b 1)
echo [4/4] tozalash ...
if exist "appwin\static\shell.html" del /q "appwin\static\shell.html" "appwin\static\shell.css" "appwin\static\shell.js"
if exist "EksportMonitor2.exe" if exist "EksportMonitor.exe" del /q "EksportMonitor2.exe"

echo.
echo Tekshiruv ...
set "PYTHONPATH=%~dp0vendor;%~dp0"
set PYTHONUTF8=1
"%~dp0python\python.exe" -c "import app.server, appwin.server, openpyxl; from appwin import server as s; print('OK  data:', s.load_config()['data_path'])"
if errorlevel 1 (echo XATO: tekshiruv o'tmadi. Yuqoridagi matnni yuboring. & pause & exit /b 1)
echo.
echo TAYYOR. AppWin endi mustaqil: EksportMonitor.exe faqat AppWin ichidagi python va app dan foydalanadi.
echo Ma'lumotlar avvalgidek: %~dp0..\data
echo Keyin: git-push.bat (GitHub ga yuborish).
pause
