@echo off
title CookieRun Classic Bot - Create Desktop Shortcut
cd /d "%~dp0"
echo ========================================================
echo   CookieRun Classic Bot - Creating Desktop Shortcut...
echo ========================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$q=[char]34; $vbs='%~dp0START_BOT_NO_CONSOLE.vbs'; $ws=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $s=$ws.CreateShortcut((Join-Path $desktop 'CookieRun Classic Bot.lnk')); $s.TargetPath=(Join-Path $env:WINDIR 'System32\wscript.exe'); $s.Arguments=$q+$vbs+$q; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0src\bot_icon.ico'; $s.Description='CookieRun Classic Bot'; $s.Save()"
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] สร้างทางลัดบน Desktop เรียบร้อยแล้ว!
    echo ทางลัดจะเปิดเฉพาะหน้าต่างโปรแกรมบอท ไม่มีหน้าต่าง Command Line โผล่ออกมา
) else (
    echo [ERROR] ไม่สามารถสร้างทางลัดได้
)
echo.
pause