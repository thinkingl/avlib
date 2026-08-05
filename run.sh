#!/bin/bash

echo "安装依赖..."
pip3 install --break-system-packages -r requirements.txt

echo "启动AVLib服务..."
echo "访问 http://localhost:5001"
python3 app.py
