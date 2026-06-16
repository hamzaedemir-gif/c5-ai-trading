@echo off
REM ====================================================================
REM  C5 Live Paper Trading — one-click launcher (Windows)
REM  Double-click this file to start C5. Paper trading only.
REM ====================================================================
setlocal
cd /d "%~dp0"

echo(
echo  ==== C5 Live Paper Trading ====
echo  (Paper trading only - no real orders, no real money)
echo(

REM 1) Create the virtual environment if it does not exist.
if not exist "venv\Scripts\python.exe" (
    echo  Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: could not create venv. Is Python installed and on PATH?
        pause
        exit /b 1
    )
)

REM 2) Activate it.
call "venv\Scripts\activate.bat"

REM 3) Install / update requirements.
echo  Installing requirements (first run may take a minute)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

REM 4) Open the browser at localhost:8501 after a short delay,
REM    then launch Streamlit in this window.
start "" cmd /c "timeout /t 5 >nul & start "" http://localhost:8501"

echo(
echo  Launching C5 at http://localhost:8501  (close this window to stop)
echo(
streamlit run app.py --server.port 8501 --server.address localhost --server.headless true

endlocal
