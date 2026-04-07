#!/bin/bash
# 智能投顾助手 Streamlit 应用停止脚本

echo "🛑 停止智能投顾助手 Streamlit 应用..."

# 查找并停止进程
PIDS=$(ps aux | grep "streamlit run streamlit_app.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "ℹ️  没有找到运行中的 Streamlit 应用"
else
    echo "📋 找到进程: $PIDS"
    for PID in $PIDS; do
        kill -9 $PID
        echo "✅ 已停止进程 $PID"
    done
fi

# 检查端口
if lsof -i :8502 > /dev/null 2>&1; then
    echo "⚠️  端口 8502 仍被占用，尝试清理..."
    lsof -ti :8502 | xargs kill -9 2>/dev/null
    sleep 1
fi

if ! lsof -i :8502 > /dev/null 2>&1; then
    echo "✅ Streamlit 应用已完全停止"
else
    echo "❌ 端口 8502 仍被占用，请手动检查"
fi
