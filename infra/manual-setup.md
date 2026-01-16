# RAG環境構築手順書
この手順書では、Oracle Cloud Infrastructure上に一からRAG環境を構築し、RAG検索を実施するまでの手順を記載しています。

## 作業内容一覧
1. コンパートメントの作成
2. VCNの作成 (ネットワーク)
3. Object Storageの作成
4. Autonomous Databaseの作成
5. Data Science環境の作成 (Python実行環境)
6. クレデンシャルの作成とコード実行に必要な情報の採取
7. Pythonコード実行

## 1. コンパートメントの作成
- [アイデンティティとセキュリティ] > [アイデンティティ] > [コンパートメント] > [コンパートメントの作成]
- 以下の情報を入力（コンパートメント名は任意ですが、後続の作業で使用する場合置き換えてください）
  - 名前: rag
  - 説明: 検証用のRAG環境
  - 親コンパートメント: root

## 2. VCNとサブネットの作成
- [ネットワーキング] > [仮想クラウド・ネットワーク] > [アクション] > [VCNウィザードの起動] > [インターネット接続性を持つVCNの作成]
- 以下の情報を入力し、[次] > [作成]
  - 基本情報
    - VCN名: vcn01
    - コンパートメント: rag
  - VCNの構成
    - VCN IPv4 CIDRブロック: 10.0.0.0/16 (Default)
    - このVCNでIPv6を有効化: 無し (Default)
    - このVCNでDNSホスト名を使用: 有り (Default)
  - パブリック・サブネットの構成: 10.0.0.0/24 (Default)
  - プライベート・サブネットの構成: 10.0.1.0/24 (Default)

## 3. Object Storageの作成
### 3.1. バケットの作成
- [ストレージ] > [オブジェクト・ストレージとアーカイブ・ストレージ] > [バケット] > [バケットの作成]
  - 適用済フィルタ: `コンパートメント rag`
- 以下の情報を入力し、バケットを作成（RAGソースドキュメント格納バケット）
  - バケット名: rag-source
  - 以下は全てデフォルト
- 以下の情報を入力し、バケットを作成（FAQリスト格納バケット）
  - バケット名: faq
  - 以下は全てデフォルト

### 3.2. フォルダの作成 (Option)
RAG検索におけるフィルタリングを行う際は、フォルダごとにソース・ドキュメントを分けて格納する
　例) "製品"フォルダに格納したドキュメントは、フィルタリング値が"製品"になる
- [ストレージ] > [オブジェクト・ストレージとアーカイブ・ストレージ] > [バケット] > [rag-source] > [オブジェクト] > [アクション] > [新規フォルダの作成]
- 以下の情報を入力し、フォルダを作成。フィルタリング値に応じて繰り返しフォルダを作成
  - 名前: <フィルタリング項目名>

### 3.3. ソース・ドキュメントのアップロード
この作業は、後から行っても問題ありません。
- [ストレージ] > [オブジェクト・ストレージとアーカイブ・ストレージ] > [バケット] > [rag-source] > [オブジェクト] > [オブジェクトのアップロード]
  - フィルタリングを行う場合は、フィルタリング値のフォルダに遷移
- アップロードするファイルをドラッグ&ドロップする
  - その他の項目は変更なし (Default)
- [次] > [アップロード]を押下する

### 3.4. FAQ一覧ファイルのアップロード
この作業は、後から行っても問題ありません。
- [ストレージ] > [オブジェクト・ストレージとアーカイブ・ストレージ] > [バケット] > [faq] > [オブジェクト] > [オブジェクトのアップロード]
- faq.excelをドラッグ&ドロップする
  - その他の項目は変更なし (Default)
- [次] > [アップロード]を押下する

