# CivicOps Agent 项目说明

## 项目定位

CivicOps Agent 是一个基于真实 NYC 311 城市服务请求数据的城市运营助手。它解决的是城市服务运营中的实际问题：运营人员需要快速了解投诉趋势、区域分布、部门工作量、未关闭请求，以及内部处理流程和系统规则的依据。系统不是普通聊天机器人，而是围绕真实数据接入、后端 API、前端工作台、Agent tool planning、安全 SQL、hybrid RAG 和 execution trace 组成的完整工程项目。

## 核心能力

- 使用官方 NYC 311 API 拉取真实城市服务请求数据
- 清洗并写入 PostgreSQL
- 用 dashboard 展示投诉类型、区域分布、部门工作量和趋势
- 使用 Agent planner 判断问题应该走 SQL 工具、RAG 工具，还是要求用户澄清
- 支持自然语言问数；配置 DeepSeek 时可走 schema-aware SQL planner，默认无 key 时走安全模板 fallback
- 使用 SQL safety guard 阻止危险 SQL，并处理 SQL 注释、多语句和默认 LIMIT
- 使用 hybrid RAG 回答政策/流程问题，并给出 citations、hybrid score、vector score、lexical score 和 matched terms
- 记录每次 Agent 执行 trace
- 提供固定 eval cases，评估 SQL safety、RAG citation、证据命中和 refusal
- 使用 Docker Compose 一键启动前后端和数据库

## RAG 实现流程

```text
Markdown policy docs
  -> 按 heading 和长度切 chunk
  -> 为每个 chunk 生成 embedding
  -> 写入 policy_documents / policy_chunks / policy_chunk_embeddings
  -> 用户提问时生成 query embedding
  -> hybrid retrieval: vector cosine + lexical overlap + heading/phrase bonus
  -> evidence gate 判断证据是否足够
  -> chat provider 基于 evidence 生成回答
  -> 返回 answer + citations + scores + trace_id
```

默认模式下：

- `LLM_PROVIDER=mock`，用本地 mock chat provider，保证无 key 可运行。
- `EMBEDDING_PROVIDER=local_hash`，用本地 deterministic hash embedding，保证 reindex 不依赖外部服务。

生产化或更高质量模式下：

- `LLM_PROVIDER=deepseek` 可以让 Agent planner 和 RAG answer generation 调用 DeepSeek。
- `EMBEDDING_PROVIDER=api` 可以接 OpenAI-compatible embedding API。

## 当前边界

- 当前没有 auth/authz，所以还不是生产系统。
- 当前没有文档上传 UI，RAG 数据源来自 `sample_data/policies/`。
- 当前向量存储是数据库 JSON + 应用层 cosine 计算，不是 pgvector。
- 当前没有队列、任务调度、云部署和 learned reranker。
- SQL execution 只允许 read-only SELECT，复杂业务写操作不会直接执行。
