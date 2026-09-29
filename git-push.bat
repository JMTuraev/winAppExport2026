@echo off
cd /d "%~dp0"
rem Git muallifi (bir marta, faqat shu repo uchun), aks holda commit ishlamaydi
git config user.email >NUL 2>&1 || git config user.email "jafaralituraev@gmail.com"
git config user.name >NUL 2>&1 || git config user.name "JMTuraev"
git add -A
set /p MSG=Izoh (Enter = sana): 
if "%MSG%"=="" set MSG=AppWin yangilanish %date% %time%
git commit -m "%MSG%"
git push
pause
