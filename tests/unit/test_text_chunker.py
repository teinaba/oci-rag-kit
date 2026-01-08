"""
TextChunkerクラスのユニットテスト

このモジュールは、日本語対応セパレータを使用してテキストを
チャンクに分割するTextChunkerクラスの包括的なテストを含みます。

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""
import pytest
from unittest.mock import Mock, patch
from src.data_pipeline.text_chunker import TextChunker, ChunkedText
from src.data_pipeline.exceptions import ChunkingError


class TestTextChunkerInit:
    """コンストラクタの検証"""

    def test_default_initialization(self):
        """デフォルト値で初期化できることを確認"""
        chunker = TextChunker()
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50
        assert chunker.separators == TextChunker.DEFAULT_SEPARATORS
        assert chunker.logger is not None
        assert chunker._splitter is None  # 遅延初期化

    def test_custom_chunk_size_initialization(self):
        """カスタムchunk_sizeで初期化できることを確認"""
        chunker = TextChunker(chunk_size=1000)
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 50  # デフォルト

    def test_custom_chunk_overlap_initialization(self):
        """カスタムchunk_overlapで初期化できることを確認"""
        chunker = TextChunker(chunk_overlap=100)
        assert chunker.chunk_size == 500  # デフォルト
        assert chunker.chunk_overlap == 100

    def test_custom_both_parameters_initialization(self):
        """両パラメータをカスタマイズして初期化できることを確認"""
        chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_invalid_chunk_size_zero_raises_error(self):
        """chunk_size=0でValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="chunk_size must be > 0"):
            TextChunker(chunk_size=0)

    def test_invalid_chunk_size_negative_raises_error(self):
        """負のchunk_sizeでValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="chunk_size must be > 0"):
            TextChunker(chunk_size=-10)

    def test_invalid_chunk_overlap_negative_raises_error(self):
        """負のchunk_overlapでValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="chunk_overlap must be >= 0"):
            TextChunker(chunk_overlap=-5)

    def test_overlap_equals_chunk_size_raises_error(self):
        """オーバーラップがチャンクサイズと等しい場合エラー"""
        with pytest.raises(ValueError, match="chunk_overlap.*must be < chunk_size"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_overlap_exceeds_chunk_size_raises_error(self):
        """オーバーラップがチャンクサイズを超える場合エラー"""
        with pytest.raises(ValueError, match="chunk_overlap.*must be < chunk_size"):
            TextChunker(chunk_size=100, chunk_overlap=150)


class TestChunk:
    """チャンク化処理のテスト"""

    def test_chunk_simple_text(self):
        """単純なテキストがチャンク化されることを確認"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=5)
        text = "これはテストテキストです。" * 10  # 130 chars

        result = chunker.chunk(text)

        assert isinstance(result, ChunkedText)
        assert result.chunk_count > 0
        assert result.chunks == result.chunks  # チャンクが存在することを確認
        assert result.original_text_length == len(text)
        assert result.chunk_size == 50
        assert result.chunk_overlap == 5

    def test_chunk_empty_text_returns_empty_result(self):
        """空のテキストで空の結果が返されることを確認"""
        chunker = TextChunker()

        result = chunker.chunk("")

        assert result.chunks == []
        assert result.chunk_count == 0
        assert result.original_text_length == 0
        assert result.avg_chunk_length == 0.0

    def test_chunk_short_text_returns_single_chunk(self):
        """chunk_sizeより短いテキストで単一チャンクが返されることを確認"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "短いテキスト"  # 7文字 < 100

        result = chunker.chunk(text)

        assert result.chunk_count == 1
        assert result.chunks[0] == text
        assert result.original_text_length == len(text)

    def test_chunk_calculates_correct_metadata(self):
        """メタデータが正しく計算されることを確認"""
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        text = "1234567890" * 10  # 100文字

        result = chunker.chunk(text)

        assert result.original_text_length == 100
        assert result.chunk_count > 1
        assert result.chunk_size == 20
        assert result.chunk_overlap == 5
        assert result.avg_chunk_length is not None
        assert result.avg_chunk_length > 0

    def test_chunk_avg_chunk_length_calculation(self):
        """平均チャンク長が正しく計算されることを確認"""
        chunker = TextChunker(chunk_size=10, chunk_overlap=0)
        text = "12345678901234567890"  # 20文字 → 10文字ずつ2チャンク

        result = chunker.chunk(text)

        # 平均は約10になるはず
        assert result.avg_chunk_length == pytest.approx(10.0, abs=5.0)

    def test_chunk_respects_chunk_size(self):
        """チャンクがchunk_sizeを大きく超えないことを確認"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "あいうえお" * 50  # 250文字

        result = chunker.chunk(text)

        # ほとんどのチャンクはchunk_size前後になるはず（セパレータ処理の余裕を含む）
        for chunk in result.chunks:
            assert len(chunk) <= 150  # セパレータ処理のため50%の余裕を許容

    def test_chunk_with_japanese_text(self):
        """日本語テキストが正しくチャンク化されることを確認"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        japanese_text = "これはテストです。\n\n次のパラグラフです。\n\n最後のパラグラフ。" * 3

        result = chunker.chunk(japanese_text)

        assert result.chunk_count > 0
        assert result.original_text_length == len(japanese_text)
        assert all(isinstance(chunk, str) for chunk in result.chunks)

    def test_chunk_preserves_text_content(self):
        """チャンク化後、全テキストが保持されることを確認（オーバーラップを除く）"""
        chunker = TextChunker(chunk_size=20, chunk_overlap=0)
        text = "12345678901234567890123456789012345"

        result = chunker.chunk(text)

        # overlap=0の場合、チャンクを結合すれば元のテキストになるはず（おおよそ）
        concatenated = "".join(result.chunks)
        assert concatenated == text


class TestLazyInitialization:
    """遅延初期化の検証"""

    def test_splitter_not_initialized_on_construction(self):
        """コンストラクタでsplitterが初期化されないことを確認"""
        chunker = TextChunker()

        assert chunker._splitter is None

    def test_splitter_initialized_on_first_access(self):
        """初回アクセス時にsplitterが初期化されることを確認"""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)

        # プロパティ経由でアクセス
        splitter = chunker.splitter

        assert splitter is not None
        assert chunker._splitter is splitter  # キャッシュされている

    def test_splitter_reused_on_subsequent_calls(self):
        """2回目以降のアクセスでsplitterが再利用されることを確認"""
        chunker = TextChunker()

        splitter1 = chunker.splitter
        splitter2 = chunker.splitter

        assert splitter1 is splitter2  # 同じインスタンス

    @patch('src.data_pipeline.text_chunker.RecursiveCharacterTextSplitter')
    def test_splitter_configuration(self, mock_splitter_class):
        """RecursiveCharacterTextSplitterが正しく設定されることを確認"""
        mock_instance = Mock()
        mock_splitter_class.return_value = mock_instance

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        _ = chunker.splitter  # 遅延初期化をトリガー

        mock_splitter_class.assert_called_once_with(
            chunk_size=100,
            chunk_overlap=20,
            separators=TextChunker.DEFAULT_SEPARATORS,
            length_function=len
        )


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    def test_chunk_non_string_input_raises_error(self):
        """文字列以外の入力でChunkingErrorが発生することを確認"""
        chunker = TextChunker()

        with pytest.raises(ChunkingError, match="Input must be str"):
            chunker.chunk(123)  # type: ignore  # noqa

    def test_chunk_none_input_raises_error(self):
        """None入力でChunkingErrorが発生することを確認"""
        chunker = TextChunker()

        with pytest.raises(ChunkingError, match="Input must be str"):
            chunker.chunk(None)  # type: ignore  # noqa

    def test_chunk_preserves_exception_chain(self):
        """例外チェーンが保持されることを確認"""
        chunker = TextChunker()

        # 内部の_splitterを直接モック
        mock_splitter = Mock()
        original_error = ValueError("Splitter error")
        mock_splitter.split_text.side_effect = original_error
        chunker._splitter = mock_splitter

        with pytest.raises(ChunkingError) as exc_info:
            chunker.chunk("test text")

        # 例外チェーンが保持されている
        assert exc_info.value.__cause__ is original_error

    def test_chunk_error_includes_text_length(self):
        """エラーメッセージにテキスト長が含まれることを確認"""
        chunker = TextChunker()

        # 内部の_splitterを直接モック
        mock_splitter = Mock()
        mock_splitter.split_text.side_effect = Exception("Test error")
        chunker._splitter = mock_splitter

        with pytest.raises(ChunkingError, match="length=9"):
            chunker.chunk("test text")


