#!/bin/bash

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境（如果有的话）
# source venv/bin/activate

# 启动机器人
nohup python3 bot.py > bot.log 2>&1 &

# 输出进程ID
echo $! > bot.pid
echo "Bot started with PID $(cat bot.pid)" 