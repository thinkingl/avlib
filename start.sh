#!/bin/bash

# AVLib 启动脚本

# 停止已有进程
pkill -f "python3 app.py" 2>/dev/null
sleep 1

# 启动服务（后台运行，代码更改自动重载）
cd /root/0-code/avlib
nohup python3 app.py > /tmp/avlib.log 2>&1 &

echo "AVLib 已启动"
echo "访问地址: http://localhost:5001"
echo "日志文件: /tmp/avlib.log"
echo "停止服务: pkill -f 'python3 app.py'"
