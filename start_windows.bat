@echo off
rem MarKusSXCH TagStudio starten (ohne Konsolenfenster, falls moeglich)
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 tagstudio.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw tagstudio.py & exit /b)
python tagstudio.py
if errorlevel 1 pause
