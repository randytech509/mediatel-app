@echo off
REM ═══════════════════════════════════════════════════════════════
REM  RANDROID — Mediatel Windows Build Script with Automated Tests
REM  RandyTech Solutions © 2024-2026
REM ═══════════════════════════════════════════════════════════════
echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║         RANDROID Mediatel — Windows Builder          ║
echo   ║               RandyTech Solutions                    ║
echo   ╚══════════════════════════════════════════════════════╝
echo.

REM 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+ from python.org
    echo         Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

REM 2. Run Test Suite
echo [1/5] Running automated unit tests...
cd /d "%~dp0"
python -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 (
    echo.
    echo [ERROR] Unit tests failed! Aborting build to ensure quality.
    pause
    exit /b 1
)
echo [OK] All tests passed.

REM 3. Install PyInstaller
echo.
echo [2/5] Ensuring PyInstaller is installed...
pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo [ERROR] Failed to install or upgrade PyInstaller.
    pause
    exit /b 1
)

REM 4. Build GUI
echo.
echo [3/5] Building Mediatel GUI (Mediatel.exe)...
cd /d "%~dp0mediatel-gui"
pyinstaller --clean --noconfirm mediatel_gui.spec
if errorlevel 1 (
    echo [ERROR] GUI build failed!
    pause
    exit /b 1
)
echo [OK] GUI built: mediatel-gui\dist\Mediatel.exe

REM 5. Build CLI
echo.
echo [4/5] Building Mediatel CLI (mediatel-cli.exe)...
cd /d "%~dp0mediatel-cli"
pyinstaller --clean --noconfirm mediatel_cli.spec
if errorlevel 1 (
    echo [ERROR] CLI build failed!
    pause
    exit /b 1
)
echo [OK] CLI built: mediatel-cli\dist\mediatel-cli.exe

REM 6. Collect & Smoke Test Outputs
echo.
echo [5/5] Collecting and testing executables...
cd /d "%~dp0"
if not exist "dist" mkdir dist
copy /Y "mediatel-gui\dist\Mediatel.exe" "dist\Mediatel.exe" >nul
copy /Y "mediatel-cli\dist\mediatel-cli.exe" "dist\mediatel-cli.exe" >nul

echo Testing CLI executable...
"dist\mediatel-cli.exe" --version
if errorlevel 1 (
    echo [WARNING] Smoke test of mediatel-cli.exe returned non-zero exit code.
) else (
    echo [OK] Smoke test passed!
)

echo.
echo   ╔══════════════════════════════════════════════════════╗
echo   ║                   BUILD COMPLETE!                    ║
echo   ╠══════════════════════════════════════════════════════╣
echo   ║                                                      ║
echo   ║   dist\Mediatel.exe      (GUI application)           ║
echo   ║   dist\mediatel-cli.exe  (Command-line tool)         ║
echo   ║                                                      ║
echo   ╚══════════════════════════════════════════════════════╝
echo.
pause
