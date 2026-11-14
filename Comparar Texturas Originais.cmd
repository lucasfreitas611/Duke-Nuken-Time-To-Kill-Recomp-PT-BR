@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_TEXTURE_SAMPLE="
if not exist "recomp\config\remaster-pilot.json" if exist "recomp\config\mouse-smooth.json" copy /y "recomp\config\mouse-smooth.json" "recomp\config\remaster-pilot.json" >nul
call "%~dp0Testar Mouse Suave.cmd" --settings-file "%~dp0recomp\config\remaster-pilot.json" %*
