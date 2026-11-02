# LiteLLM custom success callback: append one JSON line per successful
# completion so a guard timer can count calls per model group.
#
# WIRE-UP (gotchas verified 2026-11, litellm 1.106.x):
#  * config.yaml:  litellm_settings:\n  callbacks: ["usage_tracker.usage_tracker"]
#    - the entry is module.instance. Instance, NOT class (class -> startup
#      crash: "resolved to the class ... neither a CustomLogger instance
#      nor a callable").
#    - bare "usage_tracker" (no dot) -> "ValueError: Empty module name".
#  * put this file NEXT TO config.yaml (module resolves relative to the
#    config dir). If import still fails, add Environment=PYTHONPATH=<configdir>
#    to the systemd unit.
import json
from litellm.integrations.custom_logger import CustomLogger

LOG = "/home/<user>/litellm/usage.log"  # absolute path, same dir as this file


class UsageTracker(CustomLogger):
    def _track(self, kwargs):
        try:
            with open(LOG, "a") as f:
                f.write(json.dumps(
                    {"model_group": kwargs.get("model_group"),
                     "model": kwargs.get("model")}
                ) + "\n")
        except Exception:
            pass

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._track(kwargs)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._track(kwargs)


# module-level instance — THIS is what config.yaml's callbacks[] points at
usage_tracker = UsageTracker()
