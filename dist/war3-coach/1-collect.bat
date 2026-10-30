@echo off
echo war3-coach 收集并分析 (自动找录像 -> 出摘要 -> 打包发邮箱)
set "SELFDIR=%~dp0"
"%~dp0runtime\python.exe" "%~dp0app\collect.py"
pause
