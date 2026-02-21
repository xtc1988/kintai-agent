# 既知の問題 (Known Issues)

> 最終更新: 2026-02-22

---

## 重大な問題 (Critical)

<!--
### 問題タイトル
**発見日:** YYYY-MM-DD
**影響範囲:** [影響を受ける機能・ユーザー]
**回避策:** [一時的な対処法があれば記載]
**追跡:** [GitHub Issue #番号]
-->

現在、重大な問題はありません。

---

## 対応中の問題 (Active)

<!--
### 問題タイトル
**ステータス:** 調査中 / 対応中
**説明:** [問題の概要]
**次のステップ:** [次に行うべきこと]
-->

現在、対応中の問題はありません。

---

## 解決済みの問題 (Resolved)

<!--
### 問題タイトル
**解決日:** YYYY-MM-DD
**根本原因:** [原因の説明]
**解決方法:** [どのように修正したか]
**再発防止策:** [今後の防止策]
-->

### [FIXED] pyproject.toml build-backend指定エラー
**解決日:** 2026-02-22
**根本原因:** 仕様書に記載の `setuptools.backends._legacy:_Backend` は存在しないモジュール
**解決方法:** `setuptools.build_meta` に修正
**再発防止策:** TROUBLESHOOTING.md に記録済み

### [FIXED] setuptools flat-layout 複数パッケージエラー
**解決日:** 2026-02-22
**根本原因:** 複数トップレベルパッケージ（graph, services, schedulers）をflat-layoutで自動検出不可
**解決方法:** `[tool.setuptools.packages.find]` にinclude設定追加
**再発防止策:** TROUBLESHOOTING.md に記録済み

### [FIXED] テスト日付が天皇誕生日と重複
**解決日:** 2026-02-22
**根本原因:** 2026-02-23は天皇誕生日のため、平日テストに使用不可
**解決方法:** テスト日付を2026-02-24（火曜日）に変更
**再発防止策:** 祝日テストでは `jpholiday.is_holiday()` で事前確認すること

### [FIXED] Python 3.10環境でpynput未インストール
**解決日:** 2026-02-22
**根本原因:** `pip install` がvenv(Python 3.12)にインストールし、実行環境(Python 3.10)にはインストールされなかった
**解決方法:** Python 3.10に直接 `pip install pynput` を実行
**再発防止策:** `python --version` と `which python` で実行環境を確認してからインストールすること

### [FIXED] pytest-asyncio asyncio_mode未設定
**解決日:** 2026-02-22
**根本原因:** pyproject.tomlに `asyncio_mode = "auto"` がないとasyncテストが動かない
**解決方法:** `[tool.pytest.ini_options]` に `asyncio_mode = "auto"` を追加
**再発防止策:** asyncテストを使う場合は必ずpyproject.tomlに設定すること
