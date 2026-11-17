@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYEXE="
for %%P in (
  "%LocalAppData%\Programs\Python\Python313\python.exe"
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%LocalAppData%\Programs\Python\Python311\python.exe"
  "%ProgramFiles%\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
) do (
  if not defined PYEXE if exist %%~P set "PYEXE=%%~P"
)
if not defined PYEXE (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 if not defined PYEXE set "PYEXE=%%P"
  )
)
if not defined PYEXE (
  echo Falta Python. Ejecuta instalar.bat en esta misma carpeta.
  pause
  exit /b 1
)
"%PYEXE%" -u "%~dp0app.py"
if errorlevel 1 pause
