"""
HP URL スコアリングモジュール
公式HPの信頼度スコアを計算し、最適なURLを判定
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from rapidfuzz import fuzz, utils
import asyncio
import aiohttp
from bs4 import BeautifulSoup

from .logger_config import get_logger
from .search_agent import SearchResult, CompanyInfo
from .utils import URLUtils, StringUtils, BlacklistChecker

logger = get_logger(__name__)

@dataclass
class ScoringConfig:
    """スコアリング設定"""
    # 重み付け設定
    top_page_bonus: int = 5
    domain_exact_match: int = 5
    domain_similar_match: int = 3
    tld_co_jp: int = 3
    tld_com_net: int = 1
    official_keyword_bonus: int = 2
    search_rank_bonus: int = 3
    path_depth_penalty_factor: int = -10
    domain_jp_penalty: int = -2
    path_keyword_penalty: int = -2
    
    # 判定閾値
    auto_adopt_threshold: int = 9
    needs_review_threshold: int = 6
    similarity_threshold_domain: int = 80

@dataclass
class URLScore:
    """URL評価結果"""
    url: str
    total_score: int
    component_scores: Dict[str, int]
    judgment: str  # '自動採用', '要確認', '手動確認'
    is_top_page: bool
    domain_similarity: float
    details: Dict[str, Any]

class HPScorer:
    """HP URLスコアリングクラス"""
    
    def __init__(self, config: ScoringConfig, blacklist_checker: BlacklistChecker):
        self.config = config
        self.blacklist_checker = blacklist_checker
        self.url_utils = URLUtils()
        self.string_utils = StringUtils()
    
    async def score_search_results(self, 
                                 company: CompanyInfo,
                                 search_results: List[SearchResult],
                                 session: aiohttp.ClientSession) -> List[URLScore]:
        """
        検索結果リストをスコアリング
        
        Args:
            company: 企業情報
            search_results: 検索結果リスト
            session: HTTP セッション
        
        Returns:
            スコア付きURL結果リスト（降順ソート）
        """
        try:
            logger.debug(f"[{company.id}] スコアリング開始: {len(search_results)}件")
            
            scored_urls = []
            
            for i, result in enumerate(search_results):
                try:
                    # ブラックリストチェック
                    if self.blacklist_checker.is_domain_blacklisted(result.url):
                        logger.debug(f"[{company.id}] ブラックリストドメイン除外: {result.url}")
                        continue
                    
                    # URLスコアリング実行
                    url_score = await self._score_single_url(
                        company, result, i + 1, session
                    )
                    
                    if url_score:
                        scored_urls.append(url_score)
                        
                except Exception as e:
                    logger.warning(f"[{company.id}] URL個別スコアリングエラー: {result.url} - {e}")
                    continue
            
            # スコア順にソート
            scored_urls.sort(key=lambda x: x.total_score, reverse=True)
            
            logger.info(f"[{company.id}] スコアリング完了: {len(scored_urls)}件")
            return scored_urls
            
        except Exception as e:
            logger.error(f"[{company.id}] スコアリング処理エラー: {e}")
            return []
    
    async def _score_single_url(self, 
                              company: CompanyInfo,
                              result: SearchResult,
                              rank: int,
                              session: aiohttp.ClientSession) -> Optional[URLScore]:
        """
        単一URLのスコアリング
        
        Args:
            company: 企業情報
            result: 検索結果
            rank: 検索順位
            session: HTTP セッション
        
        Returns:
            URLScore または None
        """
        try:
            component_scores = {}
            details = {
                'rank': rank,
                'title': result.title,
                'description': result.description
            }
            
            # URLパース
            parsed_url = urlparse(result.url)
            domain = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            
            # 1. トップページ判定
            is_top_page = self._is_top_page(result.url)
            if is_top_page:
                component_scores['top_page_bonus'] = self.config.top_page_bonus
            else:
                # パス深度ペナルティ
                path_depth = self._calculate_path_depth(path)
                if path_depth > 0:
                    penalty = min(path_depth * self.config.path_depth_penalty_factor, -20)
                    component_scores['path_depth_penalty'] = penalty
            
            # 2. ドメイン類似度評価
            domain_similarity = self._calculate_domain_similarity(company.company_name, domain)
            if domain_similarity >= 95:  # 完全一致に近い
                component_scores['domain_exact_match'] = self.config.domain_exact_match
            elif domain_similarity >= self.config.similarity_threshold_domain:
                component_scores['domain_similar_match'] = self.config.domain_similar_match
            
            details['domain_similarity'] = domain_similarity
            
            # 3. TLD評価
            tld_score = self._evaluate_tld(domain)
            if tld_score != 0:
                component_scores['tld_bonus'] = tld_score
            
            # 4. パスキーワードペナルティ
            path_penalty = self.blacklist_checker.get_path_penalty_score(result.url)
            if path_penalty < 0:
                component_scores['path_keyword_penalty'] = path_penalty
            
            # 5. 検索順位ボーナス
            if rank <= 3:
                component_scores['search_rank_bonus'] = self.config.search_rank_bonus
            
            # 6. HTMLコンテンツ解析（公式キーワード）
            try:
                html_content = await self._fetch_html_content(result.url, session)
                if html_content:
                    official_bonus = self._analyze_html_content(html_content, company.company_name)
                    if official_bonus > 0:
                        component_scores['official_keyword_bonus'] = official_bonus
                    details['html_analyzed'] = True
                else:
                    details['html_analyzed'] = False
            except Exception as e:
                logger.debug(f"[{company.id}] HTML解析失敗: {result.url} - {e}")
                details['html_analyzed'] = False
            
            # 総合スコア計算
            total_score = sum(component_scores.values())
            
            # 判定
            judgment = self._determine_judgment(total_score)
            
            url_score = URLScore(
                url=result.url,
                total_score=total_score,
                component_scores=component_scores,
                judgment=judgment,
                is_top_page=is_top_page,
                domain_similarity=domain_similarity,
                details=details
            )
            
            logger.debug(f"[{company.id}] URLスコア: {result.url} = {total_score}点 ({judgment})")
            return url_score
            
        except Exception as e:
            logger.warning(f"[{company.id}] URLスコアリングエラー: {result.url} - {e}")
            return None
    
    def _is_top_page(self, url: str) -> bool:
        """
        トップページ判定
        
        Args:
            url: 判定対象URL
        
        Returns:
            トップページの場合True
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            # パスが空またはindex系ファイル名
            if not path:
                return True
            
            # index系ファイル名チェック
            index_files = {
                'index.html', 'index.htm', 'index.php', 'index.asp', 'index.aspx',
                'default.html', 'default.htm', 'default.asp', 'default.aspx',
                'home.html', 'home.htm'
            }
            
            if path.lower() in index_files:
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"トップページ判定エラー: {url} - {e}")
            return False
    
    def _calculate_path_depth(self, path: str) -> int:
        """
        パス深度計算
        
        Args:
            path: URLパス
        
        Returns:
            パス深度
        """
        if not path or path == '/':
            return 0
        
        # 先頭と末尾のスラッシュを除去してスプリット
        cleaned_path = path.strip('/')
        if not cleaned_path:
            return 0
        
        return len(cleaned_path.split('/'))
    
    def _calculate_domain_similarity(self, company_name: str, domain: str) -> float:
        """
        企業名とドメインの類似度計算
        
        Args:
            company_name: 企業名
            domain: ドメイン名
        
        Returns:
            類似度（0-100）
        """
        try:
            # 企業名の前処理
            processed_company = self.string_utils.normalize_company_name(company_name)
            
            # ドメインの前処理（www除去、TLD除去）
            processed_domain = domain.replace('www.', '')
            if '.' in processed_domain:
                processed_domain = processed_domain.split('.')[0]
            
            # ハイフンやアンダースコアをスペースに置換
            processed_domain = processed_domain.replace('-', ' ').replace('_', ' ')
            
            # rapidfuzzで類似度計算
            similarity = fuzz.token_set_ratio(
                processed_company, 
                processed_domain, 
                processor=utils.default_process
            )
            
            return float(similarity)
            
        except Exception as e:
            logger.debug(f"類似度計算エラー: {company_name} vs {domain} - {e}")
            return 0.0
    
    def _evaluate_tld(self, domain: str) -> int:
        """
        TLD評価
        
        Args:
            domain: ドメイン名
        
        Returns:
            TLDスコア
        """
        try:
            if domain.endswith('.co.jp'):
                return self.config.tld_co_jp
            elif domain.endswith(('.com', '.net', '.org')):
                return self.config.tld_com_net
            elif domain.endswith('.jp'):
                return self.config.domain_jp_penalty  # .jpのみは減点
            else:
                return 0
                
        except Exception as e:
            logger.debug(f"TLD評価エラー: {domain} - {e}")
            return 0
    
    async def _fetch_html_content(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        HTMLコンテンツ取得
        
        Args:
            url: 対象URL
            session: HTTPセッション
        
        Returns:
            HTMLコンテンツまたはNone
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    content = await response.text(encoding='utf-8', errors='replace')
                    return content
                else:
                    logger.debug(f"HTTP {response.status}: {url}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.debug(f"タイムアウト: {url}")
            return None
        except Exception as e:
            logger.debug(f"HTML取得エラー: {url} - {e}")
            return None
    
    def _analyze_html_content(self, html_content: str, company_name: str) -> int:
        """
        HTMLコンテンツ解析（公式キーワード検出）
        
        Args:
            html_content: HTMLコンテンツ
            company_name: 企業名
        
        Returns:
            公式キーワードボーナス点
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # title, meta description, h1タグのテキストを結合
            text_content = ""
            
            # titleタグ
            if soup.title and soup.title.string:
                text_content += soup.title.string + " "
            
            # meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                text_content += meta_desc.get('content') + " "
            
            # h1タグ
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags:
                if h1.get_text():
                    text_content += h1.get_text() + " "
            
            # 公式キーワードチェック
            official_keywords = ['公式', 'オフィシャル', 'official', '正規', 'ホームページ', 'HOME']
            
            text_lower = text_content.lower()
            for keyword in official_keywords:
                if keyword.lower() in text_lower:
                    logger.debug(f"公式キーワード検出: {keyword}")
                    return self.config.official_keyword_bonus
            
            return 0
            
        except Exception as e:
            logger.debug(f"HTML解析エラー: {e}")
            return 0
    
    def _determine_judgment(self, total_score: int) -> str:
        """
        総合判定
        
        Args:
            total_score: 総合スコア
        
        Returns:
            判定結果
        """
        if total_score >= self.config.auto_adopt_threshold:
            return '自動採用'
        elif total_score >= self.config.needs_review_threshold:
            return '要確認'
        else:
            return '手動確認'
    
    def get_best_url(self, scored_urls: List[URLScore]) -> Optional[URLScore]:
        """
        最高スコアのURLを取得
        
        Args:
            scored_urls: スコア付きURLリスト
        
        Returns:
            最高スコアのURLScore または None
        """
        if not scored_urls:
            return None
        
        # 既にスコア順でソートされている前提
        return scored_urls[0]
    
    def filter_by_judgment(self, scored_urls: List[URLScore], judgment: str) -> List[URLScore]:
        """
        判定結果でフィルタリング
        
        Args:
            scored_urls: スコア付きURLリスト
            judgment: フィルタ対象の判定結果
        
        Returns:
            フィルタされたURLリスト
        """
        return [url_score for url_score in scored_urls if url_score.judgment == judgment]

def create_scorer_from_config(config: Dict[str, Any], blacklist_checker: BlacklistChecker) -> HPScorer:
    """
    設定辞書からHPScorerインスタンスを作成
    
    Args:
        config: 設定辞書（scoring_logicセクション）
        blacklist_checker: ブラックリストチェッカー
    
    Returns:
        HPScorerインスタンス
    """
    scoring_config_dict = config.get('scoring_logic', {})
    
    # 重み付け設定
    weights = scoring_config_dict.get('weights', {})
    thresholds = scoring_config_dict.get('thresholds', {})
    
    scoring_config = ScoringConfig(
        top_page_bonus=weights.get('top_page_bonus', 5),
        domain_exact_match=weights.get('domain_exact_match', 5),
        domain_similar_match=weights.get('domain_similar_match', 3),
        tld_co_jp=weights.get('tld_co_jp', 3),
        tld_com_net=weights.get('tld_com_net', 1),
        official_keyword_bonus=weights.get('official_keyword_bonus', 2),
        search_rank_bonus=weights.get('search_rank_bonus', 3),
        path_depth_penalty_factor=weights.get('path_depth_penalty_factor', -10),
        domain_jp_penalty=weights.get('domain_jp_penalty', -2),
        path_keyword_penalty=weights.get('path_keyword_penalty', -2),
        auto_adopt_threshold=thresholds.get('auto_adopt', 9),
        needs_review_threshold=thresholds.get('needs_review', 6),
        similarity_threshold_domain=scoring_config_dict.get('similarity_threshold_domain', 80)
    )
    
    return HPScorer(scoring_config, blacklist_checker) 