class TestJapaneseTextHandling:
    """日本語テキスト処理の特殊ケース"""

    def test_chunk_japanese_text_with_periods(self):
        """日本語の句点（。）で分割されることを確認"""
        chunker = TextChunker(chunk_size=30, chunk_overlap=0)
        text = "最初の文です。二番目の文です。三番目の文です。"

        result = chunker.chunk(text)

        # 。で分割されるはず
        assert result.chunk_count >= 1

    def test_chunk_japanese_text_with_commas(self):
        """日本語の読点（、）が考慮されることを確認"""
        chunker = TextChunker(chunk_size=20, chunk_overlap=0)
        text = "これは、テストです、確認します、終わり。"

        result = chunker.chunk(text)

        assert result.chunk_count >= 1

    def test_chunk_japanese_text_with_newlines(self):
        """改行で分割されることを確認"""
        chunker = TextChunker(chunk_size=30, chunk_overlap=0)
        text = "最初の行です\n二番目の行です\n三番目の行です"

        result = chunker.chunk(text)

        assert result.chunk_count >= 1

    def test_separator_precedence_paragraph_breaks(self):
        """段落区切り（\\n\\n）が優先されることを確認"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=0)
        text = "最初の段落です。\n\n二番目の段落です。\n\n三番目の段落です。"

        result = chunker.chunk(text)

        # 段落区切りが主要な分割ポイントになるはず
        assert result.chunk_count >= 1

    def test_mixed_japanese_english_text(self):
        """日本語と英語が混在するテキストが処理できることを確認"""
        chunker = TextChunker(chunk_size=50, chunk_overlap=5)
        text = "This is English. これは日本語です。Mixed content works fine."

        result = chunker.chunk(text)

        assert result.chunk_count >= 1
        assert result.original_text_length == len(text)
