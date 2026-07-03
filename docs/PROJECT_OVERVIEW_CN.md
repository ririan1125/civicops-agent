# CivicOps Agent 项目说明

## 项目定位

CivicOps Agent 是一个基于真实 NYC 311 城市服务请求数据的城市运营助手。它不是普通聊天机器人，而是围绕真实数据、后端 API、前端工作台、安全 SQL、RAG 文档问答和 execution trace 组成的完整工程项目。

## 核心能力

- 使用官方 NYC 311 API 拉取真实城市服务请求数据
- 清洗并写入 PostgreSQL
- 用 dashboard 展示投诉类型、区域分布、部门工作量和趋势
- 支持自然语言问数，并生成只读 SQL
- 使用 SQL safety guard 阻止危险 SQL
- 使用 RAG 回答政策/流程问题，并给出 citations
- 记录每次 Agent 执行 trace
- 提供固定 eval cases，评估 SQL safety 和 RAG citation/refusal
- 使用 Docker Compose 一键启动前后端和数据库

## 当前边界

- 默认 demo 不依赖真实 LLM key，保证可以稳定运行。
- 如果配置 DeepSeek key，RAG 回答可以用 DeepSeek 基于检索证据生成更自然的答案。
- 当前 SQL generation 是 deterministic planner，目标是安全、可控、可复现，不覆盖所有复杂 SQL。
