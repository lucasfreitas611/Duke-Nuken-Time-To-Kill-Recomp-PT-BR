@echo off
setlocal
cd /d "%~dp0"
call "%~dp0Testar Artes da Campanha.cmd" --hud-hd --display borderless --window-width 1920 --widescreen 16:9 --vsync on %*
