# CameraGuard 便携版打包说明

目标效果：客户拿到 `release/CameraGuard` 文件夹后，解压并双击 `CameraGuard.exe` 即可使用。

## 在 Windows 上生成 EXE

1. 安装 Python 3.10 或 3.11，安装时勾选 `Add Python to PATH`。
2. 解压本工程。
3. 双击 `一键生成便携版.bat`。
4. 生成完成后，把 `release/CameraGuard` 整个文件夹发给客户。

客户只需要运行：

```text
CameraGuard.exe
```

## 注意

- 当前包里需要包含 `yolov8n.onnx`，运行时不需要联网下载模型。
- 程序默认后台运行，右下角托盘图标可以打开预警看板。
- 配置、日志、截图均在 exe 同级目录下，便于离线部署和拷贝。
