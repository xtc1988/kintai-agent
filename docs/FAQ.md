# よくある質問 (FAQ)

> 最終更新: 2026-02-23

---

## 一般 (General)

<!--
### Q: 質問内容
**A:** 回答内容
-->

### Q: プロジェクトをローカルで実行するには？
**A:** 以下の手順で実行できます:
```bash
cd attendance-agent
pip install -e ".[dev]"
cp .env.example .env  # 編集して認証情報を設定
python main.py
```

### Q: 環境変数はどこで設定する？
**A:** `attendance-agent/.env` ファイルに記載。`.env.example` をコピーして編集。Gitには含まれません。

---

## 開発 (Development)

<!--
### Q: 質問内容
**A:** 回答内容
```bash
# 必要であればコマンド例を記載
```
-->

### Q: 設定を変更するには？
**A:** `attendance-agent/config.yaml` を編集。チェック間隔、時刻ルール、ブラウザセレクタなどを変更可能。

### Q: 打刻モードを切り替えるには？（DummyStamper / Playwright）
**A:** `config.yaml` の `browser.stamper` を変更:
```yaml
browser:
  stamper: "dummy"       # ダミー打刻（ログ出力のみ）
  # stamper: "playwright"  # Playwright実装（本番用）
```
- `"dummy"`: DummyStamperが使われ、実際の打刻は行わずログ出力のみ
- `"playwright"`: AttendanceBrowserが使われ、Playwrightでブラウザ操作して打刻

### Q: 社内システムのセレクタを設定するには？
**A:** `config.yaml` の `browser.selectors` セクションを編集:
```yaml
browser:
  selectors:
    login_url: "https://your-system.com/login"
    username_field: "#your-username-field"
    clock_in_button: "#your-clock-in-btn"
```

---

## テスト (Testing)

<!--
### Q: 質問内容
**A:** 回答内容
```bash
# 必要であればコマンド例を記載
```
-->

### Q: テストを実行するには？
**A:**
```bash
cd attendance-agent
python -m pytest tests/ -v
```

### Q: 特定のテストだけ実行するには？
**A:**
```bash
python -m pytest tests/test_stamp.py -v          # ファイル単位
python -m pytest tests/test_stamp.py::test_stamp_clock_in_success -v  # テスト単位
```

---

## 関連ドキュメント

- **既知の問題:** [KNOWN_ISSUES.md](./KNOWN_ISSUES.md)
- **トラブルシューティング:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
