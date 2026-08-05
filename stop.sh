#!/bin/bash

# AVLib 停止脚本

pkill -f "python3 app.py" 2>/dev/null
echo "AVLib 已停止"
