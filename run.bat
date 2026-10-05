@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_VERSION=2.2.2-cloud"

echo.
echo ==============================================
echo   Spectoom %APP_VERSION% - demarrage Windows
echo ==============================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
  echo ERREUR: Python 3 est requis.
  echo Installez Python depuis python.org en cochant "Add Python to PATH".
  pause
  exit /b 1
)

set "RUNNING_VERSION="
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "try { (Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/health' -TimeoutSec 1).version } catch { '' }"`) do set "RUNNING_VERSION=%%V"
if defined RUNNING_VERSION (
  if /I "%RUNNING_VERSION%"=="%APP_VERSION%" (
    echo Spectoom %APP_VERSION% est deja demarre.
    start "" "http://127.0.0.1:8080/?v=%APP_VERSION%"
    exit /b 0
  )
  echo ERREUR: une ancienne version ^(%RUNNING_VERSION%^) utilise encore le port 8080.
  echo Fermez sa fenetre noire, puis relancez ce fichier run.bat.
  echo Cette protection evite d'ouvrir par erreur l'ancienne interface PVS.
  pause
  exit /b 2
)

set "PORT_BUSY="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',8080); 'yes' } catch { '' } finally { $c.Dispose() }"`) do set "PORT_BUSY=%%P"
if defined PORT_BUSY (
  echo ERREUR: le port 8080 est deja utilise par un autre programme.
  echo Fermez ce programme ou l'ancienne application avant de relancer Spectoom.
  pause
  exit /b 3
)

echo Verification des dependances Python...
%PYTHON_CMD% -c "import PIL, imageio_ffmpeg, mutagen" >nul 2>&1
if errorlevel 1 (
  echo Installation automatique de Pillow, FFmpeg integre et Mutagen...
  %PYTHON_CMD% -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo.
    echo ERREUR: les dependances n'ont pas pu etre installees.
    echo Verifiez votre connexion Internet puis relancez run.bat.
    pause
    exit /b 1
  )
)

%PYTHON_CMD% -c "import PIL, imageio_ffmpeg, mutagen; print('Dependances OK - FFmpeg: ' + imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 (
  echo ERREUR: le moteur audio/video n'est pas disponible.
  pause
  exit /b 1
)

echo.
echo Demarrage de Spectoom %APP_VERSION% sur http://127.0.0.1:8080
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_when_ready.ps1" -ExpectedVersion "%APP_VERSION%"
%PYTHON_CMD% "%~dp0server.py"

if errorlevel 1 (
  echo.
  echo Le serveur s'est arrete avec une erreur.
  pause
)
endlocal
