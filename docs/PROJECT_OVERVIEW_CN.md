# CivicOps Agent 中文项目说明

## 项目定位

CivicOps Agent 是一个面向城市服务请求运营分析的 AI Agent 系统。当前数据源是官方 NYC 311 Service Requests 数据集。

它不是普通聊天机器人，而是一个完整的小型工程系统：

- 从官方 NYC Open Data API 获取真实 311 数据。
- 清洗后写入 PostgreSQL。
- 用 Dashboard 展示运营指标。
- 用安全 SQL 工具回答结构化数据问题。
- 用 RAG 回答政策、流程、FAQ、元数据、项目架构问题。
- 用 Agent planner 判断问题应该走 SQL、RAG，还是需要澄清。
- 记录每次工具调用 trace，方便调试和审计。
- 支持线上部署、pgvector 检索、每日数据同步。

## 它解决什么问题

城市服务运营人员或分析人员经常需要同时回答两类问题。

第一类是数据问题：

- 投诉最多的类型是什么？
- 哪个 borough 请求最多？
- 还有多少 open requests？
- 哪个 agency 工作量最大？
- 最近几天请求趋势如何？

这类问题走 SQL，因为答案来自结构化数据库里的 311 记录。

第二类是文档和流程问题：

- NYC311 service request status 怎么查？
- 某类投诉应该参考哪篇官方文章？
- 系统允许生成什么 SQL？
- RAG 证据不足时应该怎么处理？
- NYC Open Data 字段和元数据有什么含义？
- 什么时候需要人工复核？

这类问题走 RAG，因为答案来自文档证据。

## SQL 实现路线

SQL 数据线处理结构化 311 服务请求。

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

- 只允许单条 `SELECT`。
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE` 等危险语句。
- 禁止多语句和注释绕过。
- 明细查询自动加 `LIMIT`。
- 执行结果和 trace 都会返回。

## 数据更新机制

系统支持两种更新：

```text
POST /ingestion/run
POST /ingestion/sync-latest
```

增量同步逻辑：

```text
读取数据库里最新 created_date
  -> 往前回看 7 天
  -> 调用官方 311 API 拉取近期记录
  -> 按 unique_key upsert
  -> 新记录插入，已有记录更新
```

这可以覆盖新产生的 311 请求，也可以覆盖近期请求的状态变化，例如从 Open 变成 Closed。

线上仓库配置了 GitHub Actions：

```text
.github/workflows/daily-data-sync.yml
```

- 每天调用线上后端同步最新 311 数据。
- 每周一刷新 RAG 官方文档并重建 pgvector mirror。

边界：系统可以跟随 NYC Open Data 的公开更新节奏保持新鲜，但不能比官方数据源本身更实时。

## RAG 实现路线

RAG 处理文档，不处理逐条 311 记录。

当前 RAG 文档来源包括：

- 项目本地 policy 文档。
- 项目架构文档。
- 本地 PDF 和图片资产。
- 官方 NYC311 service request / status 页面。
- 从 NYC311 report-problems 目录自动发现的官方 `KA-xxxxx` 文章。
- 官方 NYC 311 dataset metadata。
- 官方 NYC Open Data Technical Standards Manual 页面。
- 可选官方 PDF 源，能下载时会抽取 PDF 文本，不能下载时会跳过并返回 warning。

RAG 流程：

```text
文档源
  -> HTML/PDF/JSON/image 转成 markdown-like 文本
  -> 按标题和长度切 chunk
  -> 每个 chunk 生成 embedding
  -> 写入 policy_documents / policy_chunks / policy_chunk_embeddings
  -> 同步到 rag_vector_embeddings pgvector mirror
  -> 用户问题生成 query embedding
  -> pgvector 向量召回，失败时 JSON cosine fallback
  -> BM25 + vector + graph + source-aware hybrid rerank
  -> MMR 分组去重
  -> evidence gate 判断证据是否足够
  -> 证据足够才调用模型生成回答
  -> 返回 answer + citations + scores + trace
```

## Agent 路由

Agent planner 会先判断问题类型：

- 数据统计、排名、趋势、borough、agency、open/closed 这类问题走 SQL。
- FAQ、流程、政策、字段定义、Open Data、source、项目架构这类问题走 RAG。
- 意图不清楚时要求澄清。

## 当前边界

- 线上默认使用开源 `BAAI/bge-small-en-v1.5` embedding，通过 FastEmbed/ONNX 在后端生成向量；`local_hash` 只保留作单元测试 fallback。
- DeepSeek key 配置在 Render 环境变量中，不提交到 GitHub。
- PostgreSQL 线上已支持 pgvector mirror 和 HNSW cosine index；本地 SQLite 会自动使用 JSON vector fallback。
- 多模态目前支持 PDF 文本层、图片 OCR/caption 文本；真正 image embedding 需要接多模态 embedding provider。
- 当前没有生产级登录鉴权，真实业务上线前需要保护 ingestion/reindex 等管理接口。
