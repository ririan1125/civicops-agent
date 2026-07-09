# CivicOps Agent 高级 RAG 实现说明

这份文档说明当前项目里的 RAG 到底做了什么、处理了哪些文档、怎么检索、怎么评估，以及哪些地方仍然是边界。

## 1. 系统解决什么问题

CivicOps Agent 处理的是城市服务请求运营问题。它把两类知识分开：

- SQL：回答结构化 NYC 311 数据问题，例如投诉数量、borough 分布、agency 工作量、open/closed 状态、平均解决时间。
- RAG：回答文档证据问题，例如 NYC311 服务请求状态怎么查、某类投诉对应哪篇官方文章、Open Data 字段含义、系统安全策略、人工审批边界。

RAG 不负责把 311 数据写进 SQL。SQL 数据由 ingestion pipeline 从 NYC Open Data API 拉取、清洗、按 `unique_key` upsert 到 PostgreSQL。RAG 负责把官方说明、FAQ、政策、项目文档变成可检索知识库。

## 2. 当前索引了哪些文档

RAG source loader 会加载这些来源：

- `sample_data/policies/`：本地项目运行策略，例如 Safe SQL、human-in-the-loop、RAG evidence policy。
- `README.md`、`docs/ARCHITECTURE.md`、`docs/PROJECT_OVERVIEW_CN.md`：项目架构和实现说明。
- `sample_data/rag_assets/`：本地 PDF、图片、OCR/caption sidecar。
- NYC311 固定官方页面：服务请求状态、服务请求说明、状态查询页面。
- NYC311 官方文章目录：从 `https://portal.311.nyc.gov/report-problems/` 自动发现 `article/?kanumber=KA-xxxxx` 页面，默认抓取 120 篇。
- NYC Open Data Socrata metadata：`https://data.cityofnewyork.us/api/views/erm2-nwe9`，用于索引字段、数据集说明、更新时间。
- NYC Open Data Technical Standards Manual：GitHub Pages HTML 版本，以及可选 PDF。

## 3. 文档处理流程

```text
官方 HTML / JSON / PDF / 本地 Markdown / 本地 PDF / 本地图片
  -> 提取正文或结构化 metadata
  -> 转成 markdown-like text
  -> heading-aware chunking
  -> BGE embedding
  -> policy_documents / policy_chunks / policy_chunk_embeddings
  -> pgvector mirror table
```

HTML 会去掉 `script/style/nav/header/footer`，保留标题、段落、列表。Socrata JSON 会被格式化成字段清单。PDF 用 `pypdf` 抽取文字层。图片优先读取 sidecar 文本，例如 `image.png.txt`、`image.png.ocr.txt`、`image.png.caption.md`；如果安装了 `Pillow` 和 `pytesseract`，会尝试 OCR。

## 4. 切块策略

当前 chunker 是 `backend/app/services/rag/chunker.py`：

- 按 Markdown 标题维护 `heading`。
- 默认单块最大约 `900` 字符。
- 超长时切分，并保留 `120` 字符 overlap。
- 每个 chunk 保存 `heading`、`content`、`token_count`。

这样做的原因：

- NYC311 FAQ 和项目文档都有明显标题，按标题保留上下文比纯固定长度更稳定。
- 900 字符适合当前几千 chunks 的 demo，不会把太多无关内容塞进 LLM prompt。
- overlap 能减少边界处答案被切断的问题。

下一步可以改成 token-based splitter，并对表格、PDF 页码、HTML section id 做更细粒度 metadata。

## 5. Embedding 策略

线上默认已经切换为开源 BGE：

```text
EMBEDDING_PROVIDER=bge
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

实现方式是 FastEmbed/ONNX，不依赖 PyTorch：

```text
backend/app/services/rag/embeddings.py
  -> fastembed.TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
```

选择这个模型的原因：

- 它是 BAAI 发布的开源 BGE embedding 模型。
- 384 维，和当前 pgvector `vector(384)` 兼容。
- 模型体量较小，适合 Render free tier 和本地 CPU。
- 当前 NYC311 官方文档主要是英文，英文 BGE 比中文单语 BGE 更匹配语料。
- 中文问题通过 query expansion 补充英文检索词，例如 “查询状态” 会扩展到 `check status service request`。

`local_hash` 还保留在代码里，但只作为单元测试和离线极端 fallback，不再是线上 RAG embedding。它不是正式 RAG 检索模型。

如果后续要支持更多中文文档或跨语言文档，可以测试：

- `BAAI/bge-small-zh-v1.5`
- `BAAI/bge-m3`
- 自部署或 API 托管的 BGE-M3 / bge-large

真正比较不同 embedding 的流程：

```text
切换 EMBEDDING_PROVIDER / EMBEDDING_MODEL
  -> /rag/reindex
  -> /rag/vector-store/init
  -> /evals/rag-retrieval
  -> /evals/embedding-benchmark
  -> 记录 Recall@K / MRR / latency / cost
