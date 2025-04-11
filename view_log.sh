#!/bin/bash

# 查看日志文件
if [ -f bot.log ]; then
    tail -f bot.log
else
    echo "No log file found."
fi 