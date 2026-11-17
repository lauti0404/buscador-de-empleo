@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo Buscador de empleo
echo -------------------
echo Deja el programa listo en esta computadora.
echo.

if not exist "datos" mkdir "datos"
if not exist "datos\config.json" copy /Y "config.ejemplo.json" "datos\config.json" >nul
if not exist "datos\cv.txt" type nul > "datos\cv.txt"

call :buscar_python
if defined PYEXE goto acceso

echo No encontre Python. Lo instalo para este usuario.
echo Puede tardar unos minutos.
echo.
where winget >nul 2>&1
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  call :buscar_python
)
if defined PYEXE goto acceso

echo Bajando el instalador oficial de Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile (Join-Path $env:TEMP 'python-setup.exe')"
if errorlevel 1 (
  echo No pude bajar Python. Instala Python 3.12 desde https://www.python.org/downloads/ y marca Add python.exe to PATH. Despues volve a ejecutar este archivo.
  pause
  exit /b 1
)
echo Instalando Python. Acepta la ventana si Windows la muestra.
"%TEMP%\python-setup.exe" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 SimpleInstall=1
call :buscar_python
if not defined PYEXE (
  echo Python quedo instalado, pero esta ventana todavia no lo ve. Cerra todo, abri iniciar.bat y, si sigue fallando, reinicia la PC y volve a ejecutar instalar.bat.
  pause
  exit /b 1
)

:acceso
echo.
echo Python listo.
set "APPDIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Buscador de empleo.lnk')); $s.TargetPath=(Join-Path $env:APPDIR 'iniciar.bat'); $s.WorkingDirectory=$env:APPDIR.TrimEnd('\'); $s.Description='Buscador de empleo'; $s.Save()"
echo Acceso directo creado en el escritorio.
echo.
echo Se abre el buscador. Pega tu CV en la pantalla. Las claves de Adzuna y Jooble son opcionales y cada persona usa las suyas.
echo.
call "%~dp0iniciar.bat"
exit /b 0

:buscar_python
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
exit /b 0
