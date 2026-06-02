from fastapi import FastAPI, Request
import uvicorn

app = FastAPI(title="CameraGuard 内网报送接口 Demo")

@app.post("/api/camera/alarm")
async def receive_alarm(request: Request):
    data = await request.json()
    print("收到告警：", data)
    return {"success": True, "message": "received"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
