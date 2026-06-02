@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set LOG=%~dp0build_log.txt

echo ========================================== > "%LOG%"
echo CameraGuard build log >> "%LOG%"
echo Started: %date% %time% >> "%LOG%"
echo Folder: %cd% >> "%LOG%"
echo ========================================== >> "%LOG%"
echo.
echo CameraGuard 便携版 EXE 生成工具
echo 运行日志会保存到：build_log.txt
echo.

if not exist main.py (
  echo [错误] 当前目录没有 main.py。请先完整解压 zip 后，再运行 build_exe.cmd。
  echo ERROR: main.py not found. >> "%LOG%"
  goto failed
)

if not exist yolov8n.onnx (
  echo [错误] 当前目录没有 yolov8n.onnx。请把 ONNX 模型文件放到当前目录后再打包。
  echo ERROR: yolov8n.onnx not found. >> "%LOG%"
  goto failed
)

where py >> "%LOG%" 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py -3
) else (
    where python >> "%LOG%" 2>&1
    if %errorlevel%==0 (
        set PYTHON_CMD=python
    ) else (
        echo [错误] 未检测到 Python。请先安装 Python 3.10 或 3.11，并勾选 Add Python to PATH。
        echo ERROR: Python not found. >> "%LOG%"
        goto failed
    )
)

echo [检查] Python 版本...
echo ---- Python version ---- >> "%LOG%"
%PYTHON_CMD% --version >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed

echo [1/5] 创建本地虚拟环境...
echo ---- Create venv ---- >> "%LOG%"
%PYTHON_CMD% -m venv .venv >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed

call ".venv\Scripts\activate.bat"
if %errorlevel% neq 0 goto failed

echo [2/5] 升级 pip...
echo ---- Upgrade pip ---- >> "%LOG%"
python -m pip install --upgrade pip >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed

echo [3/5] 安装依赖，首次可能需要几分钟...
echo ---- Install requirements ---- >> "%LOG%"
pip install -r requirements.txt >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed
pip install pyinstaller >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed

echo [4/5] 生成 Windows EXE...
echo ---- PyInstaller ---- >> "%LOG%"
pyinstaller --noconfirm main.spec >> "%LOG%" 2>&1
if %errorlevel% neq 0 goto failed

if not exist "dist\CameraGuard\CameraGuard.exe" (
  echo [错误] PyInstaller 没有生成 dist\CameraGuard\CameraGuard.exe。
  echo ERROR: exe not found after pyinstaller. >> "%LOG%"
  goto failed
)

echo [5/5] 整理便携版目录...
echo ---- Copy release files ---- >> "%LOG%"
if exist release rmdir /s /q release >> "%LOG%" 2>&1
mkdir release >> "%LOG%" 2>&1
xcopy /e /i /y "dist\CameraGuard" "release\CameraGuard" >> "%LOG%" 2>&1
copy /y "config.yaml" "release\CameraGuard\config.yaml" >> "%LOG%" 2>&1
copy /y "yolov8n.onnx" "release\CameraGuard\yolov8n.onnx" >> "%LOG%" 2>&1
if not exist "release\CameraGuard\evidence" mkdir "release\CameraGuard\evidence" >> "%LOG%" 2>&1
if not exist "release\CameraGuard\logs" mkdir "release\CameraGuard\logs" >> "%LOG%" 2>&1
copy /y "使用说明.txt" "release\CameraGuard\使用说明.txt" >> "%LOG%" 2>&1

echo.
echo ==========================================
echo 生成完成！
echo 便携版目录：release\CameraGuard
echo 运行程序：release\CameraGuard\CameraGuard.exe
echo ==========================================
echo SUCCESS >> "%LOG%"
pause
exit /b 0

:failed
echo.
echo ==========================================
echo 生成失败。
echo 请打开当前文件夹里的 build_log.txt，把最后 30 行截图/发给我。
echo 常见原因：没有安装 Python、没有完整解压、网络无法安装依赖、杀毒软件拦截。
echo ==========================================
echo FAILED >> "%LOG%"
pause
exit /b 1
