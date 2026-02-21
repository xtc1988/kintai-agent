import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "scheduler": {
        "check_interval_minutes": 5,
    },
    "working_state": {
        "window_minutes": 15,
        "min_event_count": 2,
    },
    "time_rules": {
        "clock_out_time": "18:00",
        "cutoff_time": "22:00",
    },
    "browser": {
        "headless": True,
        "retry_count": 3,
        "session_storage_path": ".session",
        "selectors": {
            "login_url": "",
            "username_field": "#username",
            "password_field": "#password",
            "login_button": "#login-btn",
            "clock_in_button": "#clock-in",
            "clock_out_button": "#clock-out",
            "success_message": ".success-msg",
        },
    },
    "slack": {
        "enabled": True,
        "notify_channel": "",
        "fallback": "console",
    },
    "calendar": {
        "enabled": True,
        "fallback": "jpholiday",
        "holiday_calendar_id": "ja.japanese#holiday@group.v.calendar.google.com",
        "vacation_keywords": ["有給", "年休", "休暇"],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """ベース設定にオーバーライドをマージする"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str = "config.yaml") -> dict:
    """YAML設定ファイルをロードし、デフォルト設定とマージして返す"""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, user_config)
    return DEFAULT_CONFIG.copy()
