"""
Google Sheets データ読み込みモジュール
フェーズ1: 指定範囲の企業データ読み込み
フェーズ3: 未処理行の特定と読み込み
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .logger_config import get_logger
from .search_agent import CompanyInfo

logger = get_logger(__name__)

@dataclass
class SheetConfig:
    """Google Sheets設定情報"""
    service_account_file: str
    spreadsheet_id: str
    sheet_name: str
    input_columns: Dict[str, str]  # フィールド名 -> 列ID のマッピング
    start_row: int = 2  # データ開始行（ヘッダーを除く）
    end_row: Optional[int] = None  # 終了行（Noneの場合は全行）

class GoogleSheetsClient:
    """Google Sheets API クライアント"""
    
    def __init__(self, service_account_file: str):
        self.service_account_file = service_account_file
        self._gspread_client = None
        self._sheets_service = None
        
        # 必要なスコープを定義
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    
    def _get_credentials(self) -> Credentials:
        """サービスアカウントの認証情報を取得"""
        try:
            if not os.path.exists(self.service_account_file):
                raise FileNotFoundError(f"サービスアカウントファイルが見つかりません: {self.service_account_file}")
            
            credentials = Credentials.from_service_account_file(
                self.service_account_file,
                scopes=self.scopes
            )
            logger.info("Google認証情報の取得に成功しました")
            return credentials
            
        except Exception as e:
            logger.error(f"Google認証情報の取得に失敗しました: {e}")
            raise
    
    def _get_gspread_client(self):
        """gspreadクライアントを取得（遅延初期化）"""
        if self._gspread_client is None:
            try:
                credentials = self._get_credentials()
                self._gspread_client = gspread.authorize(credentials)
                logger.info("gspreadクライアントの初期化に成功しました")
            except Exception as e:
                logger.error(f"gspreadクライアントの初期化に失敗しました: {e}")
                raise
        
        return self._gspread_client
    
    def _get_sheets_service(self):
        """Google Sheets APIサービスを取得（遅延初期化）"""
        if self._sheets_service is None:
            try:
                credentials = self._get_credentials()
                self._sheets_service = build('sheets', 'v4', credentials=credentials)
                logger.info("Google Sheets APIサービスの初期化に成功しました")
            except Exception as e:
                logger.error(f"Google Sheets APIサービスの初期化に失敗しました: {e}")
                raise
        
        return self._sheets_service
    
    def test_connection(self, spreadsheet_id: str) -> bool:
        """接続テスト"""
        try:
            gc = self._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet_names = [ws.title for ws in spreadsheet.worksheets()]
            logger.info(f"接続テスト成功。利用可能なシート: {worksheet_names}")
            return True
        except Exception as e:
            logger.error(f"接続テストに失敗しました: {e}")
            return False

class DataLoader:
    """データ読み込みクラス"""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client
    
    def load_companies_from_range(self, config: SheetConfig) -> List[CompanyInfo]:
        """
        指定範囲から企業データを読み込み（フェーズ1用）
        
        Args:
            config: シート設定情報
        
        Returns:
            CompanyInfoのリスト
        """
        try:
            logger.info(f"企業データ読み込み開始: {config.spreadsheet_id}/{config.sheet_name}")
            
            # gspreadを使用してデータを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(config.spreadsheet_id)
            worksheet = spreadsheet.worksheet(config.sheet_name)
            
            # 指定範囲のデータを取得
            if config.end_row:
                # 特定範囲を指定
                range_name = f"A{config.start_row}:Z{config.end_row}"
                values = worksheet.get(range_name)
            else:
                # 全データを取得
                all_values = worksheet.get_all_values()
                # ヘッダー行を除いたデータを取得
                values = all_values[config.start_row-1:] if len(all_values) >= config.start_row else []
            
            # データをCompanyInfoオブジェクトに変換
            companies = self._parse_company_data(values, config)
            
            logger.info(f"企業データ読み込み完了: {len(companies)}件")
            return companies
            
        except Exception as e:
            logger.error(f"企業データ読み込みに失敗しました: {e}")
            raise
    
    def load_unprocessed_companies(self, config: SheetConfig, 
                                 hp_url_column: str = None) -> List[CompanyInfo]:
        """
        未処理の企業データを読み込み（フェーズ3用）
        
        Args:
            config: シート設定情報
            hp_url_column: HP URL列の識別子（Noneの場合は設定から取得）
        
        Returns:
            未処理のCompanyInfoのリスト
        """
        try:
            logger.info(f"未処理企業データ読み込み開始: {config.spreadsheet_id}/{config.sheet_name}")
            
            # HP URL列を特定
            if hp_url_column is None:
                hp_url_column = config.input_columns.get('hp_url', 'E')
            
            # gspreadを使用してデータを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(config.spreadsheet_id)
            worksheet = spreadsheet.worksheet(config.sheet_name)
            
            # 全データを取得
            all_values = worksheet.get_all_values()
            
            if len(all_values) < config.start_row:
                logger.warning("データが見つかりませんでした")
                return []
            
            # ヘッダー行を取得
            header_row = all_values[0] if all_values else []
            data_rows = all_values[config.start_row-1:]
            
            # HP URL列のインデックスを取得
            hp_url_col_index = self._column_letter_to_index(hp_url_column)
            
            # 未処理行をフィルタリング
            unprocessed_rows = []
            for i, row in enumerate(data_rows):
                # 行の長さがHP URL列のインデックスより短い場合、または空の場合
                if len(row) <= hp_url_col_index or not row[hp_url_col_index].strip():
                    unprocessed_rows.append(row)
            
            # CompanyInfoオブジェクトに変換
            companies = self._parse_company_data(unprocessed_rows, config)
            
            logger.info(f"未処理企業データ読み込み完了: {len(companies)}件")
            return companies
            
        except Exception as e:
            logger.error(f"未処理企業データ読み込みに失敗しました: {e}")
            raise
    
    def _parse_company_data(self, values: List[List[str]], config: SheetConfig) -> List[CompanyInfo]:
        """
        生データをCompanyInfoオブジェクトのリストに変換
        
        Args:
            values: スプレッドシートから取得した生データ
            config: シート設定情報
        
        Returns:
            CompanyInfoのリスト
        """
        companies = []
        
        # 列のインデックスを取得
        id_col = self._column_letter_to_index(config.input_columns.get('id', 'A'))
        prefecture_col = self._column_letter_to_index(config.input_columns.get('prefecture', 'B'))
        industry_col = self._column_letter_to_index(config.input_columns.get('industry', 'C'))
        company_name_col = self._column_letter_to_index(config.input_columns.get('company_name', 'D'))
        
        for i, row in enumerate(values):
            try:
                # 必要な列のデータを取得（不足している場合は空文字列）
                company_id = self._safe_str(row[id_col]) if len(row) > id_col else ""
                prefecture = self._safe_str(row[prefecture_col]) if len(row) > prefecture_col else ""
                industry = self._safe_str(row[industry_col]) if len(row) > industry_col else ""
                company_name = self._safe_str(row[company_name_col]) if len(row) > company_name_col else ""
                
                # 必須フィールドのチェック
                if not company_id.strip() or not company_name.strip():
                    logger.warning(f"必須フィールドが不足している行をスキップしました (行 {i+config.start_row})")
                    continue
                
                # CompanyInfoオブジェクトを作成
                company = CompanyInfo(
                    id=company_id.strip(),
                    company_name=company_name.strip(),
                    prefecture=prefecture.strip(),
                    industry=industry.strip()
                )
                
                companies.append(company)
                
            except Exception as e:
                logger.warning(f"データ解析エラー (行 {i+config.start_row}): {e}")
                continue
        
        return companies
    
    def _safe_str(self, value) -> str:
        """
        任意の値を安全に文字列に変換
        
        Args:
            value: 変換する値（None、数値、文字列など）
        
        Returns:
            文字列表現
        """
        if value is None:
            return ""
        return str(value)
    
    def _column_letter_to_index(self, column_letter: str) -> int:
        """
        列文字（例：A, B, C）を0ベースのインデックスに変換
        
        Args:
            column_letter: 列文字（A-Z）
        
        Returns:
            0ベースの列インデックス
        """
        if not column_letter:
            return 0
        
        # A=0, B=1, C=2, ... Z=25の形式に変換
        return ord(column_letter.upper()) - ord('A')
    
    def get_sheet_info(self, spreadsheet_id: str, sheet_name: str) -> Dict[str, Any]:
        """
        シートの基本情報を取得
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
        
        Returns:
            シート情報の辞書
        """
        try:
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 基本情報を取得
            info = {
                'title': worksheet.title,
                'row_count': worksheet.row_count,
                'col_count': worksheet.col_count,
                'url': worksheet.url,
                'spreadsheet_title': spreadsheet.title
            }
            
            logger.info(f"シート情報取得成功: {info}")
            return info
            
        except Exception as e:
            logger.error(f"シート情報取得に失敗しました: {e}")
            raise

def create_data_loader_from_config(config: Dict[str, Any]) -> DataLoader:
    """
    設定辞書からDataLoaderインスタンスを作成
    
    Args:
        config: 設定辞書（google_sheetsセクション）
    
    Returns:
        DataLoaderインスタンス
    """
    google_sheets_config = config.get('google_sheets', {})
    service_account_file = google_sheets_config.get('service_account_file')
    
    if not service_account_file:
        raise ValueError("Google Sheets設定にservice_account_fileが指定されていません")
    
    sheets_client = GoogleSheetsClient(service_account_file)
    return DataLoader(sheets_client) 