@echo off
cd /d "%~dp0"

set DOCKER_EXE=C:\Program Files\Docker\Docker\resources\bin\docker.exe

if not exist "%DOCKER_EXE%" (
  echo Docker bulunamadi. Docker Desktop kurulumunu kontrol edin.
  pause
  exit /b 1
)

echo Docker Desktop baslatiliyor...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo Docker motoru bekleniyor...
for /l %%i in (1,1,40) do (
  "%DOCKER_EXE%" info >nul 2>&1
  if not errorlevel 1 goto docker_ready
  timeout /t 5 /nobreak >nul
)

echo Docker motoru hazir hale gelmedi. Docker Desktop ekraninda WSL kurulumu veya sozlesme onayi bekliyor olabilir.
pause
exit /b 1

:docker_ready
echo Docker hazir. Platform kuruluyor...
"%DOCKER_EXE%" compose up --build
