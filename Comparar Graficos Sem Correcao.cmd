@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_DECAL_EXACT=0"
if not exist "recomp\config" mkdir "recomp\config"
if not exist "recomp\config\graphics-baseline.json" if exist "recomp\config\player-profiles.json" copy /y "recomp\config\player-profiles.json" "recomp\config\graphics-baseline.json" >nul
call "%~dp0Jogar Duke TTK.cmd" --renderer opengl --world-renderer polymorph --geometry-precision original --texture-precision original --frame-rate 60 --settings-file "%~dp0recomp\config\graphics-baseline.json" --memcard-dir "%~dp0recomp\saves\graphics-stage1" %*