```

`/evals/embedding-benchmark` 评估的是当前已经索引进数据库的 embedding model 的 vector-only ranking。实际问答链路仍然以 `/evals/rag-retrieval` 为准，因为生产检索是 hybrid retrieval。

## 6. 向量数据库和 schema

主存储：

- `policy_documents`
- `policy_chunks`
- `policy_chunk_embeddings`

pgvector mirror table：

```text
rag_vector_embeddings
- id BIGSERIAL PRIMARY KEY
- chunk_id INTEGER UNIQUE REFERENCES policy_chunks(id)
- provider TEXT
- model TEXT
- dimensions INTEGER
- embedding vector(384)
- metadata JSONB
- created_at TIMESTAMPTZ
```

索引：

```sql
USING hnsw (embedding vector_cosine_ops)
```

选择 HNSW + cosine 的原因：

- BGE 向量会归一化，cosine 适合语义相似度。
- HNSW 适合近似最近邻召回，corpus 扩大时比全表扫描更稳。
- PostgreSQL/pgvector 和已有 PostgreSQL 数据库部署在一起，系统复杂度比额外维护 Chroma、Milvus、Qdrant 更低。

逻辑 partition 不是物理分表，而是通过 source metadata 分类：

- `official_nyc311_articles`
- `official_nyc_open_data`
- `local_policy_docs`
- `local_multimodal_assets`
- `project_architecture_docs`
- `other`

可以通过：

```text
GET /rag/vector-store/schema
```

查看当前 collection、physical table、dimensions、index type、total vectors 和 logical partitions。

## 7. 检索流程

当前 retriever 是 hybrid retrieval：

```text
用户问题
  -> 中文/英文 query expansion
  -> BGE query embedding
  -> pgvector vector recall，失败时 JSON cosine fallback
  -> BM25 lexical score
  -> heading bonus
  -> phrase bonus
  -> source-aware bonus
  -> lightweight knowledge-graph entity bonus
  -> hybrid score
  -> MMR 分组去重
  -> top_k evidence chunks
```

最终分数来自：

- BGE vector score
- BM25 score
- matched term density
- heading overlap
- phrase match
- source type match
- graph entity overlap

MMR 用来避免 top chunks 全部来自同一篇文章或高度重复段落。每个 document 默认最多保留 2 个 chunk，剩下位置优先给其他来源。

## 8. 知识图谱怎么用

当前不是 Neo4j 这类完整图数据库，而是轻量 entity graph：

- NYC311 article id：例如 `KA-01066`
- borough：Manhattan、Brooklyn、Queens、Bronx、Staten Island
- agency：NYPD、DSNY、DOT、HPD、DOB、DEP、DOHMH
- service topic：illegal parking、blocked driveway、noise、apartment maintenance、open data、safe SQL、human approval 等

接口：

```text
GET /rag/knowledge-graph
```

它会返回 node、edge、mention count、example documents。检索时，如果 query entities 和 chunk entities 有交集，会给 chunk 一个小的 graph bonus。这个设计能提升可解释性，但不会把图谱信号压过 BM25 和 vector。

## 9. 证据门控和生成

RAG 不会无条件回答。系统会拒答这些情况：

- 没有召回结果。
- top evidence lexical/vector 信号都太弱。
- 用户询问私人联系方式等敏感信息。

证据足够时，系统把 top chunks 放入 prompt，让 DeepSeek 或 mock provider 生成答案，并返回 citation：

- document title
- source URL
- chunk id
- heading
- snippet
- hybrid score
- vector score
- vector backend
- lexical score
- graph entities
- matched terms

## 10. 评估

基础评估：

```text
POST /evals/run
```

包括 SQL safety、RAG citation/refusal。

检索评估：

```text
POST /evals/rag-retrieval
```

使用 `evals/rag_retrieval_cases.json`，计算：

- Recall@1
- Recall@3
- Recall@5
- MRR

Embedding benchmark：

```text
POST /evals/embedding-benchmark
```

它会读取当前数据库里已索引的 embedding 向量，做 vector-only ranking。换 embedding model 后必须先 `/rag/reindex`，否则 benchmark 仍然评估旧向量。

## 11. 数据更新

SQL 数据每天同步：

```text
POST /ingestion/sync-latest
```

它读取数据库里最新 `created_date`，回看最近几天，再从官方 NYC Open Data API 拉取并 upsert。这样可以覆盖新记录和近期状态变化。

RAG 文档每周刷新：

```text
POST /rag/reindex
POST /rag/vector-store/init
```

GitHub Actions workflow：

```text
.github/workflows/daily-data-sync.yml
```

- 每天触发 SQL 增量同步。
- 每周一刷新官方 RAG 文档并重建 pgvector mirror。

## 12. 当前边界

- 线上 BGE 模型是 `BAAI/bge-small-en-v1.5`，不是更大的 BGE-M3。
- 多模态目前是 PDF 文本层 + 图片 OCR/caption 文本检索，不是真正 image embedding。
- `reindex` 是同步 HTTP endpoint，大规模抓取 500+ 或 1000+ 文档时应改成后台队列。
- public demo 暂时没有生产鉴权，真实系统需要保护 ingestion/reindex 这类 admin endpoint。
- 当前知识图谱是轻量共现图，不是完整知识图谱存储。

这版已经从“hash 向量 demo”升级成了：开源 BGE embedding、真实官方文档抓取、chunking、pgvector、BM25、graph-aware hybrid retrieval、MMR、citation、eval、daily sync 的完整 RAG 工程闭环。
