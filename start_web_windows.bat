@echo off
rem MarKusSXCH TagStudio - neue Oberflaeche starten (installiert pywebview beim ersten Mal)
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -c "import webview" >nul 2>nul
if errorlevel 1 (
  echo pywebview wird installiert ^(einmalig^) ...
  %PY% -m pip install --user pywebview
  if errorlevel 1 (
    echo Installation fehlgeschlagen - die Oberflaeche oeffnet sich im Browser.
    %PY% tagstudio_web.py --browser %*
    exit /b
  )
)
where pyw >nul 2>nul && (start "" pyw -3 tagstudio_web.py %* & exit /b)
where pythonw >nul 2>nul && (start "" pythonw tagstudio_web.py %* & exit /b)
%PY% tagstudio_web.py %*
if errorlevel 1 pause
