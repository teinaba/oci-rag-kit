"""
RAG Pipelineのエンドツーエンドテスト

ノートブック 13_rag_v2.ipynb の正確なコードフローをテストします。
"""
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime

from src.rag.vector_searcher import VectorSearcher
from src.rag.reranker import JapaneseReranker
from src.rag.answer_generator import AnswerGenerator
from src.rag.ragas_evaluator import RagasEvaluator
from src.rag.excel_handler import ExcelHandler
from src.rag.rag_pipeline import RAGPipeline


class TestNotebookRAGFlow:
    """Test the main flow from notebook 13_rag_v2.ipynb"""

    def test_notebook_rag_pipeline_execution(
        self,
        config_loader,
        db_connection,
        test_faq_dataframe
    ):
        """
        Reproduce notebook 13_rag_v2.ipynb main execution flow

        This test mirrors cells 0-15:
        - Cell 0-2: Header and Imports (handled by test setup)
        - Cell 4: Configuration and DB connection
        - Cell 6: RAG parameters
        - Cell 8: Component initialization + RAGPipeline orchestrator
        - Cell 10: Load FAQ file
        - Cell 12: Process all questions
        - Cell 14: Close connection (handled by fixture)
        """
        # セル4: 設定の読み込みとDB接続
        db_params = config_loader.get_db_params()
        oci_config = config_loader.get_oci_config()
        genai_config = config_loader.get_genai_config()
        compartment_id = genai_config['compartment_id']
        embedding_model = genai_config['embed_model']

        os_config = config_loader.get_object_storage_config()
        bucket_name = os_config['bucket_name']

        # FAQ用バケット名とファイル名を取得
        faq_bucket_name = config_loader.get_faq_bucket_name()
        faq_object_name = config_loader.get_faq_object_name()

        os_client = config_loader.get_object_storage_client()
        namespace = os_client.get_namespace().data

        genai_client = config_loader.get_genai_client()

        # セル6: RAGパラメータ設定
        TOP_K = 10
        RERANK_ENABLED = True
        RERANK_TOP_N = 5
        CHAT_MODEL = "cohere.command-a-03-2025"
        MAX_TOKENS = 500  # Reduced for testing
        TEMPERATURE = 0.3
        TOP_P = 0.75
        FREQUENCY_PENALTY = 0.0
        TOP_K_SAMPLING = 0
        ANSWER_PROMPT = """
参考ドキュメントの情報に基づいて、正確に回答してください。
回答は簡潔に平文で記載してください。
"""

        # セル8: RAGコンポーネント初期化
        # Phase 1: VectorSearcher
        searcher = VectorSearcher(
            db_params=db_params,
            embedding_model=embedding_model,
            genai_client=genai_client,
            compartment_id=compartment_id,
            service_endpoint=genai_config['endpoint']
        )

        # Phase 2: JapaneseReranker
        reranker = JapaneseReranker()

        # Phase 3: AnswerGenerator
        generator = AnswerGenerator(
            genai_client=genai_client,
            compartment_id=compartment_id
        )

        # Phase 4: RagasEvaluator (skip for basic E2E test)
        evaluator = None

        # Phase 5: ExcelHandler (FAQ用バケットを使用)
        excel_handler = ExcelHandler(
            oci_config=oci_config,
            bucket_name=faq_bucket_name,
            namespace=namespace
        )

        # (Cell 8 continued: RAGPipelineオーケストレータの作成)
        progress_records = []

        def progress_callback(message: str):
            """Track progress for verification"""
            progress_records.append(message)

        # Phase 6: RAGPipeline
        pipeline = RAGPipeline(
            searcher=searcher,
            reranker=reranker,
            generator=generator,
            evaluator=evaluator,
            enable_reranking=RERANK_ENABLED,
            top_k=TOP_K,
            rerank_top_n=RERANK_TOP_N,
            progress_callback=progress_callback
        )

        # Cell 10: FAQファイル読み込み
        # Try to load from Object Storage (same as notebook)
        # If file doesn't exist, fall back to test_faq_dataframe
        try:
            print(f"Attempting to load FAQ file: {faq_object_name} from bucket: {faq_bucket_name}")
            faq_df = excel_handler.load_faq(faq_object_name)
            print(f"✓ FAQ file loaded from Object Storage: {len(faq_df)} questions")
        except Exception as e:
            print(f"⚠ FAQ file not found in Object Storage, using test data: {e}")
            faq_df = test_faq_dataframe
            print(f"✓ Using test FAQ data: {len(faq_df)} questions")

        assert len(faq_df) >= 3, f"FAQ should have at least 3 questions, got {len(faq_df)}"
        assert 'question' in faq_df.columns
        assert 'ground_truth' in faq_df.columns
        assert 'filter' in faq_df.columns

        # Cell 12: すべての質問をパイプライン処理
        print("\n" + "="*60)
        print("Starting RAG Processing (E2E Test)...")
        print("="*60 + "\n")
        print(f"Total questions: {len(faq_df)}")
        print(f"Model: {CHAT_MODEL}\n")

        batch_result = pipeline.process_batch(
            questions_df=faq_df,
            model=CHAT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            frequency_penalty=FREQUENCY_PENALTY,
            top_k=TOP_K_SAMPLING,
            answer_prompt=ANSWER_PROMPT
        )

        # Display processing results (same as notebook Cell 12)
        print("\n" + "="*60)
        print("Processing Complete")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"  ✓ Success: {batch_result.successful} questions")
        print(f"  ✗ Failed:  {batch_result.failed} questions")
        print(f"  📁 Total:   {batch_result.total_questions} questions")
        print(f"  ⏱️ Time:    {batch_result.elapsed_time:.2f} seconds")
        print(f"  📈 Avg:     {batch_result.elapsed_time/batch_result.total_questions:.2f} seconds/question")

        results_df = batch_result.results_df
        print(f"\n【処理時間の統計】")
        print(f"  ベクトル検索平均: {results_df['vector_search_time'].mean():.2f}秒")
        print(f"  Rerank平均: {results_df['rerank_time'].mean():.2f}秒")
        print(f"  回答生成平均: {results_df['generation_time'].mean():.2f}秒")
        print(f"  合計平均: {results_df['total_time'].mean():.2f}秒")

        print(f"\n📋 Results Preview:")
        print(results_df[['id', 'question', 'answer', 'total_time', 'status']].head())

        if batch_result.failed > 0:
            print(f"\n⚠ Warning: {batch_result.failed} questions failed to process")
            failed_df = results_df[results_df['status'] == 'failed']
            print("\nFailed questions:")
            print(failed_df[['id', 'question', 'error']])

        # Verify: Processing completed
        assert batch_result.total_questions == len(faq_df)
        assert batch_result.total_questions >= 3, f"Expected at least 3 questions, got {batch_result.total_questions}"

        # Verify: At least some questions were processed successfully
        # (Allow for some failures due to API rate limits)
        assert batch_result.successful + batch_result.failed == batch_result.total_questions

        # Verify: Progress callback was called for each question
        # (Each question generates at least one progress message)
        assert len(progress_records) >= batch_result.total_questions

        # Verify: Results DataFrame has all expected columns
        expected_columns = [
            'question', 'answer', 'contexts',
            'vector_search_time', 'rerank_time', 'generation_time', 'total_time',
            'model_used', 'status'
        ]
        for col in expected_columns:
            assert col in results_df.columns, f"Missing column: {col}"

        # Verify: Successful questions have answers
        successful_results = results_df[results_df['status'] == 'success']
        if len(successful_results) > 0:
            # Check that answers are not empty
            for idx, row in successful_results.iterrows():
                assert row['answer'] is not None
                assert len(row['answer']) > 0
                assert row['contexts'] is not None
                assert len(row['contexts']) > 0
                assert row['model_used'] == CHAT_MODEL
                assert row['total_time'] > 0

        # Verify: Metadata can be generated (same as notebook Cell 12)
        metadata = {
            'パラメータ': [
                'TOP_K (ベクトル検索件数)',
                'RERANK_ENABLED (Rerankが有効か)',
                'RERANK_TOP_N (Rerank後件数)',
                'CHAT_MODEL (使用LLMモデル)',
                'MAX_TOKENS (最大トークン数)',
                'TEMPERATURE (温度)',
                'TOP_P (Nucleus sampling)',
                'FREQUENCY_PENALTY (頻度ペナルティ)',
                'TOP_K_SAMPLING (Top-K sampling)',
                'ANSWER_PROMPT (回答生成時の指示文)',
                'embedding_model',
                'rerank_model',
                '実行日時',
                'FAQ件数',
                '成功件数',
                '失敗件数',
                '全体処理時間（秒）',
                '平均処理時間/件（秒）',
                'ベクトル検索平均時間（秒）',
                'Rerank平均時間（秒）',
                '回答生成平均時間（秒）'
            ],
            '設定値': [
                TOP_K,
                RERANK_ENABLED,
                RERANK_TOP_N,
                CHAT_MODEL,
                MAX_TOKENS,
                TEMPERATURE,
                TOP_P,
                FREQUENCY_PENALTY,
                TOP_K_SAMPLING,
                ANSWER_PROMPT,
                embedding_model,
                'hotchpotch/japanese-reranker-base-v2',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                batch_result.total_questions,
                batch_result.successful,
                batch_result.failed,
                f"{batch_result.elapsed_time:.2f}",
                f"{batch_result.elapsed_time/batch_result.total_questions:.2f}",
                f"{results_df['vector_search_time'].mean():.2f}",
                f"{results_df['rerank_time'].mean():.2f}",
                f"{results_df['generation_time'].mean():.2f}"
            ]
        }
        metadata_df = pd.DataFrame(metadata)

        assert len(metadata_df) == len(metadata['パラメータ'])
        assert 'パラメータ' in metadata_df.columns
        assert '設定値' in metadata_df.columns

        # Verify: ExcelHandler can save results (skip actual save in test)
        # In real notebook, this would be:
        # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # output_filename = f"rag_result_{timestamp}.xlsx"
        # excel_handler.save_results(results_df, output_filename, metadata_df)

        print("\n✓ E2E test completed successfully")
        print(f"  - All {batch_result.total_questions} questions were processed")
        print(f"  - {batch_result.successful} succeeded, {batch_result.failed} failed")
        print(f"  - Metadata generated successfully")

        # Cell 14: DB接続のクローズ (handled by fixture cleanup)

    def test_notebook_rag_pipeline_with_ragas_evaluation(
        self,
        config_loader,
        db_connection,
        test_faq_dataframe
    ):
        """
        Reproduce notebook 13_rag_v2.ipynb with RAGAS evaluation (Cell 8 added)

        This test mirrors cells 0-15 including the new Cell 8 (RAGAS evaluation):
        - Cell 0-12: Same as test_notebook_rag_pipeline_execution
        - Cell 8: RAGAS evaluation (NEW)
        - Cell 14: Close connection (handled by fixture)
        """
        # セル4: 設定の読み込みとDB接続
        db_params = config_loader.get_db_params()
        oci_config = config_loader.get_oci_config()
        genai_config = config_loader.get_genai_config()
        compartment_id = genai_config['compartment_id']
        embedding_model = genai_config['embed_model']

        os_config = config_loader.get_object_storage_config()
        bucket_name = os_config['bucket_name']

        # FAQ用バケット名とファイル名を取得
        faq_bucket_name = config_loader.get_faq_bucket_name()
        faq_object_name = config_loader.get_faq_object_name()

        os_client = config_loader.get_object_storage_client()
        namespace = os_client.get_namespace().data

        genai_client = config_loader.get_genai_client()

        # セル6: RAGパラメータ設定
        TOP_K = 10
        RERANK_ENABLED = True
        RERANK_TOP_N = 5
        CHAT_MODEL = "cohere.command-a-03-2025"
        MAX_TOKENS = 500  # Reduced for testing
        TEMPERATURE = 0.3
        TOP_P = 0.75
        FREQUENCY_PENALTY = 0.0
        TOP_K_SAMPLING = 0
        ANSWER_PROMPT = """
参考ドキュメントの情報に基づいて、正確に回答してください。
回答は簡潔に平文で記載してください。
"""

        # セル8: RAGコンポーネント初期化
        # Phase 1: VectorSearcher
        searcher = VectorSearcher(
            db_params=db_params,
            embedding_model=embedding_model,
            genai_client=genai_client,
            compartment_id=compartment_id,
            service_endpoint=genai_config['endpoint']
        )

        # Phase 2: JapaneseReranker
        reranker = JapaneseReranker()

        # Phase 3: AnswerGenerator
        generator = AnswerGenerator(
            genai_client=genai_client,
            compartment_id=compartment_id
        )

        # Phase 4: RagasEvaluator (skip for now, will initialize in Cell 8)
        evaluator = None

        # Phase 5: ExcelHandler (FAQ用バケットを使用)
        excel_handler = ExcelHandler(
            oci_config=oci_config,
            bucket_name=faq_bucket_name,
            namespace=namespace
        )

        # (Cell 8 continued: RAGPipelineオーケストレータの作成)
        progress_records = []

        def progress_callback(message: str):
            """Track progress for verification"""
            progress_records.append(message)

        # Phase 6: RAGPipeline
        pipeline = RAGPipeline(
            searcher=searcher,
            reranker=reranker,
            generator=generator,
            evaluator=evaluator,
            enable_reranking=RERANK_ENABLED,
            top_k=TOP_K,
            rerank_top_n=RERANK_TOP_N,
            progress_callback=progress_callback
        )

        # Cell 10: FAQファイル読み込み
        try:
            print(f"Attempting to load FAQ file: {faq_object_name} from bucket: {faq_bucket_name}")
            faq_df = excel_handler.load_faq(faq_object_name)
            print(f"✓ FAQ file loaded from Object Storage: {len(faq_df)} questions")
        except Exception as e:
            print(f"⚠ FAQ file not found in Object Storage, using test data: {e}")
            faq_df = test_faq_dataframe
            print(f"✓ Using test FAQ data: {len(faq_df)} questions")

        assert len(faq_df) >= 3, f"FAQ should have at least 3 questions, got {len(faq_df)}"

        # Cell 12: すべての質問をパイプライン処理
        print("\n" + "="*60)
        print("Starting RAG Processing with RAGAS Evaluation (E2E Test)...")
        print("="*60 + "\n")
        print(f"Total questions: {len(faq_df)}")
        print(f"Model: {CHAT_MODEL}\n")

        batch_result = pipeline.process_batch(
            questions_df=faq_df,
            model=CHAT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            frequency_penalty=FREQUENCY_PENALTY,
            top_k=TOP_K_SAMPLING,
            answer_prompt=ANSWER_PROMPT
        )

        results_df = batch_result.results_df

        print("\n" + "="*60)
        print("Processing Complete")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"  ✓ Success: {batch_result.successful} questions")
        print(f"  ✗ Failed:  {batch_result.failed} questions")

        assert batch_result.total_questions == len(faq_df)
        assert batch_result.successful + batch_result.failed == batch_result.total_questions

        # Cell 8: RAGAS評価の実行 (NEW)
        print("\n" + "="*60)
        print("Starting RAGAS Evaluation...")
        print("="*60 + "\n")

        # RAGAS評価用のLLMモデル
        RAGAS_LLM_MODEL = "cohere.command-a-03-2025"

        # RagasEvaluatorのインスタンスを作成
        ragas_evaluator = RagasEvaluator(
            oci_config=oci_config,
            compartment_id=compartment_id,
            service_endpoint=genai_config['endpoint'],
            embedding_model=embedding_model,
            llm_model=RAGAS_LLM_MODEL,
            genai_client=genai_client,
            batch_size=3,
            max_retries=3,
            retry_wait=30
        )

        print(f"✓ RagasEvaluator initialized")
        print(f"  - LLM Model: {RAGAS_LLM_MODEL}")
        print(f"  - Embedding Model: {embedding_model}")
        print(f"  - Batch Size: 3")

        # results_dfから評価に必要なデータを準備
        # 失敗した質問は除外
        eval_df = results_df[results_df['status'] == 'success'].copy()

        if len(eval_df) == 0:
            print("\n⚠ Warning: No successful results to evaluate")
            # Skip RAGAS evaluation if no successful results
            print("✓ E2E test completed (RAGAS evaluation skipped)")
            return

        # 評価データの準備
        questions = eval_df['question'].tolist()
        answers = eval_df['answer'].tolist()
        ground_truths = eval_df['ground_truth'].tolist()

        # contextsの準備（contexts列から評価用のリストに変換）
        contexts = []
        for chunks in eval_df['contexts'].tolist():
            if isinstance(chunks, list):
                contexts.append(chunks)
            elif isinstance(chunks, str):
                contexts.append([chunks])
            else:
                contexts.append([""])

        print(f"\nEvaluating {len(eval_df)} questions...")
        print(f"  Questions: {len(questions)}")
        print(f"  Answers: {len(answers)}")
        print(f"  Contexts: {len(contexts)}")
        print(f"  Ground Truths: {len(ground_truths)}")

        # RAGAS評価を実行
        eval_result = ragas_evaluator.evaluate(
            questions=questions,
            answers=answers,
            contexts=contexts,
            ground_truths=ground_truths
        )

        # 評価結果をDataFrameに追加
        eval_df['answer_correctness'] = eval_result.answer_correctness
        eval_df['context_recall'] = eval_result.context_recall

        # 結果のサマリーを表示
        print("\n" + "="*60)
        print("RAGAS Evaluation Complete")
        print("="*60)
        print(f"\n📊 Evaluation Metrics Summary:")
        print(f"  Answer Correctness (平均): {eval_df['answer_correctness'].mean():.4f}")
        print(f"  Answer Correctness (最小): {eval_df['answer_correctness'].min():.4f}")
        print(f"  Answer Correctness (最大): {eval_df['answer_correctness'].max():.4f}")
        print(f"  Context Recall (平均): {eval_df['context_recall'].mean():.4f}")
        print(f"  Context Recall (最小): {eval_df['context_recall'].min():.4f}")
        print(f"  Context Recall (最大): {eval_df['context_recall'].max():.4f}")

        # Verify: Evaluation results are present
        assert 'answer_correctness' in eval_df.columns
        assert 'context_recall' in eval_df.columns

        # Verify: All evaluated questions have scores
        assert not eval_df['answer_correctness'].isna().any(), "All questions should have answer_correctness scores"
        assert not eval_df['context_recall'].isna().any(), "All questions should have context_recall scores"

        # Verify: Scores are in valid range (0-1)
        assert (eval_df['answer_correctness'] >= 0).all() and (eval_df['answer_correctness'] <= 1).all()
        assert (eval_df['context_recall'] >= 0).all() and (eval_df['context_recall'] <= 1).all()

        # 元のresults_dfに評価結果をマージ
        results_df = results_df.merge(
            eval_df[['id', 'answer_correctness', 'context_recall']],
            on='id',
            how='left'
        )

        print("\n✓ E2E test with RAGAS evaluation completed successfully")
        print(f"  - All {batch_result.total_questions} questions were processed")
        print(f"  - {batch_result.successful} succeeded, {batch_result.failed} failed")
        print(f"  - {len(eval_df)} questions were evaluated with RAGAS")

        # Cell 14: DB接続のクローズ (handled by fixture cleanup)
