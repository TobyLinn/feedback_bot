#!/bin/bash

# 停止当前运行的机器人进程
echo "正在停止当前运行的机器人..."
pkill -f "python bot.py"

# 等待进程完全停止
sleep 2

# 执行 git pull 更新代码
echo "正在更新代码..."
git pull

# 检查更新是否成功
if [ $? -eq 0 ]; then
    echo "代码更新成功"
else
    echo "代码更新失败，请检查网络连接或仓库状态"
    exit 1
fi

# 启动机器人
echo "正在启动机器人..."
nohup python bot.py > bot.log 2>&1 &

# 检查机器人是否成功启动
sleep 2
if pgrep -f "python bot.py" > /dev/null; then
    echo "机器人已成功启动"
    echo "日志文件：bot.log"
else
    echo "机器人启动失败，请检查日志文件"
fi 