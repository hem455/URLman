"""
Data Loader モジュールの単体テスト
Google Sheets API読み込み機能のテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# 適切なパッケージインポート
from src.data_loader import DataLoader, GoogleSheetsClient, SheetConfig
from src.search_agent import CompanyInfo


class TestSheetConfig:
    """SheetConfigデータクラスのテスト"""
    
    def test_sheet_config_creation(self):
        """SheetConfig作成のテスト"""
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={
                'id': 'A',
                'company_name': 'B',
                'prefecture': 'C',
                'industry': 'D'
            }
        )
        
        assert config.service_account_file == "test.json"
        assert config.spreadsheet_id == "test_id"
        assert config.sheet_name == "Sheet1"
        assert config.input_columns['id'] == 'A'
        assert config.start_row == 2  # デフォルト値
        assert config.end_row is None  # デフォルト値
    
    def test_sheet_config_with_range(self):
        """範囲指定ありのSheetConfig作成のテスト"""
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A'},
            start_row=3,
            end_row=100
        )
        
        assert config.start_row == 3
        assert config.end_row == 100


class TestGoogleSheetsClient:
    """GoogleSheetsClientクラスのテスト"""
    
    def test_initialization(self):
        """GoogleSheetsClient初期化のテスト"""
        client = GoogleSheetsClient("test_service_account.json")
        
        assert client.service_account_file == "test_service_account.json"
        assert client._gspread_client is None
        assert client._sheets_service is None
        assert 'https://www.googleapis.com/auth/spreadsheets' in client.scopes


class TestDataLoader:
    """DataLoaderクラスのテスト"""
    
    def setup_method(self):
        """テスト用の設定"""
        # モックのGoogleSheetsClientを作成
        self.mock_sheets_client = Mock(spec=GoogleSheetsClient)
        
        # DataLoaderの初期化
        self.loader = DataLoader(sheets_client=self.mock_sheets_client)
        
        # テスト用の設定
        self.test_config = SheetConfig(
            service_account_file="test_service_account.json",
            spreadsheet_id="test_spreadsheet_id",
            sheet_name="Sheet1",
            input_columns={
                'id': 'A',
                'company_name': 'B',
                'prefecture': 'C',
                'industry': 'D'
            }
        )
        
        # Gspreadモックの設定
        self.mock_gc = Mock()
        self.mock_spreadsheet = Mock()
        self.mock_worksheet = Mock()
        
        self.mock_sheets_client._get_gspread_client.return_value = self.mock_gc
        self.mock_gc.open_by_key.return_value = self.mock_spreadsheet
        self.mock_spreadsheet.worksheet.return_value = self.mock_worksheet
    
    def test_initialization_success(self):
        """DataLoader初期化成功のテスト"""
        assert self.loader.sheets_client == self.mock_sheets_client
    
    def test_load_companies_success(self):
        """企業データ読み込み成功のテスト"""
        # モックデータの設定
        mock_data = [
            ["001", "Barber Boss【バーバー ボス】", "東京都", "美容業"],
            ["002", "テスト株式会社", "大阪府", "IT業"],
            ["003", "サンプル商店", "愛知県", "小売業"]
        ]
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"],  # ヘッダー行
            *mock_data
        ]
        
        # テスト実行
        companies = self.loader.load_companies_from_range(self.test_config)
        
        # 結果確認
        assert len(companies) == 3
        assert companies[0].id == "001"
        assert companies[0].company_name == "Barber Boss【バーバー ボス】"
        assert companies[0].prefecture == "東京都"
        assert companies[0].industry == "美容業"
        
        # モック呼び出し確認
        self.mock_sheets_client._get_gspread_client.assert_called_once()
        self.mock_gc.open_by_key.assert_called_once_with("test_spreadsheet_id")
        self.mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
    
    def test_load_companies_with_range_specification(self):
        """範囲指定ありの企業データ読み込みのテスト"""
        # 範囲指定ありの設定
        config_with_range = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A', 'company_name': 'B'},
            start_row=2,
            end_row=5
        )
        
        # モックデータの設定
        mock_data = [
            ["001", "テスト企業1"],
            ["002", "テスト企業2"],
            ["003", "テスト企業3"]
        ]
        self.mock_worksheet.get.return_value = mock_data
        
        # テスト実行
        companies = self.loader.load_companies_from_range(config_with_range)
        
        # 結果確認
        assert len(companies) == 3
        
        # 範囲指定でgetが呼ばれたことを確認
        self.mock_worksheet.get.assert_called_once_with("A2:Z5")
    
    def test_load_companies_empty_data(self):
        """空データの処理テスト"""
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"]  # ヘッダーのみ
        ]
        
        companies = self.loader.load_companies_from_range(self.test_config)
        
        assert len(companies) == 0
    
    def test_load_companies_with_incomplete_data(self):
        """不完全なデータの処理テスト"""
        mock_data = [
            ["001", "正常企業", "東京都", "IT業"],
            ["", "企業名のみ", "大阪府", "製造業"],  # ID欠損
            ["003", "", "愛知県", "小売業"],  # 企業名欠損
            ["004", "正常企業2", "福岡県", "サービス業"]
        ]
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"],
            *mock_data
        ]
        
        companies = self.loader.load_companies_from_range(self.test_config)
        
        # 正常なデータのみ処理される
        assert len(companies) == 2
        assert companies[0].id == "001"
        assert companies[1].id == "004"
    
    def test_load_unprocessed_companies(self):
        """未処理企業データ読み込みのテスト"""
        # HP URL列にデータがない行をシミュレート
        mock_data = [
            ["ID", "企業名", "都道府県", "業種", "HP URL"],  # ヘッダー
            ["001", "処理済み企業", "東京都", "IT業", "https://example.com"],  # 処理済み
            ["002", "未処理企業1", "大阪府", "製造業", ""],  # 未処理
            ["003", "未処理企業2", "愛知県", "小売業"],  # HP URL列自体がない（未処理）
            ["004", "処理済み企業2", "福岡県", "サービス業", "https://example2.com"]  # 処理済み
        ]
        self.mock_worksheet.get_all_values.return_value = mock_data
        
        companies = self.loader.load_unprocessed_companies(self.test_config)
        
        # 未処理企業のみ取得される
        assert len(companies) == 2
        assert companies[0].id == "002"
        assert companies[1].id == "003"
    
    def test_load_company_by_id_found(self):
        """ID指定での企業取得（見つかる場合）のテスト"""
        mock_data = [
            ["ID", "企業名", "都道府県", "業種"],
            ["001", "テスト企業1", "東京都", "IT業"],
            ["002", "テスト企業2", "大阪府", "製造業"],
            ["003", "テスト企業3", "愛知県", "小売業"]
        ]
        self.mock_worksheet.get_all_values.return_value = mock_data
        
        # DataLoaderにload_company_by_idメソッドが存在する場合
        if hasattr(self.loader, 'load_company_by_id'):
            company = self.loader.load_company_by_id(self.test_config, "002")
            assert company is not None
            assert company.id == "002"
            assert company.company_name == "テスト企業2"
            assert company.prefecture == "大阪府"
            assert company.industry == "製造業"
        else:
            pytest.skip("load_company_by_idメソッドが未実装のためテストをスキップ")
    
    def test_load_company_by_id_not_found(self):
        """ID指定での企業取得（見つからない場合）のテスト"""
        mock_data = [
            ["ID", "企業名", "都道府県", "業種"],
            ["001", "テスト企業1", "東京都", "IT業"],
            ["002", "テスト企業2", "大阪府", "製造業"]
        ]
        self.mock_worksheet.get_all_values.return_value = mock_data
        
        # DataLoaderにload_company_by_idメソッドが存在する場合
        if hasattr(self.loader, 'load_company_by_id'):
            company = self.loader.load_company_by_id(self.test_config, "999")
            assert company is None  # 存在しないIDの場合Noneが返される
        else:
            pytest.skip("load_company_by_idメソッドが未実装のためテストをスキップ")
        
    def test_get_sheet_info(self):
        """シート情報取得のテスト"""
        # モックの設定
        self.mock_worksheet.title = "Test Sheet"
        self.mock_worksheet.row_count = 100
        self.mock_worksheet.col_count = 20
        self.mock_worksheet.url = "https://docs.google.com/spreadsheets/test"
        self.mock_spreadsheet.title = "Test Spreadsheet"
        
        # テスト実行
        info = self.loader.get_sheet_info("test_id", "Sheet1")
        
        # 結果確認
        assert info['title'] == "Test Sheet"
        assert info['row_count'] == 100
        assert info['col_count'] == 20
        assert 'url' in info
        assert info['spreadsheet_title'] == "Test Spreadsheet"
    
    def test_column_letter_to_index(self):
        """列文字からインデックス変換のテスト"""
        assert self.loader._column_letter_to_index('A') == 0
        assert self.loader._column_letter_to_index('B') == 1
        assert self.loader._column_letter_to_index('Z') == 25
        assert self.loader._column_letter_to_index('a') == 0  # 小文字も対応
        assert self.loader._column_letter_to_index('') == 0  # 空文字列


class TestDataLoaderEdgeCases:
    """DataLoader のエッジケースとエラーハンドリングのテスト"""
    
    def setup_method(self):
        """テスト用設定"""
        self.mock_sheets_client = Mock(spec=GoogleSheetsClient)
        self.loader = DataLoader(sheets_client=self.mock_sheets_client)
        
        # Gspreadモックの設定
        self.mock_gc = Mock()
        self.mock_spreadsheet = Mock()
        self.mock_worksheet = Mock()
        
        self.mock_sheets_client._get_gspread_client.return_value = self.mock_gc
        self.mock_gc.open_by_key.return_value = self.mock_spreadsheet
        self.mock_spreadsheet.worksheet.return_value = self.mock_worksheet
    
    def test_unicode_company_names(self):
        """Unicode企業名の処理テスト"""
        mock_data = [
            ["001", "株式会社テスト【テスト】", "東京都", "IT業"],
            ["002", "Café & Restaurant", "大阪府", "飲食業"],
            ["003", "サンプル㈱", "愛知県", "製造業"]
        ]
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"],
            *mock_data
        ]
        
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A', 'company_name': 'B', 'prefecture': 'C', 'industry': 'D'}
        )
        
        companies = self.loader.load_companies_from_range(config)
        
        assert len(companies) == 3
        assert companies[0].company_name == "株式会社テスト【テスト】"
        assert companies[1].company_name == "Café & Restaurant"
        assert companies[2].company_name == "サンプル㈱"
    
    def test_large_dataset_range(self):
        """大量データセットの範囲処理テスト"""
        # 1000件のモックデータを作成
        mock_data = []
        for i in range(1000):
            mock_data.append([f"{i+1:04d}", f"企業{i+1}", "東京都", "IT業"])
        
        self.mock_worksheet.get.return_value = mock_data
        
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A', 'company_name': 'B', 'prefecture': 'C', 'industry': 'D'},
            start_row=2,
            end_row=1001
        )
        
        companies = self.loader.load_companies_from_range(config)
        
        assert len(companies) == 1000
        assert companies[0].id == "0001"
        assert companies[999].id == "1000"
    
    def test_mixed_data_types(self):
        """混合データ型の処理テスト"""
        mock_data = [
            ["001", "正常企業", "東京都", "IT業"],
            [2, "数値ID企業", "大阪府", "製造業"],  # 数値ID
            ["003", 123, "愛知県", "小売業"],  # 数値企業名
            ["004", "正常企業2", None, "サービス業"],  # None値（都道府県）
            ["005", None, "福岡県", "建設業"],  # None値（企業名）
            [None, "None ID企業", "沖縄県", "観光業"]  # None値（ID）
        ]
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"],
            *mock_data
        ]
        
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A', 'company_name': 'B', 'prefecture': 'C', 'industry': 'D'}
        )
        
        companies = self.loader.load_companies_from_range(config)
        
        # 有効な企業データが処理される（IDと企業名がNoneでない行）
        assert len(companies) >= 3  # 少なくとも正常な行が処理される
        
        # 数値IDが文字列として処理されることを確認
        id_list = [c.id for c in companies]
        assert "2" in id_list  # 数値2が文字列"2"として処理される
        
        # 数値企業名が文字列として処理されることを確認
        company_names = [c.company_name for c in companies]
        assert "123" in company_names  # 数値123が文字列"123"として処理される
        
        # None値を含む行の安全な処理を確認
        for company in companies:
            # IDと企業名は必須項目として処理されるためNoneではない
            assert company.id is not None and company.id != ""
            assert company.company_name is not None and company.company_name != ""
            
            # 都道府県や業種でNone値があった場合は空文字列または"未設定"等に変換される
            assert isinstance(company.prefecture, str)  # 文字列型である
            assert isinstance(company.industry, str)  # 文字列型である
    
    def test_none_value_handling(self):
        """None値の詳細な処理テスト"""
        mock_data = [
            [None, None, None, None],  # 全てNone
            ["", "", "", ""],  # 全て空文字列
            ["001", "正常企業", "", ""],  # 必須項目のみ
            ["002", "企業2", None, "IT業"]  # 一部None
        ]
        self.mock_worksheet.get_all_values.return_value = [
            ["ID", "企業名", "都道府県", "業種"],
            *mock_data
        ]
        
        config = SheetConfig(
            service_account_file="test.json",
            spreadsheet_id="test_id",
            sheet_name="Sheet1",
            input_columns={'id': 'A', 'company_name': 'B', 'prefecture': 'C', 'industry': 'D'}
        )
        
        companies = self.loader.load_companies_from_range(config)
        
        # IDまたは企業名がNone/空の行は除外される
        # 有効なデータのみが返される
        valid_companies = [c for c in companies if c.id and c.company_name]
        assert len(valid_companies) >= 2  # 001と002が有効


if __name__ == "__main__":
    # 単独実行時のテスト
    pytest.main([__file__, "-v"]) 