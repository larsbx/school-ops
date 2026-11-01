@echo off
setlocal
py -3 "%~dp0wizard.py"
if errorlevel 1 (
  echo SchoolOps setup wizard could not start.
  echo Install Python 3 with Tkinter, then run wizard.py.
  pause
  exit /b 1
)
