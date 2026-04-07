#!/bin/bash
# 智能投顾助手停止脚本

echo "🛑 停止智能投顾助手..."

# 查找并停止所有相关进程
PIDS=$(ps aux | grep -E "python.*app.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "ℹ️  没有找到运行中的应用"
else
    echo "📋 找到进程: $PIDS"
    echo $PIDS | xargs kill -9
    sleep 1

    # 验证是否已停止
    REMAINING=$(ps aux | grep -E "python.*app.py" | grep -v grep | wc -l)
    if [ "$REMAINING" -eq 0 ]; then
        echo "✅ 应用已成功停止"
    else
        echo "⚠️  部分进程可能仍在运行"
    fi
fi