## 4. Autonomous AI Databaseの作成
### 4.1. データベース・インスタンスの作成
- [Oracle AI Database] > [Autonomous AI Database] > [Autonomous AI Databaseの作成]
- 以下の情報を入力し、Autonomous AI Databaseを作成
  - 表示名: ragdb
  - データベース名: ragdb
  - コンパートメント: rag
  - ワークロード・タイプ: トランザクション処理
  - データベース構成
    - Always Free: チェックなし (Default)
    - 開発者: チェックなし (Default)
    - データベース・バージョンの選択: 26ai
    - ECPU数: 2
    - 自動スケーリングの計算: チェックあり (Default)
    - ストレージ: 50
    - ストレージ単位サイズ: GB
    - ストレージの自動スケーリング: チェックなし (Default)
    - 拡張オプション: 変更なし
    - 自動バックアップ保持期間(日): 7
    - 不変バックアップ保持: チェックなし (Default)
  - 資格証明の作成
    - パスワード: <任意のパスワード>
  - ネットワーク・アクセス
    - アクセス・タイプ: 許可されたIPおよびVCN限定のセキュア・アクセス
    - IP表記法タイプ: 仮想クラウド・ネットワーク
      - コンパートメント: rag
      - 仮想クラウド・ネットワーク: vcn01
      - IPアドレスまたはCIDR: 10.0.1.0/24
    - IP値への自分のIPアドレスの追加: チェックあり
    - 相互TLS(mTLS)認証が必要: チェックなし (Default)
  - 運用上の通知およびお知らせ用の連絡先: 変更なし
  - 拡張オプション: 変更なし

## 5. OCI Data Science環境の構築
手順の流れ
1. ポリシーの作成
2. Data Sienceプロジェクトの作成
3. Data Science Notebook の作成

### 5.1. ポリシーの作成
- [アイデンティティとセキュリティ] > [ポリシー] > [ポリシーの作成]
  - このとき、`rag`コンパートメントが選択されていることを確認しておく
- 以下の情報を入力し、作成
  - 名前: data-science-policy
  - 説明: Data Science用のポリシー
  - コンパートメント: rag
  - ポリシー・ビルダー (手動エディタで編集する)
    - `allow service datascience to use virtual-network-family in compartment <compartment name>`

> **Note**: コンパートメント名が rag 以外の場合は、利用するコンパートメント名に修正してください

### 5.2. Data Scienceプロジェクトの作成
- [アナリティクスとAI] > [データ・サイエンス] > [プロジェクトの作成]
- 以下の情報を入力し、作成
  - コンパートメント: rag
  - 名前: rag_project
  - 説明: 検証用のRAG環境プロジェクト

