@echo off
echo war3-coach 查对手历史
set /p opp=对手游戏ID: 
"%~dp0runtime\python.exe" "%~dp0app\cli.py" lookup "%opp%"
pause
