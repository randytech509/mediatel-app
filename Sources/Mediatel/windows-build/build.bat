@echo off
REM ═══════════════════════════════════════════════════════════════
REM  RANDROID — Mediatel Windows Build Script
REM  Builds both GUI (Mediatel.exe) and CLI (mediatel-cli.exe)
REM ═══════════════════════════════════════════════════════════════
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   RANDROID Mediatel — Windows Builder    ║
echo   ║         RandyTech Solutions              ║
echo   ╚══════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+ from python.org
    echo         Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

REM Install PyInstaller
echo [1/4] Installing PyInstaller...
pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

REM Build GUI
echo.
echo [2/4] Building Mediatel GUI (Mediatel.exe)...
cd /d "%~dp0mediatel-gui"
pyinstaller --onefile --windowed --name "Mediatel" ^
    --exclude-module matplotlib --exclude-module numpy --exclude-module pandas ^
    --exclude-module scipy --exclude-module PIL --exclude-module cv2 ^
    mediatel_gui.py
if errorlevel 1 (
    echo [ERROR] GUI build failed!
    pause
    exit /b 1
)
echo [OK] GUI built: mediatel-gui\dist\Mediatel.exe

REM Build CLI
echo.
echo [3/4] Building Mediatel CLI (mediatel-cli.exe)...
cd /d "%~dp0mediatel-cli"
pyinstaller --onefile --console --name "mediatel-cli" ^
    --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy ^
    --exclude-module pandas --exclude-module scipy --exclude-module PIL ^
    mediatel_cli.py
if errorlevel 1 (
    echo [ERROR] CLI build failed!
    pause
    exit /b 1
)
echo [OK] CLI built: mediatel-cli\dist\mediatel-cli.exe

REM Collect outputs
echo.
echo [4/4] Collecting executables...
cd /d "%~dp0"
if not exist "dist" mkdir dist
copy /Y "mediatel-gui\dist\Mediatel.exe" "dist\Mediatel.exe" >nul
copy /Y "mediatel-cli\dist\mediatel-cli.exe" "dist\mediatel-cli.exe" >nul

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║           BUILD COMPLETE!                ║
echo   ╠══════════════════════════════════════════╣
echo   ║                                          ║
echo   ║   dist\Mediatel.exe      (GUI app)       ║
echo   ║   dist\mediatel-cli.exe  (CLI tool)      ║
echo   ║                                          ║
echo   ╚══════════════════════════════════════════╝
echo.
pause
