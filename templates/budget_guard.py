#!/usr/bin/env python3
"""Budget guard: a provider key with a FIXED round budget (e.g. ~200 rounds,
then it stops paying) must never sit in the automatic fallback chain, or
routine agent traffic burns it to zero.

Count gateway-logged calls to the budget group (usage.log, written by
templates/usage_tracker.py); when the soft cap is hit, HOT-REMOVE the
deployment via the router API so the budget key serves nothing more.
Re-activate manually after buying more: re-add the deployment + clear the
state file.

Schedule: run every few minutes (systemd timer; see litellm-gateway.service).
"""
import json
import os
import urllib.request
import urllib.error

BASE = "http://localhost:4000"
TOKEN_FILE = "/home/<user>/litellm/master_key.txt"   # chmod 600
LOG = "/home/<user>/litellm/usage.log"
STATE = "/home/<user>/litellm/budget_guard_state.json"
STATUS = "/home/<user>/litellm/budget_status.json"
GROUP = "budget-tier"       # the model_name to guard
CAP = 190                  # soft cap under the hard budget
# litellm_params must MATCH the config deployment exactly for delete to work:
DEPLOY = {
    "model": "openai/<budget-model-id>",
    "api_base": "https://provider-c.example/v1",
    "model_id": "prov-c-key-1",
}


def main():
    used = 0
    if os.path.exists(LOG):
        for line in open(LOG):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if GROUP in (o.get("model_group"), o.get("model")):
                used += 1
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"disabled": False}
    if not state["disabled"] and used >= CAP:
        try:
            req = urllib.request.Request(
                f"{BASE}/router/models/delete", method="POST",
                headers={"Authorization": f"Bearer {open(TOKEN_FILE).read().strip()}",
                         "Content-Type": "application/json"},
                data=json.dumps({"model": GROUP, "litellm_params": DEPLOY}).encode(),
            )
            urllib.request.urlopen(req, timeout=10)
            state["disabled"] = True
            state["used_at_disable"] = used
            print(f"budget cap hit ({used}>={CAP}) — deployment hot-removed")
        except urllib.error.HTTPError as e:
            print(f"delete failed: {e.code} {e.read().decode()[:200]}")
        with open(STATE, "w") as f:
            json.dump(state, f)
    with open(STATUS, "w") as f:
        json.dump({"used": used, "cap": CAP, "active": not state["disabled"]}, f)
    print(f"budget {GROUP}: used={used}/{CAP} active={not state['disabled']}")


if __name__ == "__main__":
    main()
