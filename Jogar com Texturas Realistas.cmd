@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_TEXTURE_SAMPLE="
if not exist "recomp\analysis\level00-realistic-complete\pack.ttkpack" (
  echo Pacote local de texturas HD ausente. Prepare-o antes de jogar:
  echo python recomp\tools\local\build_complete_texture_pack.py
  pause
  exit /b 1
)
echo Texturas REALISTAS COMPLETAS e antisserrilhamento SUAVE.
call "%~dp0Testar Mouse Suave.cmd" --texture-set realistic --antialias smooth %*
