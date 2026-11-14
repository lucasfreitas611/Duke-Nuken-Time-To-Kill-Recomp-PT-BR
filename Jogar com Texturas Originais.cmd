@echo off
setlocal
cd /d "%~dp0"
set "DNTTK_TEXTURE_SAMPLE="
call "%~dp0Testar Mouse Suave.cmd" --texture-set original --antialias off %*
