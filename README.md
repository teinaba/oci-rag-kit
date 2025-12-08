# OCI RAG Kit
本リポジトリは個人による非公式サンプルです。Oracle公式の配布物ではありません。

Oracle Database 26ai のベクトル検索と OCI Generative AI Service を活用した日本語向け RAG（Retrieval-Augmented Generation）環境を簡単に構築できるKitです。  

本リポジトリは以下を提供します:
- Oracle AI Database 上のドキュメント/ベクトルデータ格納スキーマの構築
- OCI Object Storage からのドキュメント取り込み～チャンク化～Embedding～DB保存のパイプライン
- ベクトル検索 + 再ランク + LLM回答生成、および RAGAS による品質評価
  - FAQ一覧ファイルの一括実行によるRAG回答精度評価を効率化します

## リポジトリ構成

```
.
├── .gitignore
├── .env.template                  # 環境変数テンプレート（これを .env にコピーして編集してください）
├── notebooks
│   ├── 11_create_table.ipynb      # DBテーブル作成
│   ├── 12_data_pipeline.ipynb     # 取込/チャンク/Embedding/DB保存
│   ├── 13_rag.ipynb               # 検索/再ランク/回答生成/評価
│   └── config_loader.py           # 設定読み込みユーティリティ
├── README.md
└── setup
    ├── environment.yaml           # conda 環境定義
    └── setup.sh                   # 環境セットアップ補助スクリプト
```

## 前提条件
- Oracle Autonomous AI Database 26ai
- OCIリソース(Object Storage、Generative AI Service, Data Science) へのアクセス

## セットアップ
- 初期設定
  - `cp .env.template .env`
  - .env を編集して必要な値を設定
  - `python notebooks/config_loader.py` で読み込みテスト
- セットアップスクリプト（conda）
  - Data Science上のターミナルで以下を実行
    - `cd setup`
    - `bash setup.sh`

## 設定

1) OCI 認証 (~/.oci/config)
- OCI コンソールで API キーを作成し、~/.oci/config を用意
- 例:
  - [DEFAULT]
    user=ocid1.user.oc1..xxxxxxxx
    fingerprint=aa:bb:...
    tenancy=ocid1.tenancy.oc1..xxxxxxxx
    region=ap-osaka-1
    key_file=~/.oci/oci_api_key.pem

2) .env（機密値はここに保持）
- .env.template をコピーして .env を作成し、以下を設定
  - DB_USERNAME, DB_PASSWORD, DB_DSN
  - OCI_CONFIG_FILE（省略時 ~/.oci/config）
  - OCI_PROFILE（省略時 DEFAULT）
  - OCI_COMPARTMENT_ID
  - OCI_GENAI_ENDPOINT（例: https://inference.generativeai.ap-osaka-1.oci.oraclecloud.com）
  - OCI_EMBED_MODEL（例: cohere.embed-v4.0）
  - OCI_LLM_MODEL（例: cohere.command-a-03-2024 または cohere.command-a-03-2025 など）
  - OCI_BUCKET_NAME, OCI_NAMESPACE（Object Storage 用）
  - CHUNK_SIZE（例: 500）, CHUNK_OVERLAP（例: 50）, TOP_K（例: 5）

## 使い方（Notebook）

1) 11_create_table.ipynb（テーブル作成）
- source_documents, chunks テーブルを作成
- 既存の場合は作成済みメッセージが出力
- テーブル構造・中身の確認ユーティリティあり
- 注意: TRUNCATE/DROP はコメントアウトを外すと実行されます。必要時のみ実行してください

2) 12_data_pipeline.ipynb（データ取り込み）
- Object Storage バケットからファイル一覧を取得
- サポート形式: pdf, txt, csv
  - pdf: PyMuPDF で読込み
  - txt/csv: UTF-8 または Shift-JIS を自動判定
- チャンク分割（RecursiveCharacterTextSplitter）
- 埋め込み（OCIGenAIEmbeddings）
- DB へ保存（source_documents と chunks）
- タイムゾーンは Asia/Tokyo を使用（必要に応じて変更可）

3) 13_rag.ipynb（RAG 実行と評価）
- クエリを埋め込み → Oracle Database でベクトル検索（COSINE 距離）
- hotchpotch/japanese-reranker-base-v2 による Rerank（任意）
- Cohere ベースの LLM で回答生成（OCI Generative AI 経由）
- RAGAS（Faithfulness、AnswerCorrectness、ContextPrecision、ContextRecall）で評価
- 入出力（FAQ Excel）を Object Storage に保存/読込

## 設計メモ
- スキーマ
  - source_documents: ドキュメントのメタ情報（filename, filtering, content_type, file_size, text_length, registered_date）
  - chunks: chunk_text（CLOB）, embedding（VECTOR）, document_id（FK）
- ベクトル検索
  - VECTOR_DISTANCE(..., COSINE) を使用
  - 上位件数は TOP_K で調整
- タイムゾーン
  - 例: CAST(systimestamp AT TIME ZONE 'Asia/Tokyo' AS timestamp)

## Third-Party Notices / モデル・サービスの利用について
- 本プロジェクトは Reranker に「hotchpotch/japanese-reranker-base-v2」を利用します。モデル本体（重み）は同梱せず、ユーザー環境で取得されます。利用条件はモデル配布ページのライセンス・利用規約に従ってください（https://huggingface.co/hotchpotch/japanese-reranker-base-v2）。
- OCI Generative AI 経由で Cohere のモデルを利用します。OCI/Cohere の各利用条件に従ってください。

## 免責事項
- 本サンプルは参考実装です。運用環境に導入する場合は、セキュリティ/可用性/監査要件に合わせて十分な検証とレビューを行ってください。