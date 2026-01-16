# OCI RAG Kit - 自動構築手順

## 概要

- OCI RAG Kit に必要な基盤を Terraform で一括構築する手順
- 実行環境は OCI Cloud Shell 前提

### 構築されるリソース

```
┌─────────────────────────────────────────────────────────────────┐
│                        OCI Compartment                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    VCN (10.0.0.0/16)                    │    │
│  │  ┌─────────────────────┐  ┌─────────────────────────┐   │    │
│  │  │  Public Subnet      │  │  Private Subnet         │   │    │
│  │  │  10.0.0.0/24        │  │  10.0.1.0/24            │   │    │
│  │  │                     │  │                         │   │    │
│  │  │  ・Internet GW      │  │  ・NAT Gateway           │   │    │
│  │  │                     │  │  ・Service Gateway       │   │   │
│  │  └─────────────────────┘  └─────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐    │
│  │ Autonomous AI   │  │ Data Science    │  │ Object        │    │
│  │ Database 26ai   │  │ Notebook        │  │ Storage       │    │
│  │                 │  │                 │  │               │    │
│  │ ・2 ECPU        │  │ ・VM.E5.Flex     │  │ ・rag-source  │    │
│  │ ・50GB Storage  │  │ ・4oCPU/64GB MEM │  │ ・faq         │    │
│  │ ・OLTP          │  │ ・50GB Block     │  │               │    │
│  └─────────────────┘  └─────────────────┘  └───────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                         IAM                             │    │
│  │  ・Policy: data-science-policy                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 前提条件

- **対応リージョン**: `ap-osaka-1`（大阪）または `us-chicago-1`（シカゴ）
- **必要な権限**
  - 対象コンパートメントの管理者権限、または
  - 以下の個別権限:
    - VCN / Autonomous Database / Object Storage / Data Science の作成権限
    - IAMポリシーの作成権限（Data Scienceサービス用）

## クイックスタート

### 1. Cloud Shell を起動

- OCI コンソール右上の **Cloud Shell アイコン**（ターミナルマーク）をクリックして起動

### 2. リポジトリをクローン

```bash
git clone https://github.com/teinaba/oci-rag-kit.git
cd oci-rag-kit/infra/terraform
```

### 3. 変数ファイルを作成

以下をコピーし、3つの値を自分の環境に合わせて書き換えてから実行:

```bash
cat << 'EOF' > terraform.tfvars
region            = "us-chicago-1"  #or "ap-osaka-1"
home_region       = "ap-osaka-1"  #e.g. "ap-tokyo-1", "us-ashburn-1"
compartment_ocid  = "ocid1.compartment.oc1..xxxxx"
db_admin_password = "YourPassword123!"  #12〜30文字、大文字・小文字・数字を各1文字以上含む
EOF
```

> **Note**:
> `home_region` はテナンシーのホームリージョンを指定します(例: "ap-tokyo-1", "us-ashburn-1")。

### 4. デプロイ

```bash
terraform init
terraform apply
```

`Enter a value:`と表示されたら `yes` を入力。初回実行時はプロバイダーのダウンロードに数分かかります。
デプロイに失敗した場合は `terraform destroy` でリソースを削除してから再実行してください。

### 5. デプロイ結果を確認

デプロイ完了後、OCI コンソールで以下を確認:

- **ネットワーキング > VCN** - `vcn01` が作成されていること
- **Oracle AI Database > Autonomous Database** - `ragdb` が「使用可能」状態であること
- **ストレージ > バケット** - `rag-source`、`faq` が作成されていること

### 6. 次のステップ

インフラ構築完了後、**[手動構築ガイド](../manual-setup.md)** の以下の手順に進んでください:

1. **[5.4. Notebook の環境整備](../manual-setup.md#54-notebook-の環境整備)** - git clone、Python環境構築
2. **[6. クレデンシャルの作成](../manual-setup.md#6-クレデンシャルの作成とコード実行に必要な情報の採取)** - APIキー、.env設定
3. **[7. Pythonコードの実行](../manual-setup.md#7-pythonコードの実行)** - Notebook実行

### 7. リソースを削除（検証終了時）

```bash
terraform destroy
```

`Enter a value:` と表示されたら `yes` を入力して Enter を入力。

## リソース詳細

### ネットワーク (core.tf)

- **VCN** (vcn01): 10.0.0.0/16
  - パブリックサブネット: 10.0.0.0/24
  - プライベートサブネット: 10.0.1.0/24（Notebook デプロイ先）
- **ゲートウェイ**: Internet GW / NAT GW / Service GW

### データベース (database.tf)

- **ragdb** (Autonomous AI Database 26ai)
  - ワークロード: OLTP
  - ECPU: 2（自動スケーリング有効）
  - ストレージ: 50GB
  - ネットワーク: プライベートサブネットのみ

### Data Science (datascience.tf)

- **Notebook Session**
  - シェイプ: VM.Standard.E5.Flex (AMD)
  - OCPU: 4 / メモリ: 64GB
  - ブロックストレージ: 50GB

### Object Storage (object_storage.tf)

- **rag-source**: RAG ソースドキュメント格納
- **faq**: FAQ ファイル格納

### IAM (iam.tf)

- **Policy**: data-science-policy
  - `allow service datascience to use virtual-network-family in compartment id <compartment_ocid>`

## トラブルシューティング

### リソース作成エラー

#### 権限エラー

```
Error: 404-NotAuthorizedOrNotFound
```

コンパートメントへの適切な権限があるか確認してください。テナンシー管理者に IAM ポリシーの確認を依頼してください。

#### IAMポリシーのホームリージョンエラー

```
Error: 403-NotAllowed, Policy can only be created in the home tenancy region
```

OCIではIAMポリシーの作成・更新・削除はホームリージョンで実行する必要があります。`terraform.tfvars` の `home_region` が正しく設定されているか確認してください。

### 状態ファイルの破損

```bash
# 状態ファイルを削除して再初期化
rm -rf .terraform terraform.tfstate*
terraform init
```

## ファイル構成

```
infra/terraform/
├── README.md          # このファイル
├── provider.tf        # OCI プロバイダー設定
├── vars.tf            # 変数定義
├── core.tf            # VCN、サブネット、ゲートウェイ
├── database.tf        # Autonomous Database
├── datascience.tf     # Data Science リソース
├── object_storage.tf  # Object Storage バケット
└── iam.tf             # IAM Policy
```
