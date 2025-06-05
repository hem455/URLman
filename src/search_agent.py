"""
Brave Search API連携モジュール
フェーズ1: 基本的な検索機能
フェーズ3: 非同期処理、リトライ、レートリミット制御
"""

import requests
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .logger_config import get_logger
from .utils import URLUtils

logger = get_logger(__name__)

@dataclass
class SearchResult:
    """検索結果を表すデータクラス"""
    url: str
    title: str
    description: str
    rank: int  # 検索結果での順位（1始まり）

@dataclass
class CompanyInfo:
    """企業情報を表すデータクラス"""
    id: str
    company_name: str
    prefecture: str
    industry: str

class BraveSearchClient:
    """Brave Search API クライアント"""
    
    def __init__(self, api_key: str, results_per_query: int = 10):
        self.api_key = api_key
        self.results_per_query = results_per_query
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        self.session = requests.Session()
        
        # APIキーをヘッダーに設定
        self.session.headers.update({
            'X-Subscription-Token': api_key,
            'Accept': 'application/json'
        })
    
    def search(self, query: str, **kwargs) -> List[SearchResult]:
        """
        検索クエリを実行してSearchResultのリストを返す
        
        Args:
            query: 検索クエリ文字列
            **kwargs: 追加のAPIパラメータ
        
        Returns:
            SearchResultのリスト
        """
        try:
            logger.info(f"Brave Search実行: {query}")
            
            # APIパラメータの設定
            params = {
                'q': query,
                'count': self.results_per_query,
                'search_lang': 'ja',
                'country': 'JP',
                **kwargs
            }
            
            # APIリクエスト実行
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # 検索結果を解析
            results = self._parse_search_results(data)
            
            logger.info(f"検索結果取得: {len(results)}件")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Brave Search APIエラー: {e}")
            return []
        except Exception as e:
            logger.error(f"予期せぬエラー: {e}")
            return []
    
    def _parse_search_results(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        Brave Search APIのレスポンスをSearchResultのリストに変換
        
        Args:
            data: Brave Search APIのレスポンスデータ
        
        Returns:
            SearchResultのリスト
        """
        results = []
        
        # web.resultsキーから検索結果を取得
        web_results = data.get('web', {}).get('results', [])
        
        for i, result in enumerate(web_results):
            try:
                search_result = SearchResult(
                    url=result.get('url', ''),
                    title=result.get('title', ''),
                    description=result.get('description', ''),
                    rank=i + 1
                )
                
                # URLが有効かチェック
                if search_result.url and search_result.url.startswith(('http://', 'https://')):
                    results.append(search_result)
                    
            except Exception as e:
                logger.warning(f"検索結果の解析エラー (インデックス {i}): {e}")
                continue
        
        return results

class QueryGenerator:
    """検索クエリ生成クラス"""
    
    @staticmethod
    def generate_phase1_queries(company_info: CompanyInfo) -> Dict[str, str]:
        """
        フェーズ1用の3つのクエリパターンを生成
        
        Args:
            company_info: 企業情報
        
        Returns:
            クエリ名をキー、クエリ文字列を値とする辞書
        """
        # 企業名の前処理
        clean_name = company_info.company_name.strip()
        
        # 【】内の読み仮名を除去
        import re
        clean_name = re.sub(r'【.*?】', '', clean_name).strip()
        
        queries = {
            'pattern_a': f"{clean_name} {company_info.industry} {company_info.prefecture}",
            'pattern_b': f'"{clean_name}" {company_info.prefecture} 公式サイト',
            'pattern_c': f'"{clean_name}" {company_info.industry} 公式 site:co.jp OR site:com'
        }
        
        return queries
    
    @staticmethod
    def generate_custom_query(template: str, company_info: CompanyInfo) -> str:
        """
        カスタムテンプレートからクエリを生成
        
        Args:
            template: クエリテンプレート（例: "{company_name} {industry}"）
            company_info: 企業情報
        
        Returns:
            生成されたクエリ文字列
        """
        # 企業名の前処理
        clean_name = company_info.company_name.strip()
        import re
        clean_name = re.sub(r'【.*?】', '', clean_name).strip()
        
        return template.format(
            company_name=clean_name,
            industry=company_info.industry,
            prefecture=company_info.prefecture
        )

class SearchAgent:
    """検索エージェント - 複数クエリの実行と結果統合"""
    
    def __init__(self, brave_client: BraveSearchClient):
        self.brave_client = brave_client
    
    def search_company(self, company_info: CompanyInfo) -> Dict[str, List[SearchResult]]:
        """
        企業に対してフェーズ1の3つのクエリを実行
        
        Args:
            company_info: 企業情報
        
        Returns:
            クエリ名をキー、SearchResultのリストを値とする辞書
        """
        logger.info(f"企業検索開始: {company_info.company_name} (ID: {company_info.id})")
        
        # クエリ生成
        queries = QueryGenerator.generate_phase1_queries(company_info)
        
        results = {}
        
        for query_name, query_text in queries.items():
            logger.info(f"クエリ実行 [{query_name}]: {query_text}")
            
            # 検索実行
            search_results = self.brave_client.search(query_text)
            results[query_name] = search_results
            
            # APIレートリミット対策（簡易版）
            time.sleep(1.2)  # 1.2秒間隔
            
            logger.info(f"クエリ [{query_name}] 完了: {len(search_results)}件取得")
        
        logger.info(f"企業検索完了: {company_info.company_name}")
        return results
    
    def search_with_custom_queries(self, company_info: CompanyInfo, 
                                 query_templates: List[str]) -> Dict[str, List[SearchResult]]:
        """
        カスタムクエリテンプレートで検索実行
        
        Args:
            company_info: 企業情報
            query_templates: クエリテンプレートのリスト
        
        Returns:
            クエリ番号をキー、SearchResultのリストを値とする辞書
        """
        results = {}
        
        for i, template in enumerate(query_templates):
            query_name = f"custom_{i+1}"
            query_text = QueryGenerator.generate_custom_query(template, company_info)
            
            logger.info(f"カスタムクエリ実行 [{query_name}]: {query_text}")
            
            search_results = self.brave_client.search(query_text)
            results[query_name] = search_results
            
            # レートリミット対策
            time.sleep(1.2)
        
        return results 