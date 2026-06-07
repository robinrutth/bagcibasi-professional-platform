@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo WSL ve Virtual Machine Platform aciliyor...
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto

echo.
echo WSL kurulumu baslatiliyor...
wsl --install --no-distribution
wsl --set-default-version 2

echo.
echo Islem tamamlandi. Windows yeniden baslatma isterse bilgisayari yeniden baslatin.
echo Yeniden baslattiktan sonra 02_PLATFORMU_BASLAT.bat dosyasini calistirin.
pause
