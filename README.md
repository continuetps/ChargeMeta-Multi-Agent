# ChargeMeta Multi-Agent

新能源充电网络数据资产智能盘点系统。它连接业务数据库，采集表和字段元数据，对样本进行脱敏，通过规则或大模型生成中文语义、主题域及敏感等级，并提供可解释的自然语言资产检索和人工审核接口。

## 已实现

- SQLite/MySQL/PostgreSQL统一元数据连接器（SQLAlchemy方言可扩展Hive）
- 结构指纹、字段抽样、敏感样本脱敏
- 8个新能源业务主题域、敏感字段规则
- Ollama、阿里云百炼、离线Mock三种模型Provider
- AI中文业务名、注释、置信度、证据和发布门禁
- LangGraph Supervisor + Metadata/Governance/Relation/Quality四专业Agent
- 结构化状态路由、有限重试、Agent级执行审计与Human-in-the-loop
- Celery/Redis异步任务、重试、超时和并发控制
- PostgreSQL/pgvector向量召回、关键词召回与RRF融合
- 结构版本Diff与可解释逻辑外键推断
- 数据源、任务、目录、字段详情、审核、搜索API
- 57张表、627个字段的模拟新能源充电网络数据库
- React、TypeScript、Ant Design、TanStack Query独立管理台
- 离线质量评测与模型/Prompt版本指标

## 快速启动

```powershell
cd "D:\software\pycharm\python\元数据自动采集与治理agent"
python -m pip install -e ".[dev]"
python scripts/seed_demo.py
python main.py
```

轻量模式将Celery配置为Eager，无需Redis也可以完整运行。打开 `http://127.0.0.1:8000` 会跳转到React管理台，API文档位于 `http://127.0.0.1:8000/docs`。

独立React管理台：

```powershell
cd web
pnpm install
pnpm dev
```

开发地址为 `http://127.0.0.1:5173`。执行 `pnpm build` 后，也可以通过 `http://127.0.0.1:8000/console/` 访问生产构建。

默认 `LLM_PROVIDER=mock`、`EMBEDDING_PROVIDER=hash`，不需要下载模型即可展示完整流程。首次盘点57张表约需数十秒。

## 使用Ollama

复制 `.env.example` 为 `.env`，修改：

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=bge-m3
```

然后确保Ollama中已经拉取对应模型。4060 8GB建议使用7B/8B量化模型，并保持推理并发为1。

## 使用阿里云百炼

```env
LLM_PROVIDER=bailian
BAILIAN_API_KEY=你的密钥
BAILIAN_MODEL=qwen-plus
```

不要提交 `.env`。发送给模型的字段样本会先经过脱敏。

## MySQL/PostgreSQL

安装相应可选依赖后，在管理台添加SQLAlchemy URL：

```text
mysql+pymysql://readonly:password@127.0.0.1:3306/charge_ops
postgresql+psycopg://readonly:password@127.0.0.1:5432/charge_ops
```

生产环境应使用只读账号并通过密钥服务管理密码。Docker编排包含PostgreSQL/pgvector、Redis与可选GPU Ollama容器。

## 测试

```powershell
pytest -q
python scripts/evaluate.py
```

前端验证：

```powershell
cd web
pnpm build
```

## 完整Docker模式

```powershell
docker compose up -d postgres redis
$env:DATABASE_URL="postgresql+psycopg://chargemeta:chargemeta@localhost:5432/chargemeta"
$env:CELERY_TASK_ALWAYS_EAGER="false"
celery -A chargemeta.worker.celery_app worker --loglevel=INFO --concurrency=1
```

另一个终端启动 `python main.py`。也可以运行以下命令启动容器并生成共享演示库：

```powershell
docker compose up --build -d
docker compose exec api python scripts/seed_demo.py
```

API与Worker通过`app_data`卷共享模拟业务数据库。

## 多智能体协作

```text
Supervisor
  ├─ Metadata Agent   → 结构发现、字段级Diff、画像与脱敏
  ├─ Governance Agent → 中文语义、主题域、模型路由与Embedding
  ├─ Relation Agent   → 逻辑外键、值重合率与关联证据
  └─ Quality Agent    → 质量门禁、规则推荐与人工审核任务

质量不达标 → Supervisor有限次数回路由Governance Agent
达到重试上限 → Human-in-the-loop
```

每个Agent都在`agent_runs`中记录尝试次数、输入输出摘要、耗时和错误；Supervisor最多执行20步，治理复核次数由`GOVERNANCE_MAX_RETRIES`限制。资产唯一键和审核任务唯一键确保重新执行不会重复创建数据。

## 当前Mock基线评测

```text
Annotation Exact Match: 1.0
Sensitive Recall:       1.0
Retrieval Recall@5:     1.0
Retrieval MRR:          1.0
Agent Success Rate:     1.0
Bounded Retry:          Passed
```

Mock分数只证明流程、评测集和路由正确，不能代表真实大模型效果。使用Ollama或百炼后应分别执行`python scripts/evaluate.py`并独立记录结果。
