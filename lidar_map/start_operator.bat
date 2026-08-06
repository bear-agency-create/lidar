@echo off
REM Операторская панель на ноутбуке (карта как на сайте)
setlocal
cd /d "%~dp0"

if "%ROBOT_API%"=="" set ROBOT_API=http://10.255.210.201:8765
set PANEL_URL=%ROBOT_API%/operator-panel

echo [operator] Открываю %PANEL_URL%

REM Предпочитаем Edge/Chrome в режиме приложения (как отдельное окно)
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

REM запасной вариант — браузер по умолчанию
start "" "%PANEL_URL%"

:done
echo.
echo Вкладки: Состояние / Логи / Тесты / Карта лидара
echo Карта = тот же интерактив, что на сайте.
endlocal
