@echo off
rem NFS SE Enhanced patcher - launcher for Windows.
rem The first run sets up a private Python environment in .venv next to this file (needs internet,
rem about 100 MB); nothing is installed system-wide. Delete the folder to remove everything.
rem Usage: double-click it, drag the game folder onto it, or: nfsse-patcher.bat "C:\NFSSE" [options]
setlocal
set "DIR=%~dp0"
set "VENV=%DIR%.venv"
if exist "%VENV%\installed.ok" goto run

set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

echo First run: setting up a Python environment in "%VENV%"
echo (downloads numpy, scipy and Pillow, about 100 MB; only needed once)
if exist "%VENV%" rmdir /s /q "%VENV%"
%PY% -m venv "%VENV%" || goto venvfail
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r "%DIR%requirements.txt" || goto pipfail
echo ok> "%VENV%\installed.ok"
echo.

:run
"%VENV%\Scripts\python.exe" "%DIR%patcher.py" %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%

:nopython
echo The patcher needs Python 3.9 or newer.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH"
echo in the installer, then run this file again.
goto fail

:venvfail
echo Could not create the Python environment.
goto fail

:pipfail
echo Installing the Python packages failed (internet connection?). Run this file again to retry.
goto fail

:fail
echo.
pause
exit /b 1
