import os
import tempfile
from services.config_loader import load_config


def test_load_config_defaults():
    """デフォルト設定が正しくロードされること"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("scheduler:\n  check_interval_minutes: 10\n")
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["scheduler"]["check_interval_minutes"] == 10


def test_load_config_nested():
    """ネストされた設定が正しく取得できること"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            "working_state:\n"
            "  window_minutes: 15\n"
            "  min_event_count: 2\n"
        )
        f.flush()
        config = load_config(f.name)
    os.unlink(f.name)
    assert config["working_state"]["window_minutes"] == 15
    assert config["working_state"]["min_event_count"] == 2


def test_load_config_file_not_found():
    """存在しないファイルの場合デフォルト設定を返すこと"""
    config = load_config("nonexistent.yaml")
    assert "scheduler" in config
    assert config["scheduler"]["check_interval_minutes"] == 5
