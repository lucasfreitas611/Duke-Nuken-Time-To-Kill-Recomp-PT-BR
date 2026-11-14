@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_TEST_INPUT="
set "DNTTK_TEST_UNCAPTURED="
set "DNTTK_TEST_EDGES="
if not exist "recomp\config" mkdir "recomp\config"
if not exist "recomp\config\mouse-original.json" if exist "recomp\config\player-profiles.json" copy /y "recomp\config\player-profiles.json" "recomp\config\mouse-original.json" >nul
call "%~dp0Jogar Duke TTK.cmd" --renderer opengl --internal-scale 2 --frame-rate 60 --world-renderer polymorph --geometry-precision corrected --texture-precision corrected --settings-file "%~dp0recomp\config\mouse-original.json" --memcard-dir "%~dp0recomp\saves\mouse-comparison" %*
