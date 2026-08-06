@echo off
REM Админ-панель на ЭТОМ ноутбуке: локальный прокси + обычный браузер
setlocal
cd /d "%~dp0"

if "%ROBOT_API%"=="" set ROBOT_API=http://10.255.210.201:8765
if "%ADMIN_PORT%"=="" set ADMIN_PORT=8878

where python >nul 2>&1
if errorlevel 1 (
  echo [admin] Python не найден. Открываю прямую ссылку на робота...
  start "" "%ROBOT_API%/admin"
  start "" "%ROBOT_API%/map"
  goto :eof
)

echo [admin] Робот: %ROBOT_API%
echo [admin] Локально: http://127.0.0.1:%ADMIN_PORT%/admin
echo [admin] Карта:    http://127.0.0.1:%ADMIN_PORT%/map
echo [admin] Остановка: Ctrl+C в этом окне
set ADMIN_OPEN=1
python "%~dp0admin_local_server.py"
endlocal
