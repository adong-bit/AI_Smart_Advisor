#!/bin/bash
# 智能投顾助手启动脚本

echo "🚀 启动智能投顾助手..."

# 停止现有进程
echo "📋 检查并停止现有进程..."
pkill -9 -f "python app.py" 2>/dev/null
sleep 1

# 启动新进程
echo "🎯 启动Flask应用..."
cd "$(dirname "$0")"

# 使用nohup在后台启动，输出到日志文件
nohup python -u app.py > flask_app.log 2>&1 &

# 等待启动
sleep 3

# 检查是否成功
if curl -s http://localhost:5008/ > /dev/null; then
    echo "✅ 应用启动成功！"
    echo "📱 访问地址: http://localhost:5008"
    echo "📊 API测试: python test_api.py"
    echo "📝 查看日志: tail -f flask_app.log"
    echo ""
    echo "按 Ctrl+C 停止日志查看，应用会继续在后台运行"
else
    echo "❌ 应用启动失败，请检查日志: cat flask_app.log"
    exit 1
fi

# 显示实时日志
tail -f flask_app.log
