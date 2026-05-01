@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
py -m openmenu_gdemu_manager
echo.
echo App cerrada. Si hubo error, revisa openmenu_gdemu_manager.log
pause
