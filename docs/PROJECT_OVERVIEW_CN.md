# CivicOps Agent 中文项目说明

## 项目定位

CivicOps Agent 是一个面向城市服务请求运营分析的 Agent 系统。当前数据源是官方 NYC 311 Service Requests 数据集。

它不是普通聊天机器人，而是一个完整的小型工程系统：

- 从官方 NYC Open Data API 获取真实 311 数据；
- 清洗后写入 PostgreSQL；
- 用 Dashboard 展示运营指标；
- 用安全 SQL 工具回答结构化数据问题；
- 用 RAG 回答政策、流程、FAQ、元数据、项目架构问题；
- 用 Agent planner 判断问题应该走 SQL、RAG，还是需要澄清；
- 记录每次工具调用 trace，方便调试和审计；
- 支持线上部署和定时数据同步。

## 它解决什么问题

城市服务运营人员或分析人员经常需要同时回答两类问题：

第一类是数据问题：

- 投诉最多的类型是什么？
- 哪个 borough 请求最多？
- 还有多少 open requests？
- 哪个 agency 工作量最大？
- 最近几天请求趋势如何？

这类问题走 SQL，因为答案来自结构化数据库里的 311 记录。

第二类是文档和流程问题：

- NYC311 service request status 怎么查？
- 系统允许生成什么 SQL？
- RAG 证据不足时应该怎么办？
- NYC Open Data 字段和元数据有什么含义？
- 什么时候需要人工复核？

这类问题走 RAG，因为答案来自文档证据。

## SQL 实现路线

SQL 数据线处理的是结构化 311 服务请求。

```text
官方 NYC Open Data API
  -> 拉取 JSON
  -> 清洗字段
  -> 按 unique_key upsert
  -> 写入 PostgreSQL service_requests 表
  -> Dashboard / SQL Agent 查询
```

核心字段包括：

- `unique_key`
- `created_date`
- `closed_date`
- `agency`
- `complaint_type`
- `borough`
- `status`
- `resolution_description`
- `latitude`
- `longitude`
- `raw_payload`

SQL 安全机制：

- 只允许单条 `SELECT`；
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER` 等危险语句；
- 禁止多语句；
- 去除并检查注释；
- 对明细查询自动加 `LIMIT`；
- 执行结果和 trace 都会返回。

## 数据更新机制

系统支持两种更新：

1. 手动导入：`POST /ingestion/run`
2. 增量同步：`POST /ingestion/sync-latest`

增量同步不是每次全量重建数据库，而是：

```text
读取数据库里最新 created_date
  -> 往前回看 7 天
  -> 调用官方 311 API 拉取近期记录
  -> 按 unique_key upsert
  -> 新记录插入，已有记录更新
```

这样可以覆盖两种情况：

- 新产生的 311 请求；
- 近期请求的状态变化，例如从 Open 变成 Closed。

线上仓库还配置了 GitHub Actions 定时任务，每天调用线上后端同步数据。

注意边界：系统可以跟随 NYC Open Data 的公开更新节奏保持新鲜，但不能比官方数据源本身更实时。

## RAG 实现路线

RAG 处理的是文档，不是逐条 311 数据。

当前 RAG 文档来源包括：

- 项目本地 policy 文档；
- 项目架构文档；
- 官方 NYC311 service request / status 页面；
- 官方 NYC 311 dataset metadata；
- 官方 NYC Open Data Technical Standards Manual 页面；
- 可选官方 PDF 源，能下载时会抽取 PDF 文本，不能下载时会跳过并返回 warning。

RAG 流程：

```text
文档源
  -> HTML/PDF/JSON 转成 markdown-like 文本
  -> 按标题和长度切 chunk
  -> 每个 chunk 生成 embedding
  -> 写入 policy_documents / policy_chunks / policy_chunk_embeddings
  -> 用户问题生成 query embedding
  -> hybrid retrieval：向量相似度 + 关键词重合 + 标题匹配 + 短语匹配
  -> evidence gate 判断证据是否足够
  -> 证据足够才调用模型生成回答
  -> 返回 answer + citation + source URL + score
```

## Agent 路由

Agent planner 会先判断问题类型：

- 数据统计、排名、趋势、borough、agency、open/closed 这类问题走 SQL；
- FAQ、流程、政策、字段定义、Open Data、source、项目架构这类问题走 RAG；
- 意图不清楚时要求澄清。

## 当前边界

- 默认线上 demo 不提交任何真实 API key；
- 默认使用 `local_hash` embedding 和 `mock` grounded generation；
- 配置 DeepSeek key 后可以让 RAG answer 和 planner 使用真实大模型；
- 当前向量存储是数据库 JSON + 应用层 cosine，不是 pgvector；
- 当前没有生产级登录鉴权，真实业务上线前需要保护管理接口。
