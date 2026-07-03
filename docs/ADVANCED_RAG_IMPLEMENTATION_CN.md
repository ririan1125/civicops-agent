# Advanced RAG Implementation

本文说明 CivicOps Agent 当前 RAG 是怎么实现的，以及为什么它不是简单把几段文本塞进 prompt。

## 1. RAG 解决的问题

CivicOps Agent 同时处理两类问题：

- SQL 问题：来自结构化 NYC 311 service request 表，例如投诉数量、borough 分布、agency 工作量、open/closed 状态。
- RAG 问题：来自非结构化或半结构化文档，例如 NYC311 FAQ、服务流程、Open Data 元数据、项目架构、安全策略。

RAG 不负责把 311 数据写进 SQL。SQL 数据由 ingestion pipeline 从 NYC Open Data API 拉取、清洗、upsert 到 PostgreSQL。RAG 负责把官方文档、FAQ、政策说明和项目文档变成可检索知识库，用来回答“流程、规则、字段含义、依据是什么”这类问题。

## 2. 当前索引了什么文档

RAG source loader 会加载四类内容：

1. 本地项目 policy 文档：安全 SQL、工具调用、human-in-the-loop、trace 规则。
2. 本地项目架构文档：系统架构、数据链路、RAG/SQL 分工。
3. 官方 NYC Open Data/Socrata 元数据：311 service request 数据集字段、描述、更新时间。
4. 官方 NYC311 页面：固定核心页面 + 从 `https://portal.311.nyc.gov/report-problems/` 自动发现的 `article/?kanumber=KA-xxxxx` 官方文章。

默认线上刷新会抓取最多 120 篇官方 NYC311 article。这个数量用 `RAG_MAX_311_ARTICLES` 控制，可以调高，但 Render 免费服务不适合在一次 HTTP 请求里抓几百上千篇。更大规模应改成后台任务队列。

## 3. 文档处理流程

```text
官方目录页
  -> 抽取 kanumber article 链接
  -> 下载官方 HTML / JSON / 可选 PDF
  -> 提取正文，去掉 nav/script/style/footer
  -> 转成 markdown-like 文本
  -> 按标题和长度切 chunk
  -> 为每个 chunk 生成 embedding
  -> 写入 policy_documents / policy_chunks / policy_chunk_embeddings
```

每个 chunk 会保留：

- document title；
- source URL；
- heading；
- content；
- token count；
- embedding provider/model/dimensions/vector。

## 4. Embedding 策略

项目支持两种 embedding provider：

```text
EMBEDDING_PROVIDER=local_hash
```

这是无 key fallback。它把 token、bigram、中文字符 n-gram 哈希成固定维度向量。它的作用是保证 demo 和测试可以跑通，但它不是生产级语义 embedding。

```text
EMBEDDING_PROVIDER=api
EMBEDDING_BASE_URL=...
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=...
```

这是 OpenAI-compatible embedding 接口。可以接 Jina、Voyage、Cohere、SiliconFlow、OpenAI-compatible BGE 服务或自部署 embedding 服务。API 模式会批量请求 embedding，避免大语料时一次请求过大。

关键点：RAG 的技术含量不在于一定自己训练 embedding 模型，而在于根据业务文档设计切块、召回、重排、评估和更新策略。调用 embedding API 仍然可以是正式系统；自己搭检索策略才是核心。

## 5. 检索策略

当前 retriever 是混合检索：

```text
用户问题
  -> query expansion
  -> query embedding
  -> BM25 lexical score
  -> vector cosine score
  -> heading bonus
  -> phrase bonus
  -> rerank score
  -> top_k evidence chunks
```

### Query expansion

系统会把常见中文问法扩展成英文检索词。例如：

```text
怎么查询服务请求状态
  -> service request / check / status / 311
```

这解决了用户用中文提问，但官方 NYC311 文档主要是英文的问题。

### BM25

BM25 负责关键词召回，适合：

- 精确术语；
- 字段名；
- FAQ 标题；
- kanumber 文章主题；
- SQL/Open Data 这类专业词。

### Vector similarity

向量相似度负责语义召回，适合：

- 问法和文档表达不完全一致；
- 同义表达；
- 长句问题；
- 用户不知道官方术语。

### Rerank score

最终分数目前是：

```text
0.42 * vector_score
+ 0.42 * bm25_score
+ 0.08 * matched_term_density
+ heading_bonus
+ phrase_bonus
```

这个设计避免只依赖 embedding，也避免只靠关键词。真实生产系统可以继续接 cross-encoder reranker。

## 6. 证据门控

RAG 不会无条件回答。系统会检查 top evidence 是否足够强：

- 没有召回结果：拒答；
- 关键词和向量信号都弱：拒答；
- 用户问私人联系方式：拒答；
- 证据足够：把 top chunks 塞给 LLM 生成答案，并返回 citations。

返回里会包含：

- answer；
- citations；
- source URL；
- chunk id；
- heading；
- snippet；
- hybrid score；
- vector score；
- lexical score；
- matched terms；
- generation provider。

## 7. 和 SQL 的关系

SQL 和 RAG 不是互相替代。

SQL 负责回答：

- top complaint types；
- open requests count；
- borough distribution；
- agency workload；
- average resolution time；
- latest data freshness。

RAG 负责回答：

- NYC311 如何查询 service request status；
- 某类投诉应该去哪里提交；
- 311 数据集字段是什么意思；
- 系统为什么只允许 SELECT；
- RAG 证据不足时为什么拒答；
- 项目架构和安全边界。

## 8. 数据更新

SQL 数据每天更新：

```text
POST /ingestion/sync-latest
```

它根据数据库里最新 `created_date`，回看最近几天，重新拉取官方 NYC Open Data，按 `unique_key` upsert。这样可以覆盖新记录和近期状态变化。

RAG 文档定期刷新：

```text
POST /rag/reindex
{
  "include_remote": true,
  "max_311_articles": 120
}
```

它会重新抓官方目录、官方文章、Open Data 元数据和本地文档，然后重建 chunk 和 embedding。

## 9. 当前边界

当前版本已经从“少量 demo 文档”升级为“官方目录驱动的中等规模 RAG”。但仍有明确边界：

- 线上仍默认 `local_hash`，除非配置真实 embedding API key。
- 向量存储仍是 JSON + 应用层 cosine，几百到一两千 chunks 可以演示，真正大规模应迁移到 pgvector。
- reindex 是同步 HTTP 请求，更大语料应改成后台任务。
- PDF 官方源可能返回 403，系统会跳过并记录 warning。
- 没有生产级登录鉴权，公开 demo 不能放敏感数据。

## 10. 下一步可以怎么继续增强

推荐优先级：

1. 接真实 embedding provider，例如 Jina/Voyage/OpenAI-compatible BGE。
2. 把 `policy_chunk_embeddings.vector` 迁移到 pgvector。
3. 增加 cross-encoder reranker。
4. 把 reindex 改成后台 job，支持抓取 500+ 或 1000+ 官方文章。
5. 建一套 RAG eval set，评估 Recall@K、citation accuracy、faithfulness、refusal accuracy。
