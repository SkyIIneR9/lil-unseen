@echo off
setlocal
cd /d "%~dp0"
echo Close the game before exporting. / Zakroyte igru pered eksportom.
choice /C ER /N /M "Report language: [E] English / [R] Russkiy: "
if errorlevel 2 (set "LIL_UI_LANGUAGE=ru") else (set "LIL_UI_LANGUAGE=en")
where py >nul 2>nul
if errorlevel 1 (
    python -X utf8 export_unseen.py --ui-language %LIL_UI_LANGUAGE%
) else (
    py -3 -X utf8 export_unseen.py --ui-language %LIL_UI_LANGUAGE%
)
if errorlevel 1 (
    echo Export failed. See the error above and README troubleshooting.
    pause
    exit /b 1
)
start "" "%~dp0output\unseen.html"
