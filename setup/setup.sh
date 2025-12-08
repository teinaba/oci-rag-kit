#!/bin/bash

set -e

echo "=========================================="
echo "RAG環境セットアップスクリプト"
echo "=========================================="
echo ""

# Conda初期化
eval "$(conda shell.bash hook)"

# environment.yamlの存在確認
if [ ! -f "environment.yaml" ]; then
    echo "❌ エラー: environment.yaml が見つかりません"
    echo "   同じディレクトリに environment.yaml を配置してください"
    exit 1
fi

echo "✅ environment.yaml を検出しました"
echo ""

# 環境が既に存在するかチェック
if conda env list | grep -q "rag_env"; then
    echo "⚠️  環境 'rag_env' は既に存在します"
    read -p "削除して再作成しますか? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  既存環境を削除中..."
        conda activate base
        conda env remove -n rag_env -y
        echo "✅ 削除完了"
    else
        echo "既存環境を使用します"
        exit 0
    fi
fi

# 環境作成
echo "🔨 Conda環境を作成中（5-10分かかります）..."
if conda env create -f environment.yaml; then
    echo "✅ Conda環境作成完了"
else
    echo "❌ 環境作成に失敗しました"
    exit 1
fi
echo ""

# 環境をアクティベート
echo "🔄 環境をアクティベート中..."
conda activate rag_env
echo "✅ 環境アクティベート完了"
echo ""

# JupyterLabカーネル登録
echo "🔧 JupyterLabカーネルを登録中..."
/opt/conda/envs/rag_env/bin/python -m ipykernel install --user --name=rag_env --display-name="Python 3.13 (rag_env)"
echo "✅ カーネル登録完了"
echo ""

# Rerankerモデルの事前ダウンロード
echo "📦 日本語Rerankerモデルを事前ダウンロード中..."
/opt/conda/envs/rag_env/bin/python -c "
from sentence_transformers import CrossEncoder
import os

cache_dir = os.path.expanduser('~/.cache/huggingface')
os.makedirs(cache_dir, exist_ok=True)

print('✓ hotchpotch/japanese-reranker-base-v2 をダウンロード中...')
model = CrossEncoder('hotchpotch/japanese-reranker-base-v2', max_length=512)
print('✓ モデルダウンロード完了')
" || echo "⚠️ モデルの事前ダウンロードに失敗しました（初回実行時にダウンロードされます）"
echo ""

# 確認
echo "🔍 インストール確認..."
/opt/conda/envs/rag_env/bin/python --version
/opt/conda/envs/rag_env/bin/python -c "
import oci, oracledb, langchain_community
import pymupdf, pandas, openpyxl, datasets, ragas
import torch, sentencepiece
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv
print('✅ すべてのモジュールが正常にインポートされました')
print(f'✅ CUDA利用可能: {torch.cuda.is_available()}')
"

echo ""
echo "=========================================="
echo "✅ セットアップ完了！"
echo "=========================================="
echo ""
echo "次のステップ:"
echo "  1. JupyterLabでノートブックを開く"
echo "  2. Kernel → Change Kernel"
echo "  3. 'Python 3.13 (rag_env)' を選択"
echo ""
echo "環境の使用方法:"
echo "  conda activate rag_env"
echo ""
echo "登録されたカーネル一覧:"
jupyter kernelspec list