"""
Data Pipeline Orchestrator

This module coordinates all data pipeline components to process documents
from Object Storage through to database storage.
"""
from dataclasses import dataclass
from typing import List, Optional, Callable, Any
import logging
import time
from .document_loader import DocumentLoader
from .text_extractor import TextExtractor
from .text_chunker import TextChunker
from .embedding_generator import EmbeddingGenerator
from .document_writer import DocumentWriter
from .exceptions import (
    DocumentLoaderError,
    TextExtractionError,
    ChunkingError,
    EmbeddingError,
    DocumentWriteError,
    DataPipelineError
)


@dataclass
class ProcessedDocument:
    """
    Single document processing result

    Attributes:
        filename: Document filename
        status: Processing status ('success' | 'failed' | 'skipped')
        document_id: Generated document ID (bytes) or None
        chunks_saved: Number of chunks saved
        error: Error message if failed, None otherwise
    """
    filename: str
    status: str
    document_id: Optional[bytes]
    chunks_saved: int
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """
    Overall pipeline execution result

    Attributes:
        total_files: Total number of files processed
        successful: Number of successfully processed files
        failed: Number of failed files
        skipped: Number of skipped files
        total_chunks: Total chunks created across all files
        processed_docs: List of individual document results
        elapsed_time: Total processing time in seconds
    """
    total_files: int
    successful: int
    failed: int
    skipped: int
    total_chunks: int
    processed_docs: List[ProcessedDocument]
    elapsed_time: float


