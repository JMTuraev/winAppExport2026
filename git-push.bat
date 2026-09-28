@echo off
cd /d "%~dp0"
git add -A
set /p MSG=Izoh (Enter = sana): 
if "%MSG%"=="" set MSG=AppWin yangilanish %date% %time%
git commit -m "%MSG%"
git push
pause
