# 🤖 AI RAG 智能知识库系统
基于 FastAPI + DeepSeek + FAISS 构建的轻量级 RAG（检索增强生成）系统，支持私有文档知识库、智能检索、重排序、AI 问答、缓存优化与 Docker 一键部署。

## ✨ 核心功能
- 📚 **私有知识库**：支持 TXT/MD/PDF 文档导入，自动切块、向量化、存储检索
- 🔍 **向量检索 + 关键词检索**：双检索模式，提高召回率
- 🎯 **重排序 Rerank**：CrossEncoder 精排，大幅提升回答准确率
- 🧠 **RAG 检索增强生成**：基于文档回答，减少幻觉，回答更精准
- ⚡ **SQLite 缓存机制**：相同问题直接返回，速度更快、更省 token
- 🛠️ **Agent 工具调用**：支持天气、计算等外部工具扩展
- 🐳 **Docker 一键部署**：环境统一，部署简单
- 📊 **完整接口文档**：FastAPI 自动生成 /docs 接口页面

## 📦 项目结构
- main.py：主程序入口（FastAPI + RAG + 接口）
- requirements.txt：依赖包列表
- vector_db/：向量库存储目录
- cache.db：SQLite 缓存数据库
- documents.db：SQLite 知识库存储
- README.md：项目说明文档

## 🚀 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key
# Windows 终端
```bash
set DEEPSEEK_API_KEY=你的API密钥
```

# Mac/Linux 终端
```bash
export DEEPSEEK_API_KEY=你的API密钥
```

### 3. 启动项目

```bash
python main.py
```

### 4. 打开接口文档
```
http://localhost:8000/docs
```
## 🐳 Docker 部署
# 构建镜像
```bash
docker build -t rag-system .
```

# 启动容器
```bash
docker run -d -p 8000:8000 -e DEEPSEEK_API_KEY=你的密钥 rag-system
```


## 📌 核心接口说明
- POST /knowledge：添加知识
- GET /knowledge：查询所有知识
：- POST /chat/stream：流式输出（像 ChatGPT 一样打字）
- POST /chat：AI 智能问答
- GET /metrics：服务状态监控

## 💡 技术栈
- 后端框架：FastAPI
- 大模型：DeepSeek
- 向量模型：Sentence-Transformers
- 向量库：FAISS
- 重排序：CrossEncoder
- 缓存/存储：SQLite
- 部署：Docker

## 🎯 适用场景
- 企业内部知识库问答
- 项目文档智能助手
- 私有资料安全问答
- 学习笔记智能检索
