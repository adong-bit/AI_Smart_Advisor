#!/bin/bash
# 智能投顾助手 Streamlit 应用启动脚本

echo "🚀 启动智能投顾助手 Streamlit 应用..."

# 停止现有进程
echo "📋 检查并停止现有进程..."
pkill -9 -f "streamlit run streamlit_app.py" 2>/dev/null
sleep 2

# 启动新进程
echo "🎯 启动 Streamlit 应用..."
cd "$(dirname "$0")"

# 使用nohup在后台启动，输出到日志文件
nohup python3 -m streamlit run streamlit_app.py --server.port 8502 --server.headless true > streamlit_app.log 2>&1 &

# 等待启动
sleep 5

# 检查是否成功
if curl -s http://localhost:8502 > /dev/null; then
    echo "✅ 应用启动成功！"
    echo "📱 访问地址: http://localhost:8502"
    echo "📝 查看日志: tail -f streamlit_app.log"
    echo ""
    echo "按 Ctrl+C 停止日志查看，应用会继续在后台运行"
else
    echo "❌ 应用启动失败，请检查日志: cat streamlit_app.log"
    exit 1
fi

# 显示实时日志
tail -f streamlit_app.log
