# 勤怠エージェント (kintai-agent)

> PC稼働監視 + 自動打刻 LangGraphエージェント

---

## プロジェクト概要

PC操作（マウス移動、キーボード操作）をリアルタイム監視し、社内勤怠システムへの打刻を自動実行するエージェントです。

- **ルールベース設計** -- AI（LLM）は一切使用していません
- **LangGraph** はワークフロー（ステートマシン）管理のみに使用
- 祝日・有給の自動判定、時間帯に応じた出勤/退勤の自動切替
- Slack通知による打刻結果のリアルタイム報告
- 全外部サービスにフォールバック実装済み

---

## 技術スタック

| 役割 | 技術 |
|------|------|
| ワークフロー管理 | LangGraph |
| PC操作監視 | pynput |
| ブラウザ自動操作 | Playwright (Python) |
| Slack通知 | slack-sdk |
| カレンダー | google-api-python-client + jpholiday |
| スケジューラ | APScheduler |
| 設定管理 | PyYAML + python-dotenv |

---

## ディレクトリ構成

```
attendance-agent/
├── main.py                          # エントリーポイント
├── config.yaml                      # 動作設定
├── .env.example                     # 環境変数テンプレート
├── pyproject.toml                   # 依存関係
├── graph/
│   ├── state.py                     # AttendanceState TypedDict
│   ├── graph.py                     # LangGraphグラフ定義
│   └── nodes/
│       ├── working_state_node.py    # PC稼働判定
│       ├── calendar_check_node.py   # 祝日・有給判定
│       ├── time_gate_node.py        # 時刻ルール判定
│       ├── stamp_node.py            # 打刻実行
│       ├── slack_notify_node.py     # Slack通知
│       └── state_update_node.py     # 状態更新
├── services/
│   ├── pc_monitor.py                # pynput PC監視
│   ├── stamper_interface.py         # 打刻インターフェース(ABC)
│   ├── dummy_stamper.py             # ダミー打刻（テスト用）
│   ├── attendance_browser.py        # Playwright打刻（本番用）
│   ├── google_calendar.py           # Googleカレンダー + jpholiday
│   ├── slack_client.py              # Slack + Console通知
│   └── config_loader.py             # YAML設定読み込み
├── schedulers/
│   └── scheduler.py                 # APScheduler定期実行
└── tests/                           # 全57テスト
    ├── conftest.py
    ├── test_state.py
    ├── test_working_state.py
    ├── test_pc_monitor.py
    ├── test_config_loader.py
    ├── test_calendar_check.py
    ├── test_calendar_check_node.py
    ├── test_time_gate.py
    ├── test_stamp.py
    ├── test_stamp_node.py
    ├── test_dummy_stamper.py
    ├── test_slack_client.py
    ├── test_slack_notify_node.py
    ├── test_state_update_node.py
    ├── test_graph.py
    └── test_scheduler.py
```

---

## セットアップ

### 前提条件

- Python 3.10 以上
- pip

### インストール手順

```bash
cd attendance-agent
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env  # 編集して認証情報を設定
```

### 起動

```bash
python main.py
```

停止は `Ctrl+C` で行います。

---

## 動作フロー

6ノードのステートマシンが APScheduler により定期実行（デフォルト5分間隔）されます。

```
WorkingStateNode (PC稼働判定)
    |
    | is_working=True
    v
CalendarCheckNode (祝日・有給判定)
    |
    | is_holiday=False
    v
TimeGateNode (時刻ルール判定)
    |
    | action決定
    v
StampNode (打刻実行)
    |
    v
SlackNotifyNode (結果通知)
    |
    v
StateUpdateNode (状態更新)
```

各ノードの間に条件分岐があり、条件を満たさない場合は早期終了（スキップ）します。

- `is_working=False` の場合 -- WorkingStateNode で終了
- `is_holiday=True` の場合 -- CalendarCheckNode で終了
- `action_taken="skipped"` の場合 -- TimeGateNode で終了

---

## TimeGateルール表

TimeGateNode は現在時刻と出勤打刻の状態に基づき、実行すべきアクションを決定します。

