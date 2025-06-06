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
                'search_lang': 'jp',
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
                title = result.get('title', '')
                description = result.get('description', '')
                
                # デバッグ用：文字数確認
                logger.debug(f"検索結果 {i+1}: title={len(title)}文字 desc={len(description)}文字")
                if len(title) > 100:
                    logger.debug(f"長いタイトル: '{title[:100]}...'")
                if len(description) > 200:
                    logger.debug(f"長い説明文: '{description[:200]}...'")
                
                search_result = SearchResult(
                    url=result.get('url', ''),
                    title=title,
                    description=description,
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
    
    @staticmethod
    def generate_location_specific_query(company_info: CompanyInfo) -> str:
        """
        地域特定強化クエリを生成（同名店舗混在対策）
        
        Args:
            company_info: 企業情報
        
        Returns:
            地域特定に特化したクエリ文字列
        """
        # 企業名の前処理
        clean_name = company_info.company_name.strip()
        import re
        clean_name = re.sub(r'【.*?】', '', clean_name).strip()
        
        # 都道府県から主要都市を抽出
        main_city = QueryGenerator._extract_main_city(company_info.prefecture)
        
        # 他地域の主要都市を除外リストに追加
        exclude_cities = QueryGenerator._get_exclude_cities(company_info.prefecture)
        exclude_query = " ".join([f'-{city}' for city in exclude_cities])
        
        # 地域特定強化クエリ
        base_query = f'"{clean_name}" {main_city} {company_info.industry}'
        
        if exclude_query:
            return f"{base_query} {exclude_query}"
        else:
            return base_query
    
    @staticmethod
    def _extract_main_city(prefecture: str) -> str:
        """都道府県から主要都市名を抽出"""
        city_mapping = {
            '東京都': '東京',
            '大阪府': '大阪',
            '愛知県': '名古屋',
            '神奈川県': '横浜',
            '北海道': '札幌',
            '福岡県': '福岡',
            '宮城県': '仙台',
            '広島県': '広島',
            '静岡県': '静岡',
            '新潟県': '新潟',
            '熊本県': '熊本',
            '岡山県': '岡山',
            '鹿児島県': '鹿児島',
            '長野県': '長野',
            '岐阜県': '岐阜',
            '群馬県': '前橋',
            '栃木県': '宇都宮',
            '茨城県': '水戸',
            '三重県': '津',
            '滋賀県': '大津',
            '奈良県': '奈良',
            '和歌山県': '和歌山',
            '京都府': '京都',
            '兵庫県': '神戸',
            '山梨県': '甲府',
            '福井県': '福井',
            '石川県': '金沢',
            '富山県': '富山',
            '長崎県': '長崎',
            '佐賀県': '佐賀',
            '大分県': '大分',
            '宮崎県': '宮崎',
            '沖縄県': '那覇',
            '青森県': '青森',
            '岩手県': '盛岡',
            '秋田県': '秋田',
            '山形県': '山形',
            '福島県': '福島',
            '島根県': '松江',
            '鳥取県': '鳥取',
            '山口県': '山口',
            '愛媛県': '松山',
            '香川県': '高松',
            '高知県': '高知',
            '徳島県': '徳島'
        }
        
        return city_mapping.get(prefecture, prefecture.replace('県', '').replace('府', '').replace('都', ''))
    
    @staticmethod
    def _get_exclude_cities(target_prefecture: str) -> List[str]:
        """対象都道府県以外の主要都市を除外リストとして取得"""
        # 特に混在しやすい主要都市を除外
        major_cities = [
            '東京', '渋谷', '新宿', '銀座', '表参道', '原宿',
            '大阪', '梅田', '心斎橋', '難波',
            '横浜', 'みなとみらい',
            '神戸', '三宮',
            '京都', '河原町',
            '福岡', '天神',
            '札幌', 'すすきの',
            '仙台',
            '広島'
        ]
        
        # 対象都道府県の主要都市は除外リストから除く
        target_city = QueryGenerator._extract_main_city(target_prefecture)
        
        # 愛知県の場合の特別処理
        if target_prefecture == '愛知県':
            # 愛知県内の都市は除外リストから除外
            exclude_cities = [city for city in major_cities 
                            if city not in ['名古屋', '栄', '大須', '金山', '千種']]
        elif target_prefecture == '東京都':
            # 東京都内の地域は除外リストから除外
            exclude_cities = [city for city in major_cities 
                            if city not in ['東京', '渋谷', '新宿', '銀座', '表参道', '原宿']]
        elif target_prefecture == '大阪府':
            # 大阪府内の地域は除外リストから除外
            exclude_cities = [city for city in major_cities 
                            if city not in ['大阪', '梅田', '心斎橋', '難波']]
        else:
            # その他の都道府県：target_cityを除外リストから除く
            exclude_cities = [city for city in major_cities if city != target_city]
        
        return exclude_cities[:8]  # 検索クエリが長くなりすぎないよう上位8都市まで

    @staticmethod
    def generate_industry_specific_query(company_info: CompanyInfo) -> str:
        """
        業種特定強化クエリを生成（関連業種混在対策）
        
        Args:
            company_info: 企業情報
        
        Returns:
            業種特定に特化したクエリ文字列
        """
        # 企業名の前処理
        clean_name = company_info.company_name.strip()
        import re
        clean_name = re.sub(r'【.*?】', '', clean_name).strip()
        
        # 業種別の特定キーワードと除外キーワードを取得
        specific_keywords, exclude_keywords = QueryGenerator._get_industry_keywords(company_info.industry)
        
        # 基本クエリ
        base_query = f'"{clean_name}" {company_info.prefecture}'
        
        # 業種特定キーワード追加
        if specific_keywords:
            keywords_query = " ".join(specific_keywords)
            base_query += f" {keywords_query}"
        
        # 除外キーワード追加
        if exclude_keywords:
            exclude_query = " ".join([f'-{keyword}' for keyword in exclude_keywords])
            base_query += f" {exclude_query}"
        
        return base_query
    
    @staticmethod
    def _get_industry_keywords(industry: str) -> tuple[list[str], list[str]]:
        """
        業種に応じた特定キーワードと除外キーワードを取得
        
        Args:
            industry: 業種名
        
        Returns:
            (特定キーワードのリスト, 除外キーワードのリスト)
        """
        
        # 業種別キーワード定義
        industry_mapping = {
            'ヘアサロン': {
                'include': ['美容室', 'ヘアカット', 'カラー', 'パーマ'],
                'exclude': ['エステ', 'ネイル', 'まつエク', 'アイラッシュ', 'フェイシャル', 'マッサージ']
            },
            '美容院': {
                'include': ['美容室', 'ヘアサロン', 'ヘアカット'],
                'exclude': ['エステ', 'ネイル', 'まつエク', 'スクール', '化粧品', '求人']
            },
            'IT': {
                'include': ['システム開発', 'ソフトウェア', 'アプリ開発', 'WEB制作'],
                'exclude': ['派遣', 'スクール', '求人', '商社', '販売', '代理店']
            },
            '飲食店': {
                'include': ['レストラン', '料理', 'メニュー'],
                'exclude': ['求人', '派遣', 'バイト', '食材', '卸売', '配達']
            },
            '小売': {
                'include': ['店舗', 'ショップ', '販売'],
                'exclude': ['求人', '派遣', '卸売', 'EC', '通販専門']
            },
            'エステ': {
                'include': ['エステティック', 'フェイシャル', 'ボディ', 'リラクゼーション'],
                'exclude': ['ヘアサロン', '美容院', 'ネイル', 'スクール', '商材']
            }
        }
        
        # 完全一致またはキーワード含有で検索
        matched_keywords = None
        
        # 完全一致チェック
        if industry in industry_mapping:
            matched_keywords = industry_mapping[industry]
        else:
            # 部分一致チェック
            for key, value in industry_mapping.items():
                if key in industry or industry in key:
                    matched_keywords = value
                    break
        
        if matched_keywords:
            return matched_keywords['include'], matched_keywords['exclude']
        else:
            # デフォルト（業種名をそのまま使用、一般的な除外ワード）
            return [industry], ['求人', '派遣', 'アルバイト', 'スクール', '販売代理店']

    @staticmethod
    def generate_location_enhanced_query(company_info: CompanyInfo) -> str:
        """
        地域特定強化クエリを生成（シンプル版）
        基本のクエリに戻して、スコアリング側で地域判定
        
        Args:
            company_info: 企業情報
        
        Returns:
            基本的な検索クエリ文字列
        """
        # 企業名の前処理
        clean_name = company_info.company_name.strip()
        import re
        clean_name = re.sub(r'【.*?】', '', clean_name).strip()
        
        # シンプルな基本クエリ：企業名 + 県名 + 業種
        return f'{clean_name} {company_info.prefecture} {company_info.industry}'
    
    @staticmethod
    def _get_area_code(prefecture: str) -> str:
        """
        都道府県から代表的な市外局番を取得
        
        Args:
            prefecture: 都道府県名
        
        Returns:
            市外局番（該当なしの場合は空文字）
        """
        # 主要都道府県の代表市外局番マップ
        area_code_map = {
            '愛知県': '052',      # 名古屋市圏
            '東京都': '03',       # 東京23区
            '大阪府': '06',       # 大阪市
            '神奈川県': '045',    # 横浜市
            '兵庫県': '078',      # 神戸市
            '京都府': '075',      # 京都市
            '福岡県': '092',      # 福岡市
            '北海道': '011',      # 札幌市
            '宮城県': '022',      # 仙台市
            '広島県': '082',      # 広島市
            '静岡県': '054',      # 静岡市
            '千葉県': '043',      # 千葉市
            '埼玉県': '048',      # さいたま市
            '茨城県': '029',      # 水戸市
            '栃木県': '028',      # 宇都宮市
            '群馬県': '027',      # 前橋市
            '新潟県': '025',      # 新潟市
            '長野県': '026',      # 長野市
            '岐阜県': '058',      # 岐阜市
            '三重県': '059',      # 津市
            '滋賀県': '077',      # 大津市
            '奈良県': '0742',     # 奈良市
            '和歌山県': '073',    # 和歌山市
            '岡山県': '086',      # 岡山市
            '山口県': '083',      # 山口市
            '徳島県': '088',      # 徳島市
            '香川県': '087',      # 高松市
            '愛媛県': '089',      # 松山市
            '高知県': '088',      # 高知市
            '佐賀県': '0952',     # 佐賀市
            '長崎県': '095',      # 長崎市
            '熊本県': '096',      # 熊本市
            '大分県': '097',      # 大分市
            '宮崎県': '0985',     # 宮崎市
            '鹿児島県': '099',    # 鹿児島市
            '沖縄県': '098',      # 那覇市
        }
        
        return area_code_map.get(prefecture, '')

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