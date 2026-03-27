@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_desktop_shortcut.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Desktop shortcut installation failed. Review the error above, then press any key to close.
  pause >nul
)
endlocal & exit /b %EXIT_CODE%
