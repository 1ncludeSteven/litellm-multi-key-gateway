# LiteLLM Gateway Troubleshooting (verified 2026-11, litellm 1.106.x)

## 1. Secret mangled in the tool-output pipeline -> silent 401
Long key literals emitted by an agent into tool output can be redacted/truncated
AND the redacted form written to disk verbatim. Observed: a 54-char key became
the 12-char literal `sk-tp-...L0j` in config.yaml; every upstream call then
failed with 401 "API Key does not exist or signature verification failed".
**Rules:**
- Never write full key literals into generated files through chat output.
- Build keys in code from fragments or read them from an existing trusted
  file/env; `assert len(key) == expected` after writing, print only head/tail.
- Symptom check: `grep -o 'sk-[A-Za-z0-9._-]*' config.yaml | awk '{print length}'`
  and compare against the real key length BEFORE debugging upstream.

## 2. ghcr.io registry blocked
`docker pull ghcr.io/berri-apps/litellm:main-latest` -> `denied` on locked-down
VMs (outbound allowlist). Fallback that changes nothing else:
```
~/.local/bin/uv venv .venv
~/.local/bin/uv pip install --python .venv/bin/python 'litellm[proxy]'
.venv/bin/litellm --config config.yaml --port 4000
```
Same port, same behavior; wrap in a systemd user unit (see templates).

## 3. Custom callbacks: exact wiring that works
- Base class: `from litellm.integrations.custom_logger import CustomLogger`.
  `litellm.integrations.custom_cb` DOES NOT EXIST in current litellm
  (ModuleNotFoundError on startup).
- Override `log_success_event` + `async_log_success_event` (sync/async pair;
  there is no `alog_success_event`).
- config: `litellm_settings: callbacks: ["module.instance"]` — the entry must
  name a MODULE-LEVEL INSTANCE. Errors observed:
  - class name -> "resolved to the class ... neither a CustomLogger instance
    nor a callable, so the proxy would never run it"
  - bare module name (no dot) -> "ValueError: Empty module name"
- Module discovery is relative to the config file's directory: put the .py
  next to config.yaml. If it still won't import, add
  `Environment=PYTHONPATH=<configdir>` to the service unit.
- Success-event kwargs: `kwargs.get("model")` is the upstream model
  (e.g. `agnes-3.0-flash`), `kwargs.get("model_group")` is usually None on
  the chat path — count on either field.

## 4. router_settings keys
`request_timeout` is NOT a valid Router arg (1.x): it is ignored with a
warning. Valid: `routing_strategy`, `num_retries`, `allowed_fails`,
`cooldown_time`, `fallbacks`, weight options. 429 responses put a
deployment in immediate cooldown (no further retries against it within
cooldown_time).

## 5. Verification that PROVES rotation (not just 200s)
- `curl -D - -o /dev/null ...` and read the response header
  `x-litellm-model-id` — it is the deployment's `model_info.id`; across a
  few requests it must vary between keys.
- `x-litellm-attempted-retries` / `x-litellm-attempted-fallbacks` show the
  reliability path actually fired.
- SSE: one request with `"stream":true` returning `data:` chunks confirms the
  agent path (agents always stream).
- End-to-end agent check: after the agent restarts, new
  `POST /v1/chat/completions` lines from 127.0.0.1 appear in the gateway's
  journal within seconds of the agent's first LLM call.

## 6. Budget keys and the sqlite spend table
`general_settings.database: "sqlite:////path/db"` may create a 0-byte file
with NO tables initialized (observed). Don't build counters on that table
until `SELECT name FROM sqlite_master` shows the spend tables. The callback
logfile (templates/usage_tracker.py) is the reliable counter.

## 7. systemd user units at boot
- `systemctl --user enable` alone does NOT start the unit after boot.
- `loginctl enable-linger <user>` (verify: `loginctl show-user <user>`
  shows `Linger=yes`), then enable.

## 8. Agent-side restarts
When the gateway hosts the very agent doing the work (e.g. Hermes gateway
process reading its own config), the platform blocks killing it from within.
Do `hermes gateway restart` (or equivalent) in a SEPARATE shell; before that,
prove the new config path works by firing OpenAI-format requests from a
terminal (200 + real content), then restart.

## 9. Provider auth quirks observed
- Some providers (e.g. SenseNova token API) accept BOTH `Authorization:
  Bearer sk-...` and raw `Authorization: sk-...`; standard Bearer is fine —
  after a 401 retest the documented Bearer form first, don't invent hacks.
- Always bisect key problems by curling the UPSTREAM directly (both auth
  forms) before blaming the gateway: distinguishes "bad key", "IP allowlist",
  and "gateway misconfig" in one step.
