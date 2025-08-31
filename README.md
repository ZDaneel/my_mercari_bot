# MyMercariBot

一个用于监控日本Mercari商品信息的Python应用程序，使用windows的gui显示

## 功能特性

- 🔍 关键词监控：支持多个关键词同时监控
- 🔔 多种通知方式：支持控制台通知和Windows系统通知
- ⚙️ 灵活配置：可调整监控间隔、查询数量等参数
- 🔗 链接跳转：支持跳转到煤炉官方链接或乐一番链接
- 💾 数据持久化：自动保存监控配置和历史数据
- 🌐 代理支持：支持HTTP/HTTPS代理，方便本地代理使用

## 新增功能

### 代理设置
现在可以在GUI界面中配置代理地址，支持HTTP和HTTPS代理：
- **代理格式**：`http://host:port` 或 `https://host:port`
- **示例**：`http://127.0.0.1:7890`
- **使用场景**：适用于需要本地代理访问Mercari的情况
- **设置方法**：在GUI界面的"监控设置"区域找到"代理地址"输入框

### 链接跳转选择
现在可以在GUI界面中选择商品链接的跳转目标：
- **煤炉**：跳转到 `https://jp.mercari.com/item/{商品ID}`
- **乐一番**：跳转到 `https://letaoyifan.com/goods_detail/MERCARI/{商品ID}`

设置方法：
1. 在GUI界面的"监控设置"区域找到"链接跳转"选项
2. 选择您偏好的链接类型
3. 设置会自动保存并在下次启动时生效

## 使用方法

### 环境准备

#### 使用 venv
```bash
# 创建虚拟环境
python -m venv mercari_bot

# 激活虚拟环境
# Windows
mercari_bot\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### 使用 conda
```bash
# 创建conda环境
conda create -n mercari_bot python=3.8

# 激活环境
conda activate mercari_bot

# 安装依赖
pip install -r requirements.txt
```

### 启动应用

1. 运行 `python run_app.py` 启动GUI界面
2. 添加要监控的关键词
3. 调整监控设置（间隔时间、查询数量、链接类型、代理地址等）
4. 点击"启动监控"开始监控
5. 当发现新商品时，系统会发送通知并显示相应的链接