| 時間帯 | 出勤打刻済み | 判定 |
|--------|-------------|------|
| 22:00以降 | - | スキップ（打刻禁止時間帯） |
| ~18:00 | False | 出勤打刻 |
| ~18:00 | True | スキップ（既に打刻済み） |
| 18:00~22:00 | True | 退勤打刻 |
| 18:00~22:00 | False | 出勤打刻 + 退勤打刻（両方実行） |

---

## 設定

### config.yaml

チェック間隔、時刻ルール、ブラウザセレクタなどの動作設定を管理します。

```yaml
scheduler:
  check_interval_minutes: 5

working_state:
  window_minutes: 15
  min_event_count: 2

time_rules:
  clock_out_time: "18:00"
  cutoff_time: "22:00"

browser:
  headless: true
  retry_count: 3
  stamper: "dummy"       # "dummy" or "playwright"
  selectors:
    login_url: "https://your-system.example.com/login"
    clock_in_button: "#clock-in"
    clock_out_button: "#clock-out"
    # ... その他セレクタ

slack:
  enabled: true
  fallback: "console"

calendar:
  enabled: true
  fallback: "jpholiday"
```

### .env

認証情報（Slack、Google Calendar、社内システム）を環境変数として管理します。`.env.example` をコピーして編集してください。

```
# 勤怠システム
ATTENDANCE_URL=https://your-system.example.com
ATTENDANCE_USER=your_user_id
ATTENDANCE_PASS=your_password

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_NOTIFY_CHANNEL=DXXXXXXXX

# Google Calendar
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_TOKEN_PATH=token.json
HOLIDAY_CALENDAR_ID=ja.japanese#holiday@group.v.calendar.google.com
```

### 打刻モードの切り替え

`config.yaml` の `browser.stamper` で切り替えが可能です。

| モード | 説明 |
|--------|------|
| `"dummy"` | DummyStamper -- 実際の打刻は行わずログ出力のみ（テスト・開発用） |
| `"playwright"` | AttendanceBrowser -- Playwrightでブラウザ操作して実際に打刻（本番用） |

---

## フォールバック設計

全ての外部サービスにフォールバック実装を備えており、サービス障害時も安全に動作します。

| サービス | 本番実装 | フォールバック |
|----------|---------|---------------|
| 打刻 | Playwright (AttendanceBrowser) | DummyStamper (ログ出力のみ) |
| 通知 | Slack (SlackNotifier) | Console (ConsoleNotifier) |
| カレンダー | Google Calendar API | jpholiday + 土日判定 |

---

## テスト

全57件のテストが用意されています。

### 全テスト実行

```bash
cd attendance-agent
python -m pytest tests/ -v
```

### ファイル単位で実行

```bash
python -m pytest tests/test_stamp.py -v
```

### 特定のテスト関数のみ実行

```bash
python -m pytest tests/test_stamp.py::test_stamp_clock_in_success -v
```

### テストファイル一覧

| ファイル | テスト対象 |
|----------|-----------|
| `test_state.py` | AttendanceState 型定義 |
| `test_working_state.py` | WorkingStateNode |
| `test_pc_monitor.py` | PCMonitor サービス |
| `test_config_loader.py` | 設定ローダー |
| `test_calendar_check.py` | カレンダーサービス |
| `test_calendar_check_node.py` | CalendarCheckNode |
| `test_time_gate.py` | TimeGateNode |
| `test_stamp.py` | AttendanceBrowser / StampResult |
| `test_stamp_node.py` | StampNode |
| `test_dummy_stamper.py` | DummyStamper |
| `test_slack_client.py` | SlackNotifier / ConsoleNotifier |
| `test_slack_notify_node.py` | SlackNotifyNode |
| `test_state_update_node.py` | StateUpdateNode |
| `test_graph.py` | LangGraph グラフ定義・ルーティング |
| `test_scheduler.py` | APScheduler スケジューラ |

---

## 関連ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | システムアーキテクチャ |
| [docs/HANDOVER.md](docs/HANDOVER.md) | 引き継ぎ資料（他AI向け） |
| [docs/FAQ.md](docs/FAQ.md) | よくある質問 |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | 既知の問題 |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | トラブルシューティング |
| [docs/plans/2026-02-22-attendance-agent.md](docs/plans/2026-02-22-attendance-agent.md) | 実装計画 |
| [attendance_agent_spec.md](attendance_agent_spec.md) | 元の仕様書 |

---

## ライセンス

Private -- 社内利用限定
