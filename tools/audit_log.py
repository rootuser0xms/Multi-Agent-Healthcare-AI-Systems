import json
from datetime import datetime, timezone
import os

LOG_PATH = "data/audit_log.jsonl"

def log_action(agent_name, action, details, result_summary=None):
    """Append a structured audit entry. One JSON object per line (JSONL format)."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "action": action,
        "details": details,
        "result_summary": result_summary,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry