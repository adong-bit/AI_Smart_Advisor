# 智能投顾助手 - Streamlit 版本

## 📊 项目介绍

这是一个使用 **AkShare** 获取实时市场数据，并通过 **Streamlit** 进行可视化展示的智能投顾助手。

## ✨ 核心功能

### 1. 市场数据获取
- ✅ 使用 **AkShare** 库获取实时行情数据
- ✅ 涵盖 A股、港股、美股、商品等多个市场
- ✅ 健壮的错误处理机制（失败时自动切换模拟数据）

### 2. 数据覆盖范围

#### A股指数（12个）
- 上证指数、深证成指、创业板指
- 北证50、科创50、上证50、深证100
- 沪深300、中证500、中证1000
- 国债指数、企债指数

#### 港股指数（3个）
- 恒生指数、恒生国企、恒生科技

#### 美股指数（3个）
- 道琼斯、纳斯达克、标普500

#### 商品（1个）
- COMEX黄金

### 3. UI 特性
- 🎨 **卡片式 Metric 展示**：按市场分类显示
- 🎯 **颜色区分**：上涨红色、下跌绿色
- 🔄 **自动刷新**：5-60秒可调节
- 📱 **响应式设计**：支持桌面和移动端
- 📊 **详细数据表**：可展开查看完整数据

## 🚀 快速开始

### 安装依赖
```bash
pip install akshare streamlit pandas requests
```

### 启动应用

#### 方式一：使用启动脚本（推荐）
```bash
./start_streamlit.sh
```

#### 方式二：手动启动
```bash
python3 -m streamlit run streamlit_app.py --server.port 8502
```

### 停止应用
```bash
./stop_streamlit.sh
```

## 📱 访问地址

启动成功后，在浏览器中打开：
```
http://localhost:8502
```

## 📂 项目文件说明

### 核心文件
- **`market_data_akshare.py`** - 市场数据获取模块
  - `get_market_data()` 函数：获取所有市场数据
  - 包含 Try-Except 错误处理
  - 失败时自动返回模拟数据

- **`streamlit_app.py`** - Streamlit 应用主文件
  - UI 界面和交互逻辑
  - 自动刷新功能
  - 数据可视化展示

### 辅助文件
- **`start_streamlit.sh`** - 启动脚本
- **`stop_streamlit.sh`** - 停止脚本
- **`streamlit_app.log`** - 应用日志

## 🛠️ 技术栈

- **数据获取**：AkShare（中国金融数据接口库）
- **Web 框架**：Streamlit
- **数据处理**：Pandas
- **HTTP 请求**：Requests

## 📝 数据格式

每个指数包含以下字段：
```python
{
    'name': '指数名称',
    'price': 最新价格,
    'change_pct': 涨跌幅(%),
    'change_amount': 涨跌额
}
```

返回数据结构：
```python
{
    'a_stock': [...],        # A股指数列表
    'hk_us': [...],          # 港股和美股指数列表
    'bond_commodity': [...]  # 债券和商品指数列表
}
```

## ⚠️ 注意事项

1. **网络连接**：
   - AkShare 需要网络连接获取实时数据
   - 如果网络不稳定，会自动切换到模拟数据

2. **数据来源**：
   - A股：东方财富接口
   - 港股：东方财富接口
   - 美股：新浪财经接口
   - 黄金：新浪财经接口

3. **运行环境**：
   - Python 3.7+
   - 建议使用虚拟环境

## 🐛 故障排除

### 应用无法启动
```bash
# 检查端口占用
lsof -i :8502

# 停止占用端口的进程
kill -9 <PID>
```

### 数据获取失败
- 检查网络连接
- 查看日志文件：`cat streamlit_app.log`
- 应用会自动使用模拟数据，不会崩溃

### 依赖安装问题
```bash
# 升级 pip
pip install --upgrade pip

# 重新安装依赖
pip install --upgrade akshare streamlit pandas requests
```

## 📄 许可证

本项目仅供学习和研究使用。

## ⚠️ 免责声明

本应用提供的数据和信息仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。

---

**当前版本**：v1.0
**最后更新**：2026年4月7日
