@echo off
echo war3-coach 收集并分析 (自动找录像 -> 存U盘 -> 出摘要)
set "SELFDIR=%~dp0"
"%~dp0runtime\python.exe" "%~dp0app\collect.py"
pause
