# トラブルシューティングガイド

> 最終更新: 2026-02-22

よくある問題とその解決策をまとめています。

## 目次
- [ビルドの問題](#ビルドの問題)
- [実行時エラー](#実行時エラー)
- [環境設定の問題](#環境設定の問題)
- [デプロイの問題](#デプロイの問題)

---

## ビルドの問題

<!--
### 問題タイトル
**症状:**
```
エラーメッセージをここに記載
```
**原因:** [原因の説明]
**解決方法:**
```bash
# 解決コマンド
```
**予防策:** [再発を防ぐ方法]
-->

### pyproject.toml の build-backend エラー (Cannot import 'setuptools.backends._legacy')

**症状:**
```
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.backends._legacy'
```
**原因:** `setuptools.backends._legacy:_Backend` は存在しないモジュール。正しいビルドバックエンドは `setuptools.build_meta`。
**解決方法:**
```toml
# pyproject.toml の [build-system] セクションを以下に修正
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```
**予防策:** pyproject.toml作成時はbuild-backendに `setuptools.build_meta` を使うこと。

---

### setuptools flat-layout で複数パッケージ検出エラー

**症状:**
```
error: Multiple top-level packages discovered in a flat-layout: ['graph', 'services', 'schedulers'].
```
**原因:** setuptoolsの自動パッケージディスカバリがflat-layoutで複数トップレベルパッケージを拒否する。
**解決方法:**
```toml
# pyproject.toml に明示的パッケージディスカバリ設定を追加
[tool.setuptools.packages.find]
include = ["graph*", "services*", "schedulers*"]
```
**予防策:** 複数トップレベルパッケージがある場合は必ず `[tool.setuptools.packages.find]` で明示的にincludeを指定する。

---

## 実行時エラー

<!--
### 問題タイトル
**症状:** [どのような症状が出るか]
**原因:** [原因の説明]
**解決方法:** [手順を記載]
**参考:** [関連ドキュメントへのリンク]
-->

現在、記録された実行時エラーはありません。

---

## 環境設定の問題

<!--
### 問題タイトル
**症状:** [どのような症状が出るか]
**原因:** [原因の説明]
**解決方法:** [手順を記載]
-->

現在、記録された環境設定の問題はありません。

---

## デプロイの問題

<!--
### 問題タイトル
**症状:** [どのような症状が出るか]
**原因:** [原因の説明]
**解決方法:** [手順を記載]
-->

現在、記録されたデプロイの問題はありません。
