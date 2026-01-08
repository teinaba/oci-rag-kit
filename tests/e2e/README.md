# E2Eテスト

Notebook `12_data_pipeline_v2.ipynb` と `13_rag_v2.ipynb` の動作を検証するE2Eテストです。

## 目的

Notebookのコードフローをそのまま自動実行し、実際のOCI/DBで動作確認します。

## 前提条件

### 共通
1. `.env`ファイルが設定済み
2. データベーステーブルが作成済み（`11_create_table.ipynb`実行済み）
3. Conda環境がアクティベート済み（`conda activate rag_env`）

### データパイプラインテスト (`test_e2e_pipeline.py`)
- Object Storageにファイルが存在

### RAGテスト (`test_e2e_rag_pipeline.py`)
- データベースにドキュメントとチャンクが登録済み（`12_data_pipeline_v2.ipynb`実行済み）
- OCI Generative AI APIへのアクセス権限
- （推奨）FAQファイルがObject Storageに存在（実際のE2Eテスト実行のため）
  - 存在しない場合は、テスト用データにフォールバック

## 実行方法

### 全テストの実行
```bash
conda activate rag_env
pytest tests/e2e/ -v
```

### 個別テストの実行
```bash
# データパイプラインのみ
pytest tests/e2e/test_e2e_pipeline.py -v

# RAGパイプラインのみ
pytest tests/e2e/test_e2e_rag_pipeline.py -v
```

## テスト内容

### 1. データパイプライン (`test_e2e_pipeline.py`)

**テストクラス**: `TestNotebookMainFlow::test_notebook_pipeline_execution`

**対象ノートブック**: `12_data_pipeline_v2.ipynb`

**再現セル**:
- Cell 4: 設定読み込みとDB接続
- Cell 6: パラメータ設定
- Cell 8: 全コンポーネント初期化 + DataPipeline作成
- Cell 10: `loader.list_files()` でObject Storageから全ファイル取得
- Cell 12: `pipeline.process_all()` で全ファイル処理
- Cell 14: DB接続クローズ

**検証項目**:
- ✅ 全ファイルが処理される（成功/失敗/スキップ）
- ✅ progress_callbackが呼ばれる
- ✅ 成功したファイルのドキュメントとチャンクがDBに保存される
- ✅ チャンク数が正しい

### 2. RAGパイプライン (`test_e2e_rag_pipeline.py`)

**テストクラス**: `TestNotebookRAGFlow::test_notebook_rag_pipeline_execution`

**対象ノートブック**: `13_rag_v2.ipynb`

**再現セル**:
- Cell 4: 設定読み込みとDB接続
- Cell 6: RAGパラメータ設定
- Cell 8: RAGコンポーネント初期化 + RAGPipeline作成
- Cell 10: FAQファイル読み込み（テスト用データを使用）
- Cell 12: `pipeline.process_batch()` で全質問を処理
- Cell 14: DB接続クローズ

**検証項目**:
- ✅ 全質問が処理される（成功/失敗）
- ✅ progress_callbackが呼ばれる
- ✅ 成功した質問に回答が生成される
- ✅ コンテキストが取得される
- ✅ メタデータが正しく生成される
- ✅ 処理時間が計測される

**テスト用データ**:
```python
# 3つのサンプル質問を使用
test_faq_dataframe = pd.DataFrame({
    'id': [1, 2, 3],
    'question': [
        'Oracle Databaseとは何ですか？',
        'ベクトル検索の利点は何ですか？',
        'RAGシステムの主要なコンポーネントは何ですか？'
    ],
    'ground_truth': [...],
    'filter': ['', '', '']
})
```

## クリーンアップ

### データパイプラインテスト
テスト終了後、作成したドキュメントとチャンクは自動的にDBから削除されます（`cleanup_test_documents` fixture）。

### RAGテスト
RAGテストはデータベースへの書き込みを行わないため、クリーンアップは不要です。

## 注意事項

### 実行時間
- データパイプラインテスト: 数分〜数十分（ファイル数による）
- RAGテスト: 数分（LLM API呼び出し × 質問数）

### コスト
- OCI Generative AI APIの**実行コスト**が発生します（RAGテストのみ）
- 開発環境での実行を推奨

### エラーハンドリング
- HTTP 429（Rate Limit）エラーが発生する可能性があります
- AnswerGeneratorには自動リトライ機能があります
