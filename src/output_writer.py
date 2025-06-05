"""
Google Sheets データ書き込みモジュール
検索結果とスコアリング結果をGoogle Sheetsに書き込み
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time
import gspread
from googleapiclient.errors import HttpError

from .logger_config import get_logger
from .data_loader import GoogleSheetsClient

logger = get_logger(__name__)

@dataclass
class OutputColumns:
    """出力列の設定"""
    url: str = "E"          # HP URL列
    score: str = "F"        # スコア列
    status: str = "G"       # 判定結果列
    query: str = "H"        # 使用クエリ列
    timestamp: str = "I"    # 処理日時列

@dataclass
class WriteResult:
    """書き込み結果"""
    success: bool
    company_id: str
    row_number: int
    error_message: Optional[str] = None

class OutputWriter:
    """結果書き込みクラス"""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client
        self.output_columns = OutputColumns()
    
    def write_single_result(self, 
                          spreadsheet_id: str,
                          sheet_name: str,
                          row_number: int,
                          company_id: str,
                          url: Optional[str],
                          score: Optional[float],
                          status: str,
                          query: Optional[str]) -> WriteResult:
        """
        単一企業の結果を書き込み
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
            row_number: 書き込み対象の行番号（1ベース）
            company_id: 企業ID
            url: 検出されたHP URL
            score: スコア値
            status: 判定結果（自動採用/要確認/手動確認）
            query: 使用したクエリ
        
        Returns:
            WriteResult: 書き込み結果
        """
        try:
            logger.debug(f"単一結果書き込み開始: {company_id} (行 {row_number})")
            
            # gspreadクライアントを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 書き込みデータを準備
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            updates = []
            
            # URL
            if url is not None:
                updates.append({
                    'range': f'{self.output_columns.url}{row_number}',
                    'values': [[url]]
                })
            
            # スコア
            if score is not None:
                updates.append({
                    'range': f'{self.output_columns.score}{row_number}',
                    'values': [[score]]
                })
            
            # ステータス
            updates.append({
                'range': f'{self.output_columns.status}{row_number}',
                'values': [[status]]
            })
            
            # クエリ
            if query is not None:
                updates.append({
                    'range': f'{self.output_columns.query}{row_number}',
                    'values': [[query]]
                })
            
            # タイムスタンプ
            updates.append({
                'range': f'{self.output_columns.timestamp}{row_number}',
                'values': [[timestamp]]
            })
            
            # バッチ更新実行
            if updates:
                worksheet.batch_update(updates)
            
            logger.info(f"単一結果書き込み完了: {company_id} (行 {row_number})")
            return WriteResult(
                success=True,
                company_id=company_id,
                row_number=row_number
            )
            
        except Exception as e:
            error_msg = f"単一結果書き込み失敗: {company_id} (行 {row_number}) - {e}"
            logger.error(error_msg)
            return WriteResult(
                success=False,
                company_id=company_id,
                row_number=row_number,
                error_message=error_msg
            )
    
    def write_batch_results(self, 
                          spreadsheet_id: str,
                          sheet_name: str,
                          results: List[Dict[str, Any]]) -> List[WriteResult]:
        """
        複数企業の結果をバッチ書き込み
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
            results: 結果データのリスト
                    [{'company_id': str, 'row_number': int, 'url': str, 'score': float, 'status': str, 'query': str}, ...]
        
        Returns:
            List[WriteResult]: 各書き込み結果のリスト
        """
        try:
            logger.info(f"バッチ結果書き込み開始: {len(results)}件")
            
            # gspreadクライアントを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # バッチ更新データを準備
            updates = []
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            write_results = []
            
            for result in results:
                try:
                    row_number = result['row_number']
                    company_id = result['company_id']
                    
                    # URL
                    if 'url' in result and result['url'] is not None:
                        updates.append({
                            'range': f'{self.output_columns.url}{row_number}',
                            'values': [[result['url']]]
                        })
                    
                    # スコア
                    if 'score' in result and result['score'] is not None:
                        updates.append({
                            'range': f'{self.output_columns.score}{row_number}',
                            'values': [[result['score']]]
                        })
                    
                    # ステータス
                    if 'status' in result:
                        updates.append({
                            'range': f'{self.output_columns.status}{row_number}',
                            'values': [[result['status']]]
                        })
                    
                    # クエリ
                    if 'query' in result and result['query'] is not None:
                        updates.append({
                            'range': f'{self.output_columns.query}{row_number}',
                            'values': [[result['query']]]
                        })
                    
                    # タイムスタンプ
                    updates.append({
                        'range': f'{self.output_columns.timestamp}{row_number}',
                        'values': [[timestamp]]
                    })
                    
                    write_results.append(WriteResult(
                        success=True,
                        company_id=company_id,
                        row_number=row_number
                    ))
                    
                except Exception as e:
                    error_msg = f"バッチデータ準備エラー: {result.get('company_id', 'unknown')} - {e}"
                    logger.warning(error_msg)
                    write_results.append(WriteResult(
                        success=False,
                        company_id=result.get('company_id', 'unknown'),
                        row_number=result.get('row_number', 0),
                        error_message=error_msg
                    ))
            
            # バッチ更新実行
            if updates:
                try:
                    worksheet.batch_update(updates)
                    logger.info(f"バッチ結果書き込み完了: {len(updates)}件の更新")
                except Exception as e:
                    logger.error(f"バッチ更新実行エラー: {e}")
                    # 全ての結果を失敗に変更
                    for wr in write_results:
                        if wr.success:
                            wr.success = False
                            wr.error_message = f"バッチ更新実行エラー: {e}"
            
            return write_results
            
        except Exception as e:
            error_msg = f"バッチ結果書き込み失敗: {e}"
            logger.error(error_msg)
            # 全て失敗として返す
            return [WriteResult(
                success=False,
                company_id=result.get('company_id', 'unknown'),
                row_number=result.get('row_number', 0),
                error_message=error_msg
            ) for result in results]
    
    def write_error_status(self, 
                         spreadsheet_id: str,
                         sheet_name: str,
                         row_number: int,
                         company_id: str,
                         error_message: str) -> WriteResult:
        """
        エラー状態を書き込み
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
            row_number: 書き込み対象の行番号
            company_id: 企業ID
            error_message: エラーメッセージ
        
        Returns:
            WriteResult: 書き込み結果
        """
        try:
            logger.debug(f"エラー状態書き込み開始: {company_id} (行 {row_number})")
            
            # gspreadクライアントを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # エラー状態を書き込み
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            updates = [
                {
                    'range': f'{self.output_columns.status}{row_number}',
                    'values': [['処理エラー']]
                },
                {
                    'range': f'{self.output_columns.query}{row_number}',
                    'values': [[f'エラー: {error_message}']]
                },
                {
                    'range': f'{self.output_columns.timestamp}{row_number}',
                    'values': [[timestamp]]
                }
            ]
            
            worksheet.batch_update(updates)
            
            logger.info(f"エラー状態書き込み完了: {company_id} (行 {row_number})")
            return WriteResult(
                success=True,
                company_id=company_id,
                row_number=row_number
            )
            
        except Exception as e:
            error_msg = f"エラー状態書き込み失敗: {company_id} (行 {row_number}) - {e}"
            logger.error(error_msg)
            return WriteResult(
                success=False,
                company_id=company_id,
                row_number=row_number,
                error_message=error_msg
            )
    
    def clear_row_data(self, 
                      spreadsheet_id: str,
                      sheet_name: str,
                      row_number: int,
                      company_id: str) -> WriteResult:
        """
        指定行の出力データをクリア
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
            row_number: 対象行番号
            company_id: 企業ID
        
        Returns:
            WriteResult: 書き込み結果
        """
        try:
            logger.debug(f"行データクリア開始: {company_id} (行 {row_number})")
            
            # gspreadクライアントを取得
            gc = self.sheets_client._get_gspread_client()
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # 出力列をクリア
            updates = [
                {
                    'range': f'{self.output_columns.url}{row_number}',
                    'values': [['']]
                },
                {
                    'range': f'{self.output_columns.score}{row_number}',
                    'values': [['']]
                },
                {
                    'range': f'{self.output_columns.status}{row_number}',
                    'values': [['']]
                },
                {
                    'range': f'{self.output_columns.query}{row_number}',
                    'values': [['']]
                },
                {
                    'range': f'{self.output_columns.timestamp}{row_number}',
                    'values': [['']]
                }
            ]
            
            worksheet.batch_update(updates)
            
            logger.info(f"行データクリア完了: {company_id} (行 {row_number})")
            return WriteResult(
                success=True,
                company_id=company_id,
                row_number=row_number
            )
            
        except Exception as e:
            error_msg = f"行データクリア失敗: {company_id} (行 {row_number}) - {e}"
            logger.error(error_msg)
            return WriteResult(
                success=False,
                company_id=company_id,
                row_number=row_number,
                error_message=error_msg
            )
    
    def set_output_columns(self, output_columns: OutputColumns):
        """
        出力列設定を変更
        
        Args:
            output_columns: 新しい出力列設定
        """
        self.output_columns = output_columns
        logger.info(f"出力列設定を変更しました: {output_columns}")
    
    def get_output_columns(self) -> OutputColumns:
        """
        現在の出力列設定を取得
        
        Returns:
            OutputColumns: 現在の出力列設定
        """
        return self.output_columns

def create_output_writer_from_config(config: Dict[str, Any]) -> OutputWriter:
    """
    設定辞書からOutputWriterインスタンスを作成
    
    Args:
        config: 設定辞書（google_sheetsセクション）
    
    Returns:
        OutputWriterインスタンス
    """
    google_sheets_config = config.get('google_sheets', {})
    service_account_file = google_sheets_config.get('service_account_file')
    
    if not service_account_file:
        raise ValueError("Google Sheets設定にservice_account_fileが指定されていません")
    
    sheets_client = GoogleSheetsClient(service_account_file)
    output_writer = OutputWriter(sheets_client)
    
    # 出力列の設定があれば適用
    output_columns_config = google_sheets_config.get('output_columns', {})
    if output_columns_config:
        output_columns = OutputColumns(
            url=output_columns_config.get('url', 'E'),
            score=output_columns_config.get('score', 'F'),
            status=output_columns_config.get('status', 'G'),
            query=output_columns_config.get('query', 'H'),
            timestamp=output_columns_config.get('timestamp', 'I')
        )
        output_writer.set_output_columns(output_columns)
    
    return output_writer 