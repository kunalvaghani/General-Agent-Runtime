@echo off
setlocal
set "GAR_DOUBLE_CLICK="
if "%~1"=="" set "GAR_DOUBLE_CLICK=1"
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "GAR_SKIP_SETUP="
if /I "%~1"=="--no-setup" (
  set "GAR_SKIP_SETUP=1"
  shift
)
if defined GAR_SKIP_SETUP goto ready
if exist ".venv\Scripts\python.exe" goto validate
py -3.11 -m venv .venv >nul 2>&1
if not errorlevel 1 goto validate
py -3 -c "import sys; sys.exit(sys.version_info < (3,11))" >nul 2>&1
if errorlevel 1 goto try_python
py -3 -m venv .venv
if errorlevel 1 goto failed
goto validate
:try_python
python -c "import sys; sys.exit(sys.version_info < (3,11))" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto failed
:validate
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3,11))"
if errorlevel 1 goto missing_python
echo Installing GAR and development dependencies...
".venv\Scripts\python.exe" -m pip install "setuptools>=68" wheel
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --no-build-isolation -e ".[dev]"
if errorlevel 1 goto failed
if not exist ".env" copy /Y ".env.example" ".env" >nul
:ready
if not exist ".venv\Scripts\python.exe" goto missing_python
set "PATH=%CD%\.venv\Scripts;%PATH%"
rem Stage 20: acceptance runs backend, lint, frontend and live Docker browser scenarios.
rem Default startup selects free API/UI ports and opens only its verified GAR instance.
rem GAR uses UI port 4317 instead of legacy 3000 to avoid cached Open WebUI pages.
rem Task pages include live bottom activity updates; no additional service is needed.
rem Use stop-gar.bat to stop tracked services and task containers.
rem Usage: run-gar.bat --no-setup plan TASK_ID (Ollama must already be running).
".venv\Scripts\python.exe" -m gar db-init
if errorlevel 1 goto failed
if /I "%~1"=="setup" goto success
if /I "%~1"=="check" goto checks
if /I "%~1"=="plan-help" goto plan_help
if /I "%~1"=="tools-help" goto tools_help
if /I "%~1"=="sandbox-setup" goto sandbox_setup
if /I "%~1"=="sandbox-check" goto sandbox_check
if /I "%~1"=="web-setup" goto web_setup
if /I "%~1"=="web" goto web
if /I "%~1"=="web-check" goto web_check
if /I "%~1"=="web-e2e" goto web_e2e
if /I "%~1"=="dev" goto dev
if /I "%~1"=="serve" goto serve
if /I "%~1"=="acceptance" goto acceptance
if "%~1"=="" goto dev
".venv\Scripts\python.exe" -m gar %1 %2 %3 %4 %5 %6 %7 %8 %9
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:serve
echo Starting GAR. Press Ctrl+C to stop. API documentation is available at /docs.
".venv\Scripts\python.exe" -m gar.launcher serve
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:plan_help
".venv\Scripts\python.exe" -m gar plan --help
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:tools_help
".venv\Scripts\python.exe" -m gar tool --help
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:sandbox_setup
echo Building GAR tool container. Docker must be running; this downloads build dependencies.
docker build -t gar-tools:stage4 -f docker/tools.Dockerfile docker
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:sandbox_check
".venv\Scripts\python.exe" -m pytest tests/e2e/test_live_tools.py --docker
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:web_setup
pushd web
call npm ci
set "GAR_EXIT=%ERRORLEVEL%"
popd
goto finish
:web
".venv\Scripts\python.exe" -m gar.launcher web
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:dev
if not exist "web\node_modules\next" (
  pushd web
  call npm ci
  if errorlevel 1 goto web_failed
  popd
)
".venv\Scripts\python.exe" -m gar.launcher
set "GAR_EXIT=%ERRORLEVEL%"
goto finish
:web_check
pushd web
call npm run typecheck
if errorlevel 1 goto web_failed
call npm test
if errorlevel 1 goto web_failed
call npm run build
set "GAR_EXIT=%ERRORLEVEL%"
popd
goto finish
:web_failed
popd
goto failed
:web_e2e
docker info >nul 2>&1
if errorlevel 1 goto docker_unavailable
docker image inspect gar-tools:stage4 >nul 2>&1
if errorlevel 1 goto docker_unavailable
set "GAR_BACKEND_URL=http://127.0.0.1:8100"
pushd web
call npm run build
if errorlevel 1 goto web_failed
call npm run test:e2e
set "GAR_EXIT=%ERRORLEVEL%"
popd
goto finish
:docker_unavailable
echo Docker engine or gar-tools:stage4 is unavailable. Start Docker and run sandbox-setup.
goto failed
:acceptance
docker info >nul 2>&1
if errorlevel 1 goto docker_unavailable
docker image inspect gar-tools:stage4 >nul 2>&1
if errorlevel 1 goto docker_unavailable
".venv\Scripts\python.exe" -m pytest --docker
if errorlevel 1 goto failed
ruff check .
if errorlevel 1 goto failed
ruff format --check .
if errorlevel 1 goto failed
pushd web
call npm run typecheck
if errorlevel 1 goto web_failed
call npm test
if errorlevel 1 goto web_failed
popd
goto web_e2e
:checks
".venv\Scripts\python.exe" -m pytest
if errorlevel 1 goto failed
ruff check .
if errorlevel 1 goto failed
ruff format --check .
if errorlevel 1 goto failed
:success
set "GAR_EXIT=0"
goto finish
:missing_python
echo GAR requires Python 3.11 or newer with the Windows Python launcher.
echo Install Python, or repair the existing .venv, then run this file again.
:failed
set "GAR_EXIT=1"
:finish
if defined GAR_DOUBLE_CLICK if not "%GAR_EXIT%"=="0" (
  echo GAR could not start. Review the error above. Close any older GAR window before retrying.
  pause
)
popd
exit /b %GAR_EXIT%
