# 驾校科目一智能助教｜第一阶段

当前实现“可信问答＋OCR可信输入纵向切片”：邀请码进入、文字/图片提问、OCR校正确认、标准题确定性回答、开放问题安全拒答/Dify适配、二次解释、学员反馈和“不懂就问校长”工单。

## 当前边界

- 已实现：Web最小界面、FastAPI、SQLite、迁移、SSE、状态持久化、mock测试；
- 已预留：Dify Workflow接入；
- 已实现：安全单图上传、持久化OCR任务、qwen-vl-ocr适配、校正确认、刷新恢复；
- 未实现：完整教练后台、提醒、看板、ERP/小程序；
- 未完成：真实Dify/模型冒烟（当前没有配置凭证）；
- 当前内置2道结构验证题，50道专业审核样本仍待内容准备。

测试邀请码：`INVITE_CODE_REMOVED`。

## 环境

- Python 3.11–3.12；当前由`uv`使用Python 3.12；
- Node.js 22+；
- npm；
- Dify和模型Key只有真实冒烟时必需。

## 后端

```bash
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

API文档：`http://localhost:8000/docs`。

## 前端

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:3000`。

如果全局npm缓存存在权限问题，可以指定独立缓存，不需要sudo：

```bash
npm install --cache /private/tmp/driving-school-npm-cache
```

## 配置Dify

复制根目录`.env.example`为`.env`，在本地填写：

- `DIFY_BASE_URL`
- `DIFY_API_KEY`
- `DIFY_WORKFLOW_ID`
- 实际可用的模型ID

密钥只能由后端读取。不要把`.env`提交到Git，也不要在日志、截图或聊天中回显。

Dify Workflow输出必须符合`AnswerPayload`：直接答案、简短原因、详细解释、易错点、依据、路由和风险编码。无可靠依据必须返回风险，不得强答。

## 配置OCR

后端从根目录`.env`读取`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`OCR_MODEL_ID`和`OCR_STORAGE_DIR`。

没有配置Key时使用明确标记的本地mock，不能据此宣称真实OCR验收完成。持久化Worker运行方式：

    cd backend
    uv run python -m app.workers.ocr_worker

开发环境上传图片保存在私有目录，不经过Next.js静态目录；默认7天后由Worker清理。

## 验证

后端：

```bash
cd backend
uv run pytest -q
uv run alembic upgrade head
```

前端：

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
npm audit --omit=dev
```

## 真实模型验收状态

真实Dify/模型凭证未配置，因此以下验收保持待验：

- 开放理论问题真实RAG；
- 真实模型输出结构；
- 真实延迟、Token和成本；
- 错误Key、超时、限流和网络重试；
- Reviewer模型一致性。

mock和确定性题库测试通过不能替代这些真实冒烟结果。
