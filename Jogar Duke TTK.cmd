@echo off
setlocal
cd /d "%~dp0"
if not defined DNTTK_LANGUAGE set "DNTTK_LANGUAGE=pt-BR"
if defined RETCOMM_TOOLCHAIN_DIR set "PATH=%RETCOMM_TOOLCHAIN_DIR%\bin;%PATH%"
if exist "%USERPROFILE%\.local\share\retcomm\toolchains\cmake-clang-v1\latest\bin\clang.exe" set "PATH=%USERPROFILE%\.local\share\retcomm\toolchains\cmake-clang-v1\latest\bin;%PATH%"
if not exist "recomp\build-local\Duke_Nukem__Time_to_Kill_Recompiled.exe" (
    echo Compile o jogo primeiro. Consulte README.md.
    pause
    exit /b 1
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" recomp\tools\local\run.py %*
) else if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" recomp\tools\local\run.py %*
) else (
    python recomp\tools\local\run.py %*
)
if errorlevel 1 pause
