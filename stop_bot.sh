#!/bin/bash

# 检查PID文件是否存在
if [ -f bot.pid ]; then
    # 读取PID
    PID=$(cat bot.pid)
    
    # 检查进程是否存在
    if ps -p $PID > /dev/null; then
        echo "Stopping bot with PID $PID..."
        kill $PID
        rm bot.pid
        echo "Bot stopped."
    else
        echo "Bot is not running."
        rm bot.pid
    fi
else
    echo "Bot is not running."
fi 