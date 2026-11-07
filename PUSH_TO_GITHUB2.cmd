@echo off
rem Pushes every file in this folder (and its subfolders) to the AlundraMaker repository on
rem GitHub, including files .gitignore would skip. GitHub's copy is replaced by this folder.
cd /d "%~dp0"
if not exist .git (
  git init -b main || goto fail
  git remote add origin https://github.com/SkyPilotSamurai/Alundra-NTSC-Decomp.git || goto fail
)
git add -A --force . || goto fail
git commit -m "Alundra PC"
git push --force -u origin main || goto fail
echo.
echo Pushed.
pause
exit /b 0
:fail
echo.
echo Push failed - see above.
pause
exit /b 1
