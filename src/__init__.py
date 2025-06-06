"""
会社HP自動検索・貼り付けツール - コアモジュール

主要コンポーネント:
- search_agent: Brave Search API連携とクエリ生成
- scorer: HP候補のスコアリングロジック
- data_loader: Google Sheets読み込み
- output_writer: Google Sheets書き込み
- utils: 共通ユーティリティ
"""

from .search_agent import SearchAgent, CompanyInfo, SearchResult, QueryGenerator
from .scorer import HPScorer, HPCandidate, ScoringConfig
from .data_loader import DataLoader, GoogleSheetsClient, SheetConfig
from .output_writer import OutputWriter, OutputColumns, WriteResult
from .utils import URLUtils, StringUtils, BlacklistChecker, ConfigManager
from .logger_config import get_logger

__all__ = [
    # Search Agent
    'SearchAgent', 'CompanyInfo', 'SearchResult', 'QueryGenerator',
    # Scorer
    'HPScorer', 'HPCandidate', 'ScoringConfig',
    # Data Loader
    'DataLoader', 'GoogleSheetsClient', 'SheetConfig',
    # Output Writer
    'OutputWriter', 'OutputColumns', 'WriteResult',
    # Utils
    'URLUtils', 'StringUtils', 'BlacklistChecker', 'ConfigManager',
    # Logger
    'get_logger'
] 