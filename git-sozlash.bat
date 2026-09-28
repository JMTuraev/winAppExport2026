@echo off
cd /d "%~dp0"
where git >nul 2>&1 || (echo Git topilmadi. https://git-scm.com/download/win dan o'rnating. & pause & exit /b 1)
if exist ".git" (echo Bu papka allaqachon git repo. git-push.bat / git-pull.bat dan foydalaning. & pause & exit /b 0)
set /p REPO=GitHub repo manzili (masalan https://github.com/JMTuraev/appwin.git): 
git init
git branch -M main
git remote add origin "%REPO%"
git add -A
git commit -m "AppWin: birinchi yuklash"
git push -u origin main
echo.
echo Tayyor. Keyingi safar: git-push.bat (o'zgarishlarni yuborish), git-pull.bat (olib kelish).
pause
