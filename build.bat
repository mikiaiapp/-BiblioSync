@echo off
echo ========================================================
echo Building BiblioSync with PyInstaller
echo ========================================================

:: Dynamic retrieval of customtkinter package location
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))" 2^>nul') do set CTK_PATH=%%i

if "%CTK_PATH%"=="" (
    echo ERROR: customtkinter is not installed in the active Python environment.
    echo Running: pip install -r requirements.txt
    pip install -r requirements.txt
    for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))" 2^>nul') do set CTK_PATH=%%i
)

if "%CTK_PATH%"=="" (
    echo ERROR: Could not resolve customtkinter path even after pip install.
    pause
    exit /b 1
)

echo Found CustomTkinter assets at: %CTK_PATH%
echo Initiating PyInstaller build...

pyinstaller --noconfirm --onedir --windowed --name "BiblioSync" --add-data "%CTK_PATH%;customtkinter/" src/main.py

echo ========================================================
echo Build process finished! Check the dist/ directory.
echo ========================================================
pause
