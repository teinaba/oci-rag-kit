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

- **Vector Search on Oracle Database 26ai**
  - ベクトル検索機能を使った高速な文書検索

- **Automated Data Pipeline**
  - Object Storage → チャンク化 → Embedding → DB保存まで自動化

- **Rerank & Multi-LLM Generation**
  - 日本語Rerankerによる精度向上 + 12種類のLLMモデルから選択可能

- **RAGAS Evaluation**
  - FAQ一括評価でRAG品質を定量測定

## Setup

### インフラ構築

OCI上にRAG環境を構築する方法は2つあります:

| 方法 | 説明 |
|------|------|
| **[Terraform 自動構築](infra/terraform/README.md)** | Cloud Shell から一括構築（推奨） |
| **[手動構築](infra/manual-setup.md)** | OCI コンソールで各リソースを個別作成 |

詳細は **[infra/README.md](infra/README.md)** を参照してください。

構築されるリソース:
- Virtual Cloud Network (VCN)
- Autonomous AI Database 26ai
- Object Storage
- Data Science Notebook環境


### Quick Start（環境構築済みの場合）

```bash
# 1. 環境変数設定（詳細は infra/manual-setup.md 参照）
# .env ファイルを作成してOCI/DB接続情報を入力

# 2. 環境構築（conda）
cd setup && bash setup.sh

# 3. Notebookを順番に実行
# 01_setup_database.ipynb  → DBテーブル作成
# 02_data_pipeline.ipynb   → データ取り込み
# 03_rag.ipynb             → RAG実行・評価
```

## Prerequisites

- OCIコンパートメント
  - コンパートメントの管理権限が必要

詳細は [infra/README.md](infra/README.md) を参照してください。

## Repository Structure

```bash
infra/                   # インフラ構築
├── README.md            # 構築方法の選択ガイド
├── manual-setup.md      # 手動構築ガイド
└── terraform/           # Terraform 自動構築
    ├── README.md        # Terraform 構築ガイド
    └── *.tf

notebooks/               # Jupyter Notebooks
├── 01_setup_database.ipynb
├── 02_data_pipeline.ipynb
└── 03_rag.ipynb

src/                     # ソースコード
├── config/              # 設定管理モジュール
├── data_pipeline/       # データパイプラインクラス群
└── rag/                 # RAG処理クラス群

setup/                   # 環境構築
├── environment.yaml
└── setup.sh
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

プロジェクトルートに `.env` を作成し、以下を設定（詳細は `infra/manual-setup.md` の手順6.5を参照）：

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `DB_USERNAME` | DB ユーザー名 | `rag` |
| `DB_PASSWORD` | DB パスワード | `YourPassword123` |
| `DB_DSN` | DB 接続文字列 | `(description=...)` |
| `OCI_COMPARTMENT_ID` | コンパートメント OCID | `ocid1.compartment...` |
| `OCI_REGION` | リージョン名 | `us-chicago-1`, `ap-osaka-1` |
| `OCI_BUCKET_NAME` | バケット名 | `rag-source` |

**注:** エンドポイントはリージョン名から自動生成されます。LLM/Embeddingモデルはデフォルト値があります。

</details>

## Usage

### 1. `01_setup_database.ipynb` - テーブル作成

データベーススキーマを初期化
- `source_documents` / `chunks` テーブル作成
- テーブル構造の確認ユーティリティ付き

### 2. `02_data_pipeline.ipynb` - データ取り込み

Object Storage → Database へのパイプライン
- サポート形式: PDF / TXT / CSV
- 自動エンコーディング検出（UTF-8 / Shift-JIS）
- チャンク分割 → Embedding → DB保存

### 3. `03_rag.ipynb` - RAG実行・評価

質問応答とパフォーマンス測定
- ベクトル検索（COSINE距離）
- 日本語Reranker適用
- 12種類のLLMモデルから選択可能な回答生成
- RAGAS評価（Faithfulness / Answer Correctness / Context Precision / Recall）

#### 対応LLMモデル
- **注) Google Geminiモデルの利用時に出力が途切れて保存されてしまうBugがあります。**
- まずは、`command-a` か `grok-4-fast-non-reasoning` の利用をおすすめします。
- 各モデルごとの[利用料金](https://www.oracle.com/jp/cloud/price-list/#pricing-ai)を確認の上ご利用ください

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