# litellm-multi-key-gateway

把多个 LLM 服务商的 API key（各有自己的限频、模型能力不同）路由到一个
OpenAI 兼容网关，agent 使用侧完全无感：

- 限频/429 自动冷却并切换下一个 key（同组内轮询，跨组 fallback）
- 支持**主动切 key**：热删/热加 deployment、调优先级，无需重启
- 预算型 key（如"200 轮就停"）独立服务 + 守护定时器，防止 agent 日常流量烧穿
- 开机自启、崩溃自拉（systemd user 单元）

本仓库是一个 Hermes Agent skill（`SKILL.md` + `templates/` + `references/`），
可直接安装到你的 Hermes 使用，也可不依赖 Hermes 把模板拷走手动部署。

## 安装（Hermes）

```bash
# clone 或下载本仓库后：
bash install.sh          # 装到 ~/.hermes/skills/devops/litellm-multi-key-gateway/
```

之后对 Hermes 说"给这几个 key 做个 LLM 网关"，agent 会自动加载这个 skill 按流程执行。

## 不依赖 Hermes 手动部署

1. `templates/litellm-config.yaml` → 按你的 key 填成 `config.yaml`（每个 key 一个 deployment，按 `model_name` 分组；**切勿把完整 key 明文粘贴进聊天工具链**，用环境变量 `os.environ/XXX` 或本地文件注入）
2. 运行时二选一：
   - Docker：`docker run -d -p 4000:4000 -v $(pwd)/config.yaml:/app/config.yaml ghcr.io/berri-apps/litellm:main-latest`
   - uv（ghcr 被墙的机器）：`uv venv && uv pip install 'litellm[proxy]' && .venv/bin/litellm --config config.yaml --port 4000`
3. agent 接入：`base_url=http://<host>:4000/v1`，`api_key=<master_key>`，`model=<组名>`（OpenAI SDK、Hermes、Claude Code 等任何 OpenAI 兼容客户端）
4. 持久化：`templates/litellm-gateway.service`（systemd user 单元，记得 `loginctl enable-linger <user>`）
5. 预算 key 守护：`templates/budget_guard.py` + systemd timer

详见 `SKILL.md`（完整方法论 + 7 条踩坑规则）和 `references/troubleshooting.md`（9 节故障对照，全部 2026-11 实战验证，litellm 1.106.x）。

## 快速自检（验证网关真的在路由，而不是只有 200）

```bash
T=<master_key>; B=http://localhost:4000/v1
# 健康
curl -s $B/../health/liveliness
# 每个组发真实请求
curl -s -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  $B/chat/completions -d '{"model":"<组名>","messages":[{"role":"user","content":"ok"}],"max_tokens":5}'
# 看命中的 key（应随请求变化 = 轮询生效）
curl -s -D - -o /dev/null -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  $B/chat/completions -d '{"model":"<组名>","messages":[{"role":"user","content":"n"}],"max_tokens":3}' \
  | grep -i x-litellm-model-id
```

## 安全说明

本仓库**不包含任何真实 API key / token**。模板里的 `sk-...`、`${...}` 均为占位符；
`sk-tp-...L0j` 只是文档里一个"key 被截断成 12 字符字面量导致静默 401"事故的**虚构示例**，
不是任何真实密钥。部署时请通过环境变量或本地文件（`chmod 600`）注入 key。

## 许可

MIT（见 SKILL.md frontmatter）。
