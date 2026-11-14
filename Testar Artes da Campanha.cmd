@echo off
setlocal
cd /d "%~dp0"
if not exist "recomp\analysis\level00-realistic-complete\pack.ttkpack" (
    echo Pacote da primeira fase ausente. Execute build_complete_texture_pack.py.
    pause
    exit /b 1
)
if not exist "recomp\analysis\campaign-art\packs\01\pack.ttkpack" (
    echo Pacotes da campanha ausentes. Execute build_campaign_texture_bank.py para cada banco.
    pause
    exit /b 1
)
call "%~dp0Testar Mouse Suave.cmd" --texture-set realistic --antialias smooth --campaign-art-preview %*
