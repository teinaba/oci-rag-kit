# OCI RAG Kit

> Oracle Database 26ai × OCI Generative AI で作る、日本語RAGシステムのスターターキット

![Oracle Cloud](https://img.shields.io/badge/Oracle%20Cloud-F80000?logo=oracle&logoColor=white)
![Oracle AI Database](https://img.shields.io/badge/Oracle%20AI%20Database-26ai-red)
![Autonomous Database](https://img.shields.io/badge/Autonomous%20Database-26ai-red)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3%2B-1C3C3C?logo=langchain&logoColor=white)
![RAGAS](https://img.shields.io/badge/RAGAS-evaluation-9cf)
![License](https://img.shields.io/badge/License-MIT-green)

本リポジトリは個人による非公式サンプルです。Oracle公式の配布物ではありません。

## Features

**Vector Search on Oracle Database 26ai**
ベクトル検索機能を使った高速な文書検索

**Automated Data Pipeline**
Object Storage → チャンク化 → Embedding → DB保存まで自動化

**Rerank & Multi-LLM Generation**
日本語Rerankerによる精度向上 + 12種類のLLMモデルから選択可能

**RAGAS Evaluation**
FAQ一括評価でRAG品質を定量測定

## Quick Start

```bash
# 1. 環境変数設定
cp .env.template .env
# .env を編集してOCI/DB接続情報を入力

# 2. 環境構築（conda）
cd setup && bash setup.sh

# 3. Notebookを順番に実行
# 11_create_table.ipynb    → DBテーブル作成
# 12_data_pipeline.ipynb   → データ取り込み
# 13_rag.ipynb             → RAG実行・評価
```

## Prerequisites

- Oracle Autonomous AI Database 26ai
- OCI リソースへのアクセス
  - Object Storage
  - Generative AI Service
  - Data Science (Notebook環境)

## Repository Structure

```
notebooks/          # Jupyter Notebooks
├── 11_create_table.ipynb
├── 12_data_pipeline.ipynb
└── 13_rag.ipynb

setup/              # 環境構築
├── environment.yaml
└── setup.sh

.env.template       # 環境変数テンプレート
```

## Configuration

<details>
<summary>詳細な設定手順（クリックで展開）</summary>

### 1. OCI 認証設定

`~/.oci/config` を作成：

```ini
[DEFAULT]
user=ocid1.user.oc1..xxxxxxxx
fingerprint=aa:bb:cc:dd:...
tenancy=ocid1.tenancy.oc1..xxxxxxxx
region=ap-osaka-1
key_file=~/.oci/oci_api_key.pem
```

### 2. 環境変数（.env）

`.env.template` をコピーして `.env` を作成し、以下を設定：

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `DB_USERNAME` | DB ユーザー名 | `ADMIN` |
| `DB_PASSWORD` | DB パスワード | `YourPassword123` |
| `DB_DSN` | DB 接続文字列 | `dbname_high` |
| `OCI_COMPARTMENT_ID` | コンパートメント OCID | `ocid1.compartment...` |
| `OCI_GENAI_ENDPOINT` | GenAI エンドポイント | `https://inference.generativeai.ap-osaka-1.oci.oraclecloud.com` |
| `OCI_EMBED_MODEL` | Embedding モデル | `cohere.embed-v4.0` |
| `OCI_LLM_MODEL` | LLM モデル | `cohere.command-a-03-2025` |
| `OCI_BUCKET_NAME` | バケット名 | `your-bucket` |
| `OCI_NAMESPACE` | Object Storage Namespace | `your-namespace` |
| `CHUNK_SIZE` | チャンクサイズ | `500` |
| `CHUNK_OVERLAP` | チャンクオーバーラップ | `50` |
| `TOP_K` | 検索上位件数 | `5` |

</details>

## Usage

### 1. `11_create_table.ipynb` - テーブル作成

データベーススキーマを初期化
- `source_documents` / `chunks` テーブル作成
- テーブル構造の確認ユーティリティ付き

### 2. `12_data_pipeline.ipynb` - データ取り込み

Object Storage → Database へのパイプライン
- サポート形式: PDF / TXT / CSV
- 自動エンコーディング検出（UTF-8 / Shift-JIS）
- チャンク分割 → Embedding → DB保存

### 3. `13_rag.ipynb` - RAG実行・評価

質問応答とパフォーマンス測定
- ベクトル検索（COSINE距離）
- 日本語Reranker適用
- 12種類のLLMモデルから選択可能な回答生成
- RAGAS評価（Faithfulness / Answer Correctness / Context Precision / Recall）

#### 対応LLMモデル

| モデルファミリー | モデルID |
|----------------|----------|
| **Cohere** | `cohere.command-a-03-2025` |
| | `cohere.command-r-plus-08-2024` |
| **Meta Llama** | `meta.llama-3.3-70b-instruct` |
| **xAI Grok** | `xai.grok-4-fast-non-reasoning` |
| | `xai.grok-4-fast-reasoning` |
| | `xai.grok-4` |
| **Google Gemini** | `google.gemini-2.5-pro` |
| | `google.gemini-2.5-flash` |
| | `google.gemini-2.5-flash-lite` |
| **OpenAI GPT-OSS** | `openai.gpt-oss-20b` |
| | `openai.gpt-oss-120b` |

## Architecture

<details>
<summary>技術仕様（クリックで展開）</summary>

### Database Schema

- `source_documents`: ドキュメントメタデータ
- `chunks`: チャンクテキスト（CLOB）+ ベクトル（VECTOR）

### Vector Search

- COSINE距離による類似度計算
- `VECTOR_DISTANCE()` 関数使用
- 検索件数は `TOP_K` で調整

### Timezone

- デフォルト: `Asia/Tokyo`
- `CAST(systimestamp AT TIME ZONE 'Asia/Tokyo' AS timestamp)`

</details>

## Licenses & Notices

### Third-Party Models

**Japanese Reranker**
- [hotchpotch/japanese-reranker-base-v2](https://huggingface.co/hotchpotch/japanese-reranker-base-v2)
- モデル本体は同梱せず、実行時に取得されます

**OCI Generative AI**
- 複数のLLMモデルを利用可能（Cohere, Meta Llama, xAI Grok, Google Gemini, OpenAI GPT-OSS）
- 各モデルの利用規約に従ってください

### Disclaimer

本サンプルは参考実装です。運用環境へ導入する場合は、セキュリティ・可用性・監査要件に合わせて十分な検証を実施してください。

---

**Built with Oracle Autonomous AI Database 26ai** ♥