class DataPipeline:
    """
    Data pipeline orchestrator that coordinates all components

    This class orchestrates the entire data ingestion pipeline:
    1. DocumentLoader - Download from Object Storage
    2. TextExtractor - Extract text from PDF/TXT/CSV
    3. TextChunker - Split into chunks
    4. EmbeddingGenerator - Generate embeddings
    5. DocumentWriter - Save to database

    Design:
    - NOT Singleton: Multiple pipelines with different configs
    - Composition: Uses all 5 component classes
    - Error Isolation: Continue processing even if one file fails
    - Progress Tracking: Optional callback for monitoring

    Example:
        >>> loader = DocumentLoader(oci_config, bucket, namespace)
        >>> extractor = TextExtractor()
        >>> chunker = TextChunker(chunk_size=500)
        >>> embedding_gen = EmbeddingGenerator()
        >>> writer = DocumentWriter(connection)
        >>>
        >>> pipeline = DataPipeline(
        ...     loader=loader,
        ...     extractor=extractor,
        ...     chunker=chunker,
        ...     embedding_gen=embedding_gen,
        ...     writer=writer
        ... )
        >>>
        >>> files = loader.list_files()
        >>> result = pipeline.process_all(files)
        >>> print(f"Processed: {result.successful}/{result.total_files}")
    """

    def __init__(
        self,
        loader: DocumentLoader,
        extractor: TextExtractor,
        chunker: TextChunker,
        embedding_gen: EmbeddingGenerator,
        writer: DocumentWriter,
        progress_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize DataPipeline orchestrator

        Args:
            loader: DocumentLoader instance
            extractor: TextExtractor instance
            chunker: TextChunker instance
            embedding_gen: EmbeddingGenerator instance
            writer: DocumentWriter instance
            progress_callback: Optional callback(filename, status)

        Raises:
            ValueError: If any required component is None
        """
        if loader is None:
            raise ValueError("loader is required")
        if extractor is None:
            raise ValueError("extractor is required")
        if chunker is None:
            raise ValueError("chunker is required")
        if embedding_gen is None:
            raise ValueError("embedding_gen is required")
        if writer is None:
            raise ValueError("writer is required")

        self.loader = loader
        self.extractor = extractor
        self.chunker = chunker
        self.embedding_gen = embedding_gen
        self.writer = writer
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

    def process_single(self, file_path: str) -> ProcessedDocument:
        """
        Process a single document through the pipeline

        Args:
            file_path: Object Storage file path

        Returns:
            ProcessedDocument: Processing result with status and metadata
        """
        try:
            # Step 1: Download from Object Storage
            self.logger.info(f"Processing: {file_path}")
            doc_metadata = self.loader.download_file(file_path)

            # Step 2: Extract text
            extracted = self.extractor.extract(
                content=doc_metadata.content,
                filename=doc_metadata.filename,
                content_type=doc_metadata.content_type
            )

            # Step 3: Chunk text
            chunked = self.chunker.chunk(extracted.text)

            # Handle empty chunks
            if not chunked.chunks:
                self.logger.warning(f"No chunks created for {doc_metadata.filename}")
                result = ProcessedDocument(
                    filename=doc_metadata.filename,
                    status='skipped',
                    document_id=None,
                    chunks_saved=0,
                    error="No chunks created from text"
                )
                if self.progress_callback:
                    self.progress_callback(doc_metadata.filename, 'skipped')
                return result

            # Step 4: Generate embeddings
            embeddings = []
            for chunk in chunked.chunks:
                embedding = self.embedding_gen.embed_query(chunk)
                embeddings.append(embedding.vector_str)

            # Step 5: Save to database
            # 5a. Save document metadata
            saved_doc = self.writer.save_document(
                filename=doc_metadata.filename,
                filtering=self._extract_filtering(doc_metadata.full_path),
                content_type=self._extract_content_type(doc_metadata.content_type),
                file_size=doc_metadata.file_size,
                text_length=extracted.text_length
            )

            # 5b. Save chunks with embeddings
            saved_chunks = self.writer.save_chunks(
                document_id=saved_doc.document_id,
                chunks=chunked.chunks,
                embeddings=embeddings
            )

            self.logger.info(
                f"Successfully processed {doc_metadata.filename}: "
                f"{saved_chunks.chunk_count} chunks"
            )

            result = ProcessedDocument(
                filename=doc_metadata.filename,
                status='success',
                document_id=saved_doc.document_id,
                chunks_saved=saved_chunks.chunk_count
            )

            if self.progress_callback:
                self.progress_callback(doc_metadata.filename, 'success')

            return result

        except TextExtractionError as e:
            # Unsupported file type - skip
            filename = file_path.split('/')[-1]
            self.logger.warning(f"Skipping {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='skipped',
                document_id=None,
                chunks_saved=0,
                error=str(e)
            )
            if self.progress_callback:
                self.progress_callback(filename, 'skipped')
            return result

        except (DocumentLoaderError, ChunkingError, EmbeddingError, DocumentWriteError) as e:
            # Known pipeline errors - mark as failed
            filename = file_path.split('/')[-1]
            self.logger.error(f"Failed to process {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='failed',
                document_id=None,
                chunks_saved=0,
                error=str(e)
            )
            if self.progress_callback:
                self.progress_callback(filename, 'failed')
            return result

        except Exception as e:
            # Unexpected error - mark as failed
            filename = file_path.split('/')[-1]
            self.logger.error(f"Unexpected error processing {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='failed',
                document_id=None,
                chunks_saved=0,
                error=f"Unexpected error: {str(e)}"
            )
            if self.progress_callback:
                self.progress_callback(filename, 'failed')
            return result

    def process_all(self, file_paths: List[str]) -> PipelineResult:
        """
        Process multiple documents through the pipeline

        Args:
            file_paths: List of Object Storage file paths

        Returns:
            PipelineResult: Overall processing statistics and results
        """
        start_time = time.time()

        processed_docs = []
        successful = 0
        failed = 0
        skipped = 0
        total_chunks = 0

        self.logger.info(f"Starting pipeline processing: {len(file_paths)} files")

        for file_path in file_paths:
            result = self.process_single(file_path)
            processed_docs.append(result)

            if result.status == 'success':
                successful += 1
                total_chunks += result.chunks_saved
            elif result.status == 'failed':
                failed += 1
            elif result.status == 'skipped':
                skipped += 1

        elapsed_time = time.time() - start_time

        self.logger.info(
            f"Pipeline complete: {successful} success, {failed} failed, "
            f"{skipped} skipped, {total_chunks} total chunks, "
            f"{elapsed_time:.2f}s elapsed"
        )

        return PipelineResult(
            total_files=len(file_paths),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_chunks=total_chunks,
            processed_docs=processed_docs,
            elapsed_time=elapsed_time
        )

    def _extract_filtering(self, full_path: str) -> str:
        """
        Extract filtering (folder name) from full path

        Args:
            full_path: Full Object Storage path (e.g., 'folder/file.pdf')

        Returns:
            Folder name or empty string
        """
        parts = full_path.split('/')
        if len(parts) > 1:
            return parts[0]
        return ''

    def _extract_content_type(self, mime_type: str) -> str:
        """
        Extract simple content type from MIME type

        Args:
            mime_type: MIME type (e.g., 'application/pdf')

        Returns:
            Simple type (e.g., 'pdf')
        """
        # Map common MIME types
        mime_map = {
            'application/pdf': 'pdf',
            'text/plain': 'txt',
            'text/csv': 'csv',
            'application/csv': 'csv'
        }

        return mime_map.get(mime_type, mime_type.split('/')[-1])
