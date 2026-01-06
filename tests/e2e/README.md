# E2Eテスト

Notebook `12_data_pipeline_v2.ipynb` の動作を検証するE2Eテストです。

## 目的

Notebookのコードフロー（Cell 0-20）をそのまま自動実行し、実際のOCI/DBで動作確認します。

## 前提条件

1. `.env`ファイルが設定済み
2. データベーステーブルが作成済み（`11_create_table.ipynb`実行済み）
3. Object Storageにファイルが存在

## 実行方法

```bash
pytest tests/e2e/ -v
```

## テスト内容

**TestNotebookMainFlow::test_notebook_pipeline_execution**

Notebookの以下のセルを再現：
- Cell 6: 設定読み込みとDB接続
- Cell 8: パラメータ設定
- Cell 10: 全コンポーネント初期化
- Cell 12: DataPipeline作成
- Cell 14: `loader.list_files()` でObject Storageから全ファイル取得
- Cell 16: `pipeline.process_all()` で全ファイル処理
- Cell 20: DB接続クローズ

**検証項目**:
- 全ファイルが処理される（成功/失敗/スキップ）
- progress_callbackが呼ばれる
- 成功したファイルのドキュメントとチャンクがDBに保存される

## クリーンアップ

テスト終了後、作成したドキュメントとチャンクは自動的にDBから削除されます。
