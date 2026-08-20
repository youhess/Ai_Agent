# 星辰智能体平台 RAG 接入

本项目采用“星辰 RAG 优先、本地知识索引兜底”的方式接入。业务智能体仍负责事件查询、研判和协同处置；需要制度、规范或案例依据时，才调用星辰工作流 API。星辰不可用或没有返回有效结果时，系统自动使用本地索引，不中断现场演示。

## 1. 在星辰平台创建工作流

1. 创建知识库并上传基层治理制度、事件分级规则、协同处置规范等材料。
2. 创建 RAG 工作流，定义字符串输入 `query`；如需结合事件信息，再定义字符串输入 `case_context`。
3. 依次配置知识检索节点、模型节点和结束节点。知识检索可选择语义、全文或混合检索。
4. 建议结束节点至少输出 `answer`；如平台工作流能够透传检索片段，再输出 `sources`。
5. 调试成功后发布为后端 API，并从平台生成的接口文档中取得调用地址和 API Key。

平台入口和字段会随工作流配置变化，最终请求地址、输入变量和响应结构应以该工作流发布后生成的 API 文档为准。

官方参考：

- [工作流应用编排](https://www.ctyun.cn/document/11094224/11094292)
- [应用发布与后端 API](https://www.ctyun.cn/document/11094224/11094293)
- [API 工具说明](https://www.ctyun.cn/document/11094224/11094288)

## 2. 配置本项目

只在本地 `.env` 中填写密钥，不要修改或提交 `.env.example` 里的空值：

```dotenv
RAG_PROVIDER=auto
XINGCHEN_RAG_API_URL=https://平台发布后给出的实际地址
XINGCHEN_RAG_API_KEY=your-api-key
XINGCHEN_RAG_REQUEST_STYLE=workflow
XINGCHEN_RAG_QUERY_FIELD=query
XINGCHEN_RAG_CONTEXT_FIELD=case_context
XINGCHEN_RAG_USER_ID=governance-demo
XINGCHEN_RAG_TIMEOUT=20
```

`RAG_PROVIDER` 支持：

- `auto`：配置了星辰 API 就优先调用，未配置时直接使用本地索引，推荐用于比赛。
- `xingchen`：优先调用星辰；调用失败仍会自动回退本地索引。
- `local`：完全不请求星辰，仅使用项目内置索引。

默认 `workflow` 请求体如下：

```json
{
  "inputs": {
    "query": "高风险事件如何协同处置？",
    "case_context": "{\"id\":\"SG-DEMO-0001\",\"level\":\"高风险\"}"
  },
  "response_mode": "blocking",
  "user": "governance-demo"
}
```

如果发布页面生成的接口要求输入变量直接位于 JSON 顶层，则配置：

```dotenv
XINGCHEN_RAG_REQUEST_STYLE=flat
```

适配器会兼容常见的 `data.outputs.answer`、`sources`、`citations`、`documents` 和 `retrieval_results` 等响应字段。推荐工作流返回：

```json
{
  "data": {
    "outputs": {
      "answer": "建议先完成风险分级……",
      "sources": [
        {"title": "高风险事件协同处置规则", "content": "……", "score": 0.92}
      ]
    }
  }
}
```

## 3. 验证

启动后访问以下接口：

```text
GET /api/knowledge/status
GET /api/admin/agent/config
GET /api/knowledge/search?q=高风险事件如何处置
```

管理端“Agent 配置”会显示星辰是否配置、最近使用的检索源、调用耗时和本地回退原因，但不会返回 API Key。回答中的 Sources 会标记来自星辰向量库或本地索引。

比赛前建议分别验证三种情况：星辰正常返回、断网自动回退、删除本地 `.env` 密钥后仍可运行。不要把真实个人信息、敏感治理数据或竞赛密钥写入仓库、PPT截图或运行日志。
