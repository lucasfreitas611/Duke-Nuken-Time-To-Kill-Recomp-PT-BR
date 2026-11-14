@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_TEST_INPUT="
set "DNTTK_TEST_UNCAPTURED="
set "DNTTK_TEST_EDGES="
set "DNTTK_FRAME_INTERP="
set "DNTTK_LATE_CAMERA="
set "PSX_WIN_RENDER_TIMEOUT_MS="
if not exist "recomp\config" mkdir "recomp\config"
if not exist "recomp\config\mouse-smooth.json" if exist "recomp\config\player-profiles.json" copy /y "recomp\config\player-profiles.json" "recomp\config\mouse-smooth.json" >nul
call "%~dp0Jogar Duke TTK.cmd" --renderer opengl --internal-scale 2 --frame-rate auto --world-renderer polymorph --geometry-precision corrected --texture-precision corrected --settings-file "%~dp0recomp\config\mouse-smooth.json" --memcard-dir "%~dp0recomp\saves\mouse-comparison" %*