### 5.3. Data Science Notebook の作成
- [アナリティクスとAI] > [データ・サイエンス] > [rag_project] > [ノートブック・セッションの作成]
- 以下の情報を入力し、作成
  - コンパートメント: rag
  - 名前: rag_notebook
  - コンピュート・シェイプ
    - 仮想マシン
    - Ampere > VM.Standard.A1.Flex　
      - 4 OCPU / 24 GB Memory  ← 無償枠範囲内([Always Free](https://docs.oracle.com/ja-jp/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm))
  - ブロック・ストレージ・サイズ: 50 (GB)
  - ネットワーキング・リソース
    - ネットワーク・タイプ: カスタム・ネットワーク
      - vcn: vcn01
      - サブネット: プライベート・サブネット-vcn01
    - エンドポイント・タイプ: パブリック・エンドポイント
  - 以下はデフォルト通り

> **Note**: 
> コンピュート・シェイプは用途に応じて、任意のシェイプに変更して問題ありません。
> Rerank処理を行う場合は、AMDで4 OCPU以上をおすすめします(A1シェイプだと処理に長時間要します)。

### 5.4. Notebook の環境整備
- [アナリティクスとAI] > [データ・サイエンス] > [rag_project] > [rag_notebook] > [開く]
- [Launcher] > [Other] > [Terminal] を押下し、新しいTerminalを開始
- 以下のコマンドを実行
```bash
# gitリポジトリをclone
git clone https://github.com/teinaba/oci-rag-kit.git

# Python環境作成用のディレクトリに移動
cd oci-rag-kit/setup/

# Python環境を作成するshellスクリプトを実行
bash setup.sh 
```
- Notebookのホーム画面(Launcher)に、[Python 3.13(rag_env)]が追加されていることを確認する

## 6. クレデンシャルの作成とコード実行に必要な情報の採取
### 6.1. OCI APIキーの作成 (OCIコンソール)
- [プロファイル(画面右上の人型マーク)] > [ユーザ設定] > [トークンおよびキー] > [APIキーの追加]
- [秘密キーのダウンロード]を押下し、秘密キーをローカルPCにダウンロード
- [追加]を押下
- [構成ファイルのプレビュー]画面で表示される情報をメモ帳に保存しておく（全行を一括コピーしておくとよい）
  - user
  - fingerprint
  - tenancy
  - region
- [閉じる]でAPIキーの作成を終了

### 6.2. OCI認証情報の設定（Data Science Notebook内）
- Data Science Notebook内でTerminalで以下のコマンドを実行し、.ociディレクトリを作成
```bash
mkdir -p ~/.oci
chmod 700 ~/.oci
```
- Notebookのファイルブラウザで、6.1でダウンロードした秘密鍵ファイル（例: `oci_api_key.pem`）をホームディレクトリにアップロード
  - 秘密鍵はデフォルトの名前が長いので、ローカルで上記にRenameしてから操作すると効率的
- Terminalで秘密鍵を.ociディレクトリに移動し、パーミッションを設定
```bash
mv ~/oci_api_key.pem ~/.oci/
chmod 600 ~/.oci/oci_api_key.pem
```
- Terminalで以下のコマンドを実行し、configファイルを作成
  - 手順6.1でメモした情報を使用
  - メモ帳などで編集してからペーストすると効率的
```bash
cat > ~/.oci/config << 'EOF'
[DEFAULT]
user=<6.1で取得したuser OCID>
fingerprint=<6.1で取得したfingerprint>
tenancy=<6.1で取得したtenancy OCID>
region=<6.1で取得したリージョン>
key_file=~/.oci/oci_api_key.pem
EOF

chmod 600 ~/.oci/config
```

### 6.3. コンパートメントOCIDの確認
- [アイデンティティとセキュリティ] > [アイデンティティ] > [コンパートメント] > [rag]
- [OCID]をコピーし、メモ帳に保存する

### 6.4. データベースの接続文字列の確認
- [Oracle AI Database] > [Autonomous AI Database] > [ragdb] > [データベース接続]
- [接続文字列]で以下の設定で接続文字列をコピー(右端の[・・・]を押下)し、メモ帳に保存する
  - TLS認証: 相互TLS
  - TLS名: ragdb_high
- [取消]を押下

### 6.5. 設定ファイルの作成
- Terminalで以下のコマンドを実行し、.envファイルを作成
  - 手順6.1～6.4で取得した情報を使用
  - メモ帳などで編集してからペーストすると効率的
  - 値を " " で囲む必要はない (例: OCI_REGION=ap-osaka-1)
```bash
cd ~/oci-rag-kit

cat > .env << 'EOF'
# ========================================
# Oracle AI Database ADMIN 接続情報
# ========================================
DB_ADMIN_PASSWORD=<4.1で設定したADMINパスワード>

# ========================================
# Oracle AI Database User 接続情報
# ========================================
DB_USERNAME=rag
DB_PASSWORD=<RAGユーザのパスワード>
DB_DSN=<6.4で取得したデータベース接続文字列>

# ========================================
# OCI 認証情報 (Do not edit)
# ========================================
# Path to ~/.oci/config file (default: ~/.oci/config)
OCI_CONFIG_FILE=~/.oci/config
# Profile name to use (default: DEFAULT)
OCI_PROFILE=DEFAULT

# ========================================
# OCI Generative AI Service
# ========================================
OCI_COMPARTMENT_ID=<6.3で取得したragコンパートメントのOCID>
OCI_REGION=<使用するリージョン名（例: us-chicago-1, ap-osaka-1）>

# ========================================
# OCI Object Storage
# ========================================
OCI_BUCKET_NAME=rag-source
EOF

chmod 600 .env
```
- 編集が必要な項目（`< >`で囲まれた部分を置き換える）:
  - `DB_ADMIN_PASSWORD`: 4.1で設定したADMINパスワード（RAGユーザー自動作成に必要）
  - `DB_PASSWORD`: RAGユーザのパスワード（任意のパスワードを設定）
  - `DB_DSN`: 6.4で取得したデータベース接続文字列
  - `OCI_COMPARTMENT_ID`: 6.3で取得したragコンパートメントのOCID
  - `OCI_REGION`: 使用するリージョン名（例: `us-chicago-1`, `ap-osaka-1`）

## 7. Pythonコードの実行
- [アナリティクスとAI] > [データ・サイエンス] > [rag_project] > [rag_notebook] > [開く]
- 実行したいソースコードを右クリックし、[Open]を選択
- 開かれたソースコードのタブの右上で先ほど作成したカーネルを選択 > [Python 3.13(rag_env)]
- セルの一番上から順番にブロックを実行する (Shift+Enter or 実行マークをクリック)
  - チューニング・パラメータは、必要に応じて適宜変更する