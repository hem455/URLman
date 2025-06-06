"""
Output Writer モジュールの単体テスト
Google Sheets API書き込み機能とフォーマット処理のテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# 適切なパッケージインポート
from src.output_writer import OutputWriter, OutputColumns, WriteResult
from src.scorer import HPCandidate
from src.search_agent import CompanyInfo


class TestOutputColumns:
    """OutputColumnsデータクラスのテスト"""
    
    def test_output_columns_creation(self):
        """OutputColumns作成のテスト"""
        columns = OutputColumns(
            url="E",
            score="F",
            status="G",
            query="H",
            timestamp="I"
        )
        
        assert columns.url == "E"
        assert columns.score == "F"
        assert columns.status == "G"
        assert columns.query == "H"
        assert columns.timestamp == "I"

    def test_output_columns_defaults(self):
        """OutputColumnsデフォルト値のテスト"""
        columns = OutputColumns()
        
        assert columns.url == "E"
        assert columns.score == "F"
        assert columns.status == "G"
        assert columns.query == "H"
        assert columns.timestamp == "I"


class TestWriteResult:
    """WriteResultデータクラスのテスト"""
    
    def test_write_result_success(self):
        """成功時WriteResultのテスト"""
        result = WriteResult(
            success=True,
            company_id="001",
            row_number=2
        )
        
        assert result.success is True
        assert result.company_id == "001"
        assert result.row_number == 2
        assert result.error_message is None
    
    def test_write_result_failure(self):
        """失敗時WriteResultのテスト"""
        result = WriteResult(
            success=False,
            company_id="002",
            row_number=3,
            error_message="Test error"
        )
        
        assert result.success is False
        assert result.company_id == "002"
        assert result.row_number == 3
        assert result.error_message == "Test error"


class TestOutputWriter:
    """OutputWriterクラスのテスト"""
    
    def setup_method(self):
        """テスト用の設定"""
        # モックのGoogleSheetsClientを作成
        self.mock_sheets_client = Mock()
        
        # OutputWriterの初期化
        self.writer = OutputWriter(sheets_client=self.mock_sheets_client)
        
        # テスト用データ
        self.test_company = CompanyInfo(
            id="001",
            company_name="Barber Boss【バーバー ボス】",
            prefecture="東京都",
            industry="美容業"
        )
        
        self.test_candidate = HPCandidate(
            url="https://barberboss.co.jp",
            title="Barber Boss 公式サイト",
            description="バーバーボス公式ホームページ",
            search_rank=1,
            query_pattern="pattern_a",
            domain_similarity=95.0,
            is_top_page=True,
            total_score=12.0,
            judgment="自動採用",
            score_details={"domain": 5, "top_page": 5, "tld": 3}
        )
        
        # Gspreadモックの設定
        self.mock_gc = Mock()
        self.mock_spreadsheet = Mock()
        self.mock_worksheet = Mock()
        
        self.mock_sheets_client._get_gspread_client.return_value = self.mock_gc
        self.mock_gc.open_by_key.return_value = self.mock_spreadsheet
        self.mock_spreadsheet.worksheet.return_value = self.mock_worksheet
    
    def test_initialization(self):
        """OutputWriter初期化のテスト"""
        assert self.writer.sheets_client == self.mock_sheets_client
        assert isinstance(self.writer.output_columns, OutputColumns)
        assert self.writer.output_columns.url == "E"
    
    def test_write_single_result_success(self):
        """単一結果書き込み成功のテスト"""
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001",
            url="https://example.com",
            score=8.5,
            status="自動採用",
            query="pattern_a"
        )
        
        # 結果の確認
        assert result.success is True
        assert result.company_id == "001"
        assert result.row_number == 2
        assert result.error_message is None
        
        # モック呼び出しの確認
        self.mock_sheets_client._get_gspread_client.assert_called_once()
        self.mock_gc.open_by_key.assert_called_once_with("test_spreadsheet_id")
        self.mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
        self.mock_worksheet.batch_update.assert_called_once()
        
        # batch_updateの引数確認
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        assert len(update_calls) == 5  # URL, score, status, query, timestamp
        
        # 各更新の確認
        url_update = next(u for u in update_calls if u['range'] == 'E2')
        assert url_update['values'] == [["https://example.com"]]
        
        score_update = next(u for u in update_calls if u['range'] == 'F2')
        assert score_update['values'] == [[8.5]]
        
        status_update = next(u for u in update_calls if u['range'] == 'G2')
        assert status_update['values'] == [["自動採用"]]
        
        query_update = next(u for u in update_calls if u['range'] == 'H2')
        assert query_update['values'] == [["pattern_a"]]
    
    def test_write_single_result_with_none_values(self):
        """None値を含む単一結果書き込みのテスト"""
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=3,
            company_id="002",
            url=None,
            score=None,
            status="HP未発見",
            query=None
        )
        
        # 結果の確認
        assert result.success is True
        assert result.company_id == "002"
        assert result.row_number == 3
        
        # batch_updateの引数確認（None値は除外される）
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        assert len(update_calls) == 2  # status, timestamp のみ
        
        status_update = next(u for u in update_calls if u['range'] == 'G3')
        assert status_update['values'] == [["HP未発見"]]
    
    def test_write_single_result_failure(self):
        """単一結果書き込み失敗のテスト"""
        # 例外を発生させる
        self.mock_sheets_client._get_gspread_client.side_effect = Exception("API Error")
        
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001",
            url="https://example.com",
            score=8.5,
            status="自動採用",
            query="pattern_a"
        )
        
        # 結果の確認
        assert result.success is False
        assert result.company_id == "001"
        assert result.row_number == 2
        assert "API Error" in result.error_message
    
    def test_write_batch_results_success(self):
        """バッチ結果書き込み成功のテスト"""
        batch_data = [
            {
                'company_id': '001',
                'row_number': 2,
                'url': 'https://example1.com',
                'score': 8.5,
                'status': '自動採用',
                'query': 'pattern_a'
            },
            {
                'company_id': '002',
                'row_number': 3,
                'url': 'https://example2.com',
                'score': 6.0,
                'status': '要確認',
                'query': 'pattern_b'
            }
        ]
        
        results = self.writer.write_batch_results(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            results=batch_data
        )
        
        # 結果の確認
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].company_id == "001"
        assert results[1].company_id == "002"
        
        # batch_updateが呼ばれたことを確認
        self.mock_worksheet.batch_update.assert_called_once()
        
        # 更新データの確認（2件分 × 5項目 = 10個の更新）
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        assert len(update_calls) == 10
    
    def test_write_batch_results_with_partial_failure(self):
        """バッチ結果書き込み部分失敗のテスト"""
        batch_data = [
            {
                'company_id': '001',
                'row_number': 2,
                'url': 'https://example1.com',
                'score': 8.5,
                'status': '自動採用',
                'query': 'pattern_a'
            },
            {
                # row_numberが欠けている不正なデータ
                'company_id': '002',
                'url': 'https://example2.com',
                'score': 6.0,
                'status': '要確認',
                'query': 'pattern_b'
            }
        ]
        
        results = self.writer.write_batch_results(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            results=batch_data
        )
        
        # 結果の確認
        assert len(results) == 2
        assert results[0].success is True  # 正常なデータ
        assert results[1].success is False  # 不正なデータ
        assert "row_number" in results[1].error_message
    
    def test_write_error_status(self):
        """エラーステータス書き込みのテスト"""
        result = self.writer.write_error_status(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001",
            error_message="検索エラー"
        )
        
        # 結果の確認
        assert result.success is True
        assert result.company_id == "001"
        assert result.row_number == 2
        
        # エラーステータスが書き込まれたことを確認
        self.mock_worksheet.batch_update.assert_called_once()
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        
        # ステータス、クエリ（エラーメッセージ）、タイムスタンプが書き込まれる
        assert len(update_calls) == 3
        
        status_update = next(u for u in update_calls if u['range'] == 'G2')
        assert status_update['values'] == [["処理エラー"]]
        
        query_update = next(u for u in update_calls if u['range'] == 'H2')
        assert query_update['values'] == [["エラー: 検索エラー"]]
    
    def test_clear_row_data(self):
        """行データクリアのテスト"""
        result = self.writer.clear_row_data(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001"
        )
        
        # 結果の確認
        assert result.success is True
        assert result.company_id == "001"
        assert result.row_number == 2
        
        # 空文字でクリアされたことを確認
        self.mock_worksheet.batch_update.assert_called_once()
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        
        # 5列すべてがクリアされる
        assert len(update_calls) == 5
        
        for update in update_calls:
            assert update['values'] == [[""]]
    
    def test_set_output_columns(self):
        """出力列設定のテスト"""
        custom_columns = OutputColumns(
            url="F",
            score="G",
            status="H",
            query="I",
            timestamp="J"
        )
        
        self.writer.set_output_columns(custom_columns)
        
        assert self.writer.output_columns == custom_columns
        assert self.writer.output_columns.url == "F"
    
    def test_get_output_columns(self):
        """出力列取得のテスト"""
        columns = self.writer.get_output_columns()
        
        assert isinstance(columns, OutputColumns)
        assert columns.url == "E"
        assert columns.score == "F"
        assert columns.status == "G"
        assert columns.query == "H"
        assert columns.timestamp == "I"


class TestOutputWriterEdgeCases:
    """OutputWriter のエッジケースとエラーハンドリングのテスト"""
    
    def setup_method(self):
        """テスト用の設定"""
        self.mock_sheets_client = Mock()
        self.writer = OutputWriter(sheets_client=self.mock_sheets_client)
        
        # Gspreadモックの設定
        self.mock_gc = Mock()
        self.mock_spreadsheet = Mock()
        self.mock_worksheet = Mock()
        
        self.mock_sheets_client._get_gspread_client.return_value = self.mock_gc
        self.mock_gc.open_by_key.return_value = self.mock_spreadsheet
        self.mock_spreadsheet.worksheet.return_value = self.mock_worksheet
    
    def test_large_batch_write(self):
        """大量データのバッチ書き込みテスト"""
        # 100件のテストデータを作成
        batch_data = []
        for i in range(100):
            batch_data.append({
                'company_id': f'{i:03d}',
                'row_number': i + 2,
                'url': f'https://example{i}.com',
                'score': float(i % 10),
                'status': '自動採用' if i % 2 == 0 else '要確認',
                'query': f'pattern_{i % 3}'
            })
        
        results = self.writer.write_batch_results(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            results=batch_data
        )
        
        # 結果の確認
        assert len(results) == 100
        assert all(r.success for r in results)
        
        # 大量の更新が実行されたことを確認
        self.mock_worksheet.batch_update.assert_called_once()
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        assert len(update_calls) == 500  # 100件 × 5項目
    
    def test_unicode_data_writing(self):
        """Unicode データの書き込みテスト"""
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001",
            url="https://日本語ドメイン.com",
            score=8.5,
            status="自動採用",
            query="株式会社テスト 公式サイト"
        )
        
        # 結果の確認
        assert result.success is True
        
        # Unicode文字が正しく処理されたことを確認
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        
        url_update = next(u for u in update_calls if u['range'] == 'E2')
        assert url_update['values'] == [["https://日本語ドメイン.com"]]
        
        query_update = next(u for u in update_calls if u['range'] == 'H2')
        assert query_update['values'] == [["株式会社テスト 公式サイト"]]
    
    def test_write_with_api_error(self):
        """API エラー時の処理テスト"""
        # gspread.exceptions.APIError をシミュレート
        self.mock_worksheet.batch_update.side_effect = Exception("API Rate Limit Exceeded")
        
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=2,
            company_id="001",
            url="https://example.com",
            score=8.5,
            status="自動採用",
            query="pattern_a"
        )
        
        # エラーが適切に処理されたことを確認
        assert result.success is False
        assert result.company_id == "001"
        assert "API Rate Limit Exceeded" in result.error_message
    
    def test_custom_column_mapping(self):
        """カスタム列マッピングのテスト"""
        custom_columns = OutputColumns(
            url="J",
            score="K",
            status="L",
            query="M",
            timestamp="N"
        )
        
        self.writer.set_output_columns(custom_columns)
        
        result = self.writer.write_single_result(
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            row_number=5,
            company_id="001",
            url="https://example.com",
            score=8.5,
            status="自動採用",
            query="pattern_a"
        )
        
        # カスタム列が使用されたことを確認
        assert result.success is True
        
        update_calls = self.mock_worksheet.batch_update.call_args[0][0]
        
        # カスタム列範囲が使用されていることを確認
        ranges = [update['range'] for update in update_calls]
        assert 'J5' in ranges  # URL列
        assert 'K5' in ranges  # Score列
        assert 'L5' in ranges  # Status列
        assert 'M5' in ranges  # Query列
        assert 'N5' in ranges  # Timestamp列 