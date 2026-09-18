@echo off
rem ============================================================
rem  BF2 dedicated server  --  Dalian_Plant, conquest 64
rem
rem  TWO things learned the hard way; do not "fix" them:
rem
rem  1) Do NOT quote the paths. This engine's command line parser does not
rem     understand quotes, so "+config "C:\path with space\x.con"" makes it
rem     look for a file called  "C:\path  and it reports
rem         "No maps in maplist. Please add atleast one map"
rem     Paths must be bare, which is why we cd into the install dir first.
rem
rem  2) There is no +modPath switch in bf2_w32ded.exe (verified: the string
rem     does not exist in the binary). Setting %CD% to the install root is
rem     what makes it find mods/bf2, and it makes Admin/default.py's
rem     relative open("admin/default.cfg") resolve too.
rem
rem  Output is mirrored to server-console.log.
rem ============================================================

setlocal
cd /d "%~dp0"
set "BASE=%CD%"
set "LOG=%BASE%\server-console.log"

echo Working directory: %BASE%
echo.

if not exist "bf2_w32ded.exe" (
  echo [ERROR] bf2_w32ded.exe NOT FOUND in %BASE%
  pause
  exit /b 1
)

echo Files check:
if exist "mods\bf2\Settings\ServerSettings.con" (echo   [ok] ServerSettings.con) else (echo   [MISSING] ServerSettings.con)
if exist "mods\bf2\Settings\maplist.con"        (echo   [ok] maplist.con)        else (echo   [MISSING] maplist.con)
if exist "Admin\default.cfg"                    (echo   [ok] Admin\default.cfg)  else (echo   [MISSING] Admin\default.cfg)
if exist "Admin\standard_admin\spawn.py"        (echo   [ok] spawn.py)           else (echo   [MISSING] spawn.py)
if exist "Admin\standard_admin\__init__.py"     (echo   [ok] __init__.py)        else (echo   [MISSING] __init__.py)
echo.
echo maplist.con contents:
type "mods\bf2\Settings\maplist.con"
echo.
echo RCON password is: deepseek
echo In game, press the console key and type:   rcon login deepseek
echo.
echo Starting server... (this window must stay open)
echo ============================================================
echo.

REM bare relative paths, no quotes, cwd = install root
bf2_w32ded.exe +config mods/bf2/Settings/ServerSettings.con +mapList mods/bf2/Settings/maplist.con > "%LOG%" 2>&1

echo.
echo ============================================================
echo Server exited. Output saved to: %LOG%
echo.
echo ---- last 50 lines ----
powershell -NoProfile -Command "if (Test-Path '%LOG%') { Get-Content '%LOG%' -Tail 50 }"
echo ---------------------------------------------
echo.
pause
