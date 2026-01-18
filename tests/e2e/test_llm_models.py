"""
LLMモデル出力テスト

OCI GenAI Serviceで利用可能なLLMモデル（Cohere以外）の
出力テストを実行します。各モデルでサンプルコンテキストと
質問を用いて50字程度の回答を生成させます。
"""
import pytest

from src.rag.answer_generator import AnswerGenerator
from src.rag.reranker import RankedChunk


# テスト対象モデル（Cohere以外のGenericモデル）
GENERIC_MODELS = [
    "meta.llama-3.3-70b-instruct",
    "xai.grok-4-fast-non-reasoning",
    "xai.grok-4-fast-reasoning",
    "xai.grok-4",
    "google.gemini-2.5-pro",
    "google.gemini-2.5-flash",
    "google.gemini-2.5-flash-lite",
    "openai.gpt-oss-20b",
    "openai.gpt-oss-120b",
]


@pytest.fixture
def sample_context():
    """テスト用サンプルコンテキスト"""
    return RankedChunk(
        chunk_id=1,
        document_id=1,
        filename="test.txt",
        chunk_text="Oracle Database 26aiはベクトル検索機能を持つリレーショナルデータベースです。AI Vector Searchにより、テキストや画像の類似検索が可能です。",
        distance=0.1,
        rerank_score=0.9
    )


class TestLLMModelOutput:
    """LLMモデル出力テスト"""

    @pytest.mark.parametrize("model_id", GENERIC_MODELS)
    def test_model_generates_answer(
        self,
        config_loader,
        sample_context,
        model_id
    ):
        """
        各モデルが50字程度の回答を生成できることを確認

        Args:
            config_loader: E2E conftest.pyのフィクスチャ
            sample_context: サンプルコンテキスト
            model_id: テスト対象モデルID
        """
        genai_client = config_loader.get_genai_client()
        genai_config = config_loader.get_genai_config()
        compartment_id = genai_config['compartment_id']

        generator = AnswerGenerator(
            genai_client=genai_client,
            compartment_id=compartment_id,
            max_retries=1,
            retry_delay=30
        )

        result = generator.generate(
            query="Oracle Database 26aiとは何ですか？50字程度で回答してください。",
            contexts=[sample_context],
            model=model_id,
            max_tokens=4000,
            temperature=0.3
        )

        # 回答が生成されていることを確認
        assert result.answer is not None, f"{model_id}: 回答がNone"
        assert len(result.answer) > 0, f"{model_id}: 回答が空"
        assert result.model_used == model_id

        # 結果を出力
        print(f"\n{'='*60}")
        print(f"モデル: {model_id}")
        print(f"回答: {result.answer}")
        print(f"生成時間: {result.generation_time:.2f}秒")
        print(f"{'='*60}")
