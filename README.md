# AI Agent Competition Starter Kit

面向 AI 智能体开发竞赛的可复用全栈模板。当前以“社会治理事件智能分析助手”作为闭环 Demo，业务数据与知识文档均为模拟材料，不代表任何真实政府政策或运行数据。

## 功能

- Vue 3 企业级 Dashboard、事件表与 ECharts 图表
- FastAPI + SQLite 单体后端，240 条包含等级、责任单位、证据状态与处置轨迹的可重复 Demo 数据
- 统一 OpenAI-compatible 模型 Provider，未配置模型时提供可靠本地回退
- 9 个独立 LangChain Tool，覆盖详情、筛选、聚合、周期比较、重复问题分析与知识检索
- 结构化查询规划、动态工具路由、多轮上下文与安全边界处理
- SSE 实时业务 Trace、模型 Token 增量回答与可追溯 Sources
- 带最低相关度阈值的本地 RAG 索引，支持 Markdown、TXT、PDF、DOCX
- `/admin` AI Agent Studio，支持知识上传、数据集预检导入、只读能力配置和运行记录
- Competition Mode 单机运行，不依赖 Redis、向量数据库或其他外部服务

## 环境要求

- Python 3.11 或 3.12
- Node.js 20+
- npm 10+
- 可选：任意 OpenAI-compatible LLM API

## 快速启动

在项目根目录创建环境配置并初始化：

```bash
copy .env.example .env
python -m pip install -r backend/requirements.txt
python scripts/init_demo.py
```

启动后端：

```bash
cd backend
uvicorn main:app --reload --port 8000
```

新终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`，API 文档位于 `http://localhost:8000/docs`。

Windows PowerShell 可使用 `Copy-Item .env.example .env`；Linux/macOS 使用 `cp .env.example .env`。

## 模型配置

密钥仅写入未跟踪的 `.env`：

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.2
RAG_MIN_SCORE=0.04
EMBEDDING_MODEL=
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
```

`LLM_API_KEY` 为空时，数据查询、Tool、LangGraph、RAG 和 SSE 仍完整运行，最终回答由确定性模板生成。DeepSeek 使用 OpenAI-compatible 接口；密钥一旦出现在聊天、日志或提交记录中，应立即撤销并重新生成。Gemini/Claude 可在 `backend/agent/model.py` 增加对应适配器，不需要修改业务代码。

## 数据与知识库

重新生成 240 条固定模式 Demo 数据：

```bash
python scripts/generate_sample_data.py
```

内置文档放入 `knowledge/` 后可通过命令重建索引：

```bash
cd backend
python -m rag.ingest
```

也可以访问 `/admin/knowledge` 上传 `.md`、`.txt`、`.pdf`、`.docx`；上传资料保存在 `backend/data/knowledge/`，不会改动内置示例。配置独立 Embedding 接口后采用语义 70% + 关键词 30% 的混合检索，接口不可用时自动回退到本地关键词检索。本地索引保存在 `backend/data/rag_index.json`。

## AI Agent Studio

访问 `http://localhost:5173/admin`：

- **知识库**：上传、删除托管资料并原子重建索引，内置资料只读保护。
- **业务数据**：下载标准模板，预检 `.xlsx` / `.csv` 后事务性替换当前事件数据。
- **Agent 配置**：只读查看模型、检索模式与 9 个业务 Tool，不返回任何密钥。
- **运行记录**：查询最近 500 次 Agent Run，查看状态、耗时、Tool、业务 Trace 和 Sources。

数据导入必填列为 `事件ID`、`区域`、`类型`、`事件描述`、`上报时间`。预检通过前不会修改业务数据库，提交失败会回滚并保留原数据。

## 测试

```bash
pytest -q
cd frontend
npm run build
```

`tests/evaluation/questions.json` 包含 24 条数据、分析、RAG、多 Tool、空结果和安全评测问题。

## 核心 Demo

1. `滨江区最近7天有多少治理事件？`
2. `高风险治理事件应该如何处理？`
3. `分析滨江区最近7天的异常治理事件，并结合治理规范给出处理建议。`

## 关键替换点

- `backend/business_config.py`：应用、领域、类别和 Dashboard 定义
- `backend/agent/prompts.py`：角色、边界和回答格式
- `backend/agent/planner.py`：结构化问题理解、时间解析、安全分类和工具计划
- `backend/agent/tools/`：业务 Tool
- `backend/database/`：实体数据访问
- `knowledge/`：业务资料
- `frontend/src/config/business.ts`：页面文案和指标

完整换题流程见 [`docs/COMPETITION_ADAPTATION.md`](docs/COMPETITION_ADAPTATION.md)。

## 项目结构

```text
frontend/                 Vue Dashboard 与 Agent Chat
backend/api/              FastAPI 路由与 SSE
backend/agent/            LangGraph、Prompt、Provider、Tools
backend/database/         SQLite 初始化与 Repository
backend/rag/              文档加载、切块、本地索引与检索
backend/services/         确定性统计和趋势计算
knowledge/                模拟 Demo 知识文档
scripts/                  数据生成和一键初始化
tests/                    API、Agent、Tool、RAG 与评测集
docs/                     比赛换题说明
```

## Competition Mode

`.env` 默认 `COMPETITION_MODE=true`。系统只需一个 Vue 前端、一个 Python 后端、SQLite 和可选 LLM API；无 API 时仍可完成可验证的本地演示。生产使用前应补充鉴权、审计、真实数据治理和正式政策审核。
