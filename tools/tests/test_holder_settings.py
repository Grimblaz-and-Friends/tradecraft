import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_project_settings_register_the_holder_hook_for_every_write_surface():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_bytes())
    assert settings["hooks"]["PreToolUse"] == [{
        "matcher": "Edit|Write|NotebookEdit|Bash|PowerShell",
        "hooks": [{"type": "command", "command": "python lib/holder_tree_guard.py"}],
    }]
