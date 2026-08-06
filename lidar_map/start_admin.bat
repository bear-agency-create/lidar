@echo off
REM Полная админ-панель робота (все API + карта + киоск)
setlocal
cd /d "%~dp0"

if "%ROBOT_API%"=="" set ROBOT_API=http://10.255.210.201:8765
set PANEL_URL=%ROBOT_API%/admin

echo [admin] Открываю %PANEL_URL%

where msedge >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" msedge --app="%PANEL_URL%"
  goto :done
)
where chrome >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" chrome --app="%PANEL_URL%"
  goto :done
)

start "" "%PANEL_URL%"

:done
echo [admin] Простой режим по умолчанию, Полный — по кнопке
echo URL: %PANEL_URL%
endlocal
