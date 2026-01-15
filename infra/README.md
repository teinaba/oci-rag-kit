# OCI RAG Kit - インフラ構築ガイド

OCI RAG Kit に必要なインフラを構築するための2つの方法を提供しています。

## 構築方法の選択

| 方法 | 所要時間 | 推奨ユーザー |
|------|----------|--------------|
| [Terraform 自動構築](terraform/README.md) | 約10分 | 素早く構築したい方、IaC に慣れている方 |
| [手動構築](manual-setup.md) | 約30-60分 | OCI を学びながら構築したい方、細かく設定したい方 |

## Terraform 自動構築

Cloud Shell から Terraform を実行し、必要なリソースを一括で構築します。

**構築されるリソース:**
- VCN（パブリック/プライベートサブネット）
- Autonomous AI Database 26ai
- Data Science Notebook Session
- Object Storage バケット（rag-source, faq）
- IAM Policy

詳細は **[terraform/README.md](terraform/README.md)** を参照してください。

## 手動構築

OCI コンソールから各リソースを手動で作成します。各ステップの意味を理解しながら構築できます。

**構築されるリソース:**
- VCN（パブリック/プライベートサブネット）
- Autonomous AI Database 26ai
- Data Science Notebook Session
- Object Storage バケット
- IAM Policy

詳細は **[manual-setup.md](manual-setup.md)** を参照してください。

## ディレクトリ構造

```
infra/
├── README.md              # このファイル（選択ガイド）
├── manual-setup.md        # 手動構築ガイド
└── terraform/
    ├── README.md          # Terraform 詳細手順
    ├── provider.tf        # OCI プロバイダー設定
    ├── vars.tf            # 変数定義
    ├── core.tf            # VCN、サブネット、ゲートウェイ
    ├── database.tf        # Autonomous Database
    ├── datascience.tf     # Data Science リソース
    ├── object_storage.tf  # Object Storage バケット
    └── iam.tf             # IAM Policy
```
