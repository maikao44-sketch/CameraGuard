# CameraGuard 内网摄像头安全监管系统

这是一个 Windows/内网单机版 MVP：通过电脑摄像头实时识别“有人手持手机拍摄”的疑似行为，自动截图留证、记录日志，并预留内网报送接口。

## 功能

- 摄像头画面实时检测：person / cell phone
- 疑似手机拍摄行为判断
- 截图留证
- JSONL 事件日志
- 可选内网 HTTP 报送
- 可选摄像头占用进程审计（Windows 下更准确）

## 安装

```bash
pip install -r requirements.txt
```

默认使用 ONNX Runtime 加载 `yolov8n.onnx`。内网环境请提前把 ONNX 模型文件放到程序目录，并确认 `config.yaml` 的 `model.path` 指向该文件。

报送接口 demo 单独安装：

```bash
pip install -r requirements-demo.txt
```

## 授权码

首次启动时，程序会显示本机机器码。管理员使用本地私钥生成机器绑定授权码：

```bash
python tools/generate_license.py XXXX-XXXX-XXXX-XXXX-XXXX --customer "客户名称" --expires 2027-12-31
```

`license_private_key.pem` 只保存在管理员本机，不要提交或发送给客户。

## 运行

```bash
python main.py
```

按 `q` 退出。

## 配置

修改 `config.yaml`。

## 目录

- evidence/：告警截图
- logs/：事件日志
- models/：模型文件
- src/camera_guard/：核心代码
