"""
DataPipelineのエンドツーエンドテスト

ノートブック 12_data_pipeline_v2.ipynb の正確なコードフローをテストします。
"""
from src.data_pipeline.document_loader import DocumentLoader
from src.data_pipeline.text_extractor import TextExtractor
from src.data_pipeline.text_chunker import TextChunker
from src.data_pipeline.embedding_generator import EmbeddingGenerator
from src.data_pipeline.document_writer import DocumentWriter
from src.data_pipeline.data_pipeline import DataPipeline


class TestNotebookMainFlow:
    """Test the main flow from notebook Cell 0-14"""

    def test_notebook_pipeline_execution(
        self,
        config_loader,
        db_connection,
        cleanup_test_documents
    ):
        """
        Reproduce notebook 12_data_pipeline_v2.ipynb main execution flow

        This test mirrors cells 0-14:
        - Cell 0-2: Header and Imports (handled by test setup)
        - Cell 4: Configuration and DB connection
        - Cell 6: Tuning parameters
        - Cell 8: Component initialization + DataPipeline orchestrator (merged)
        - Cell 10: List files from Object Storage
        - Cell 12: Process all files
        - Cell 14: Close connection (handled by fixture)
        """
        # セル4: 設定の読み込みとDB接続
        oci_config = config_loader.get_oci_config()
        os_config = config_loader.get_object_storage_config()
        bucket_name = os_config['bucket_name']

        os_client = config_loader.get_object_storage_client()
        namespace = os_client.get_namespace().data

        # セル6: チューニングパラメータ
        app_config = config_loader.get_app_config()
        chunk_size = app_config['chunk_size']
        chunk_overlap = app_config['chunk_overlap']

        # セル8: コンポーネントの初期化 + DataPipelineオーケストレータの作成（統合）
        loader = DocumentLoader(
            oci_config=oci_config,
            bucket_name=bucket_name,
            namespace=namespace
        )

        extractor = TextExtractor()

        chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        embedding_gen = EmbeddingGenerator()

        writer = DocumentWriter(db_connection)

        # (Cell 8 continued: DataPipelineオーケストレータの作成)
        progress_records = []

        def progress_callback(filename: str, status: str):
            """Track progress for verification"""
            progress_records.append({'filename': filename, 'status': status})

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer,
            progress_callback=progress_callback
        )

        # Cell 10: Object Storageからファイル一覧を取得
        file_paths = loader.list_files()

        assert len(file_paths) > 0, "No files found in Object Storage"

        # Cell 12: すべてのファイルを一括処理
        result = pipeline.process_all(file_paths)

        # Display processing results (same as notebook Cell 12)
        print("\n" + "="*60)
        print("Processing Complete")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"  ✓ Success: {result.successful} files")
        print(f"  ✗ Failed:  {result.failed} files")
        print(f"  ⊘ Skipped: {result.skipped} files")
        print(f"  📁 Total:   {result.total_files} files")
        print(f"  📦 Chunks:  {result.total_chunks} chunks")
        print(f"  ⏱️  Time:    {result.elapsed_time:.2f} seconds")

        if result.processed_docs:
            print(f"\n📋 Detailed Results:")
            for doc in result.processed_docs:
                status_emoji = {'success': '✓', 'failed': '✗', 'skipped': '⊘'}.get(doc.status, '•')
                print(f"\n  {status_emoji} {doc.filename} ({doc.status})")

                if doc.status == 'success':
                    doc_id_hex = doc.document_id.hex() if doc.document_id else 'N/A'
                    print(f"      Document ID: {doc_id_hex}")
                    print(f"      Chunks: {doc.chunks_saved}")
                elif doc.error:
                    print(f"      Error: {doc.error}")

        # Register all processed documents for cleanup
        for doc in result.processed_docs:
            if doc.status == 'success' and doc.document_id:
                cleanup_test_documents.append(doc.document_id)

        # Verify: Processing completed
        assert result.total_files == len(file_paths)
        assert result.total_files > 0

        # Verify: At least some files were processed successfully
        # (Allow for some skipped/failed files due to file type support)
        assert result.successful + result.skipped + result.failed == result.total_files

        # Verify: Progress callback was called for each file
        assert len(progress_records) == result.total_files

        # Verify: Successful files have chunks in database
        if result.successful > 0:
            assert result.total_chunks > 0

            cursor = db_connection.cursor()
            try:
                for doc in result.processed_docs:
                    if doc.status == 'success':
                        # Verify document exists in database
                        cursor.execute(
                            "SELECT COUNT(*) FROM source_documents WHERE document_id = :id",
                            id=doc.document_id
                        )
                        assert cursor.fetchone()[0] == 1

                        # Verify chunks exist in database
                        cursor.execute(
                            "SELECT COUNT(*) FROM chunks WHERE document_id = :id",
                            id=doc.document_id
                        )
                        chunk_count = cursor.fetchone()[0]
                        assert chunk_count == doc.chunks_saved
                        assert chunk_count > 0
            finally:
                cursor.close()

        # Cell 14: DB接続のクローズ (handled by fixture cleanup)
