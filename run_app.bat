@echo off
cd /d "%~dp0"
title Chuyen Ban Ve Sang 3D - AI Gemini Free

python -c "import PySide6, PIL, numpy, trimesh, shapely, mapbox_earcut, manifold3d" 2>nul
if errorlevel 1 (
    echo Dang cai dat thu vien can thiet, vui long cho...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Cai dat that bai. Hay cai Python 3.10+ tu python.org va tick "Add Python to PATH".
        pause
        exit /b 1
    )
)

start "" pythonw gui.py
exit
