"""
HP URL スコアリングモジュール
公式HPの信頼度スコアを計算し、最適なURLを判定
"""

import re
import pykakasi
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse
from rapidfuzz import fuzz
from rapidfuzz import utils as fuzz_utils

from .logger_config import get_logger
from .search_agent import SearchResult, CompanyInfo
from .utils import StringUtils, URLUtils

logger = get_logger(__name__)

@dataclass
class HPCandidate:
    """HP候補を表すデータクラス"""
    url: str
    title: str
    description: str
    search_rank: int
    query_pattern: str
    domain_similarity: float
    is_top_page: bool
    total_score: float
    judgment: str  # '自動採用', '要確認', '手動確認'
    score_details: Dict[str, Any]

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
    path_depth_penalty_factor: int = -10 # 現状直接は使われていないが将来用
    domain_jp_penalty: int = -2
    path_keyword_penalty: int = -2
    
    # 判定閾値
    auto_adopt_threshold: int = 9
    needs_review_threshold: int = 6
    similarity_threshold_domain: int = 80

class HPScorer:
    """HP URLスコアリングクラス"""
    
    def __init__(self, config: ScoringConfig, blacklist_domains: Set[str] = None, penalty_paths: List[str] = None):
        self.config = config
        self.blacklist_domains = blacklist_domains if blacklist_domains is not None else set()
        self.penalty_paths = penalty_paths if penalty_paths is not None else []
        self.string_utils = StringUtils()
        self.url_utils = URLUtils()
        
        # pykakasi コンバータを初期化してキャッシュ（v2.0+ New API）
        self._kks = pykakasi.kakasi()
    
    def _romanize(self, text: str) -> str:
        """
        日本語をローマ字へ変換（pykakasi v2.0+ New API）
        
        Args:
            text: 変換対象の日本語文字列
        
        Returns:
            ローマ字変換された文字列
        """
        try:
            if not text:
                return ""
            
            # v2.0+ New API: convertメソッドで辞書リストを取得
            result = self._kks.convert(text)
            romanized = ''.join([item['hepburn'] for item in result])
            
            # 小文字に統一し、余分な空白を除去
            return romanized.lower().strip()
            
        except Exception as e:
            logger.warning(f"ローマ字変換エラー: text='{text}' - {e}")
            return ""
    
    def _enhanced_clean_company_name(self, company_name: str) -> str:
        """
        企業名の強化された正規化処理
        法人接尾語を除去しつつ、日本語本体は保持
        
        Args:
            company_name: 原企業名
        
        Returns:
            正規化された企業名
        """
        if not company_name:
            return ""
        
        # 基本の正規化（【】除去、空白正規化）
        cleaned = self.string_utils.clean_company_name(company_name)
        
        # 法人接尾語を除去
        cleaned = self.string_utils.remove_legal_suffixes(cleaned)
        
        # 全角英数字を半角に変換
        import unicodedata
        cleaned = unicodedata.normalize('NFKC', cleaned)
        
        # 記号を除去（ただし、日本語文字は保持）
        # 英数字、ひらがな、カタカナ、漢字、空白のみ残す
        cleaned = re.sub(r'[^\w\sぁ-んァ-ヴー一-龯]', '', cleaned)
        
        # 余分な空白を除去
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _calculate_domain_similarity(self, company_name: str, url: str) -> float:
        """
        ドメイン名と企業名の類似度計算（強化版）
        日本語→ローマ字変換と複数アルゴリズムを使用
        """
        try:
            # 企業名の正規化
            cleaned_name = self._enhanced_clean_company_name(company_name)
            
            # ドメイン名の取得
            domain = self.url_utils.get_domain(url)
            domain_without_tld = domain.split('.')[0]
            
            # 比較候補を準備
            candidates = []
            
            # 1. 原企業名（正規化済み）
            if cleaned_name:
                candidates.append(cleaned_name)
            
            # 2. ローマ字変換版（日本語がある場合のみ）
            if re.search(r'[あ-んア-ヶー一-龯]', cleaned_name):
                romanized_name = self._romanize(cleaned_name)
                if romanized_name and romanized_name != cleaned_name.lower():
                    candidates.append(romanized_name)
            
            # 3. カタカナ部分のみ抽出してローマ字変換
            katakana_only = self.string_utils.extract_katakana(company_name)
            if katakana_only:
                romanized_katakana = self._romanize(katakana_only)
                if romanized_katakana and romanized_katakana not in candidates:
                    candidates.append(romanized_katakana)
                    
            # 4. 英語の場合は小文字化した版も追加
            if re.search(r'[a-zA-Z]', cleaned_name):
                lower_name = cleaned_name.lower()
                if lower_name not in candidates:
                    candidates.append(lower_name)
            
            # 候補が空の場合は0を返す
            if not candidates:
                logger.debug(f"[SIM] 比較候補なし: name='{company_name}' -> cleaned='{cleaned_name}'")
                return 0.0
            
            # 各候補でスコア計算
            best_score = 0.0
            best_candidate = ""
            scores_log = []
            
            for candidate in candidates:
                if not candidate:
                    continue
                
                # 複数のアルゴリズムを試して最高スコアを取得
                wratio_score = fuzz.WRatio(
                    candidate, domain_without_tld,
                    processor=fuzz_utils.default_process
                )
                
                token_sort_score = fuzz.token_sort_ratio(
                    candidate, domain_without_tld,
                    processor=fuzz_utils.default_process
                )
                
                # より高いスコアを採用
                score = max(wratio_score, token_sort_score)
                scores_log.append(f"{candidate}→{score}(W:{wratio_score}/T:{token_sort_score})")
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            # デバッグログ出力
            logger.debug(f"[SIM] name='{company_name}' domain='{domain_without_tld}' "
                        f"best={best_score} via '{best_candidate}' scores=[{', '.join(scores_log)}]")
            
            return float(best_score)
            
        except Exception as e:
            logger.warning(f"ドメイン類似度計算エラー: Name='{company_name}', URL='{url}' - {e}", exc_info=True)
            return 0.0
    
    def calculate_score(self, search_result: SearchResult, company: CompanyInfo, query_pattern: str) -> Optional[HPCandidate]:
        """
        単一の検索結果をスコアリング
        
        Args:
            search_result: 検索結果
            company: 企業情報
            query_pattern: 使用されたクエリパターン
        
        Returns:
            HPCandidate または None（ブラックリスト等で除外の場合）
        """
        try:
            if self._is_blacklisted_domain(search_result.url):
                logger.debug(f"ブラックリストドメイン除外: {search_result.url}")
                return None
            
            score_details = {}
            total_score = 0
            
            is_top_page = self._is_top_page(search_result.url)
            if is_top_page:
                score_details["top_page"] = self.config.top_page_bonus
                total_score += self.config.top_page_bonus
            else:
                score_details["top_page"] = 0
            
            domain_similarity = self._calculate_domain_similarity(
                company.company_name, search_result.url
            )
            
            # ドメイン完全一致の判定をより厳密に（類似度95以上など）
            if domain_similarity >= 95: 
                domain_score = self.config.domain_exact_match
            elif domain_similarity >= self.config.similarity_threshold_domain:
                domain_score = self.config.domain_similar_match
            else:
                domain_score = 0
            score_details["domain_similarity_score"] = domain_score
            total_score += domain_score
            
            tld_score = self._get_tld_score(search_result.url)
            score_details["tld_score"] = tld_score
            total_score += tld_score
            
            if self._has_official_keywords(search_result.title):
                official_score = self.config.official_keyword_bonus
                score_details["official_keyword"] = official_score
                total_score += official_score
            else:
                score_details["official_keyword"] = 0
            
            rank_bonus = self._get_search_rank_bonus(search_result.rank)
            score_details["search_rank"] = rank_bonus
            total_score += rank_bonus
            
            path_penalty = self._get_path_penalty(search_result.url)
            score_details["path_penalty"] = path_penalty
            total_score += path_penalty
            
            judgment = self._determine_judgment(total_score)
            
            # 詳細ログ出力
            logger.debug(f"[SCORE] {company.company_name} -> {search_result.url} "
                        f"total={total_score} judgment={judgment} "
                        f"details={score_details}")
            
            return HPCandidate(
                url=search_result.url,
                title=search_result.title,
                description=search_result.description,
                search_rank=search_result.rank,
                query_pattern=query_pattern,
                domain_similarity=domain_similarity, # 元の類似度(0-100)を格納
                is_top_page=is_top_page,
                total_score=total_score,
                judgment=judgment,
                score_details=score_details
            )
            
        except Exception as e:
            logger.error(f"スコア計算エラー: {search_result.url}, 会社名: {company.company_name} - {e}", exc_info=True)
            return None
    
    def score_multiple_candidates(self, search_results: Dict[str, List[SearchResult]], 
                                company: CompanyInfo) -> List[HPCandidate]:
        all_candidates = []
        for query_pattern, results in search_results.items():
            for result in results:
                candidate = self.calculate_score(result, company, query_pattern)
                if candidate:
                    all_candidates.append(candidate)
        all_candidates.sort(key=lambda x: x.total_score, reverse=True)
        return all_candidates
    
    def get_best_candidate(self, search_results: Dict[str, List[SearchResult]], 
                         company: CompanyInfo) -> Optional[HPCandidate]:
        candidates = self.score_multiple_candidates(search_results, company)
        if not candidates:
            return None
        return candidates[0]
    
    def _is_blacklisted_domain(self, url: str) -> bool:
        try:
            domain = self.url_utils.get_domain(url) # get_domainは既にwww除去と小文字化を行う
            return domain in self.blacklist_domains
        except Exception as e:
            logger.warning(f"ブラックリストドメイン判定エラー: {url} - {e}")
            return False # エラー時は安全側に倒し、ブラックリストではないとする
    
    def _is_top_page(self, url: str) -> bool:
        try:
            path_depth = self.url_utils.get_path_depth(url)
            return path_depth == 0
        except Exception as e:
            logger.warning(f"トップページ判定エラー: {url} - {e}")
            return False # エラー時はトップページではないとする
    
    def _has_official_keywords(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        official_keywords = ['公式', 'official', 'オフィシャル', '正式']
        return any(keyword in text_lower for keyword in official_keywords)
    
    def _get_tld_score(self, url: str) -> int:
        try:
            domain = self.url_utils.get_domain(url) # 既に小文字化されている
            if domain.endswith('.co.jp'):
                return self.config.tld_co_jp
            elif domain.endswith(('.com', '.net')):
                return self.config.tld_com_net
            elif domain.endswith('.jp'):
                return self.config.domain_jp_penalty
            else:
                return 0
        except Exception as e:
            logger.warning(f"TLDスコア計算エラー: {url} - {e}")
            return 0
    
    def _get_search_rank_bonus(self, rank: int) -> int:
        if 1 <= rank <= 3:
            return self.config.search_rank_bonus
        return 0
    
    def _get_path_penalty(self, url: str) -> int:
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            for penalty_keyword in self.penalty_paths:
                if penalty_keyword in path:
                    return self.config.path_keyword_penalty
            return 0
        except Exception as e:
            logger.warning(f"パスペナルティ計算エラー: {url} - {e}")
            return 0
    
    def _determine_judgment(self, total_score: float) -> str:
        if total_score >= self.config.auto_adopt_threshold:
            return "自動採用"
        elif total_score >= self.config.needs_review_threshold:
            return "要確認"
        else:
            return "手動確認"

def create_scorer_from_config(config: Dict[str, Any], blacklist_checker) -> HPScorer:
    """設定からHPScorerを作成するファクトリー関数"""
    try:
        # スコアリング設定の取得
        scoring_logic = config.get('scoring_logic', {})
        weights = scoring_logic.get('weights', {})
        
        scoring_config = ScoringConfig(
            top_page_bonus=weights.get('top_page', 5),
            domain_exact_match=weights.get('domain_exact_match', 5),
            domain_similar_match=weights.get('domain_similarity', 3),
            tld_co_jp=weights.get('tld_co_jp', 3),
            tld_com_net=weights.get('tld_com_net', 1),
            official_keyword_bonus=weights.get('official_keyword', 2),
            search_rank_bonus=weights.get('search_rank', 3),
            domain_jp_penalty=weights.get('domain_jp_penalty', -2),
            path_keyword_penalty=weights.get('path_penalty', -2),
            auto_adopt_threshold=scoring_logic.get('auto_adopt_threshold', 9),
            needs_review_threshold=scoring_logic.get('needs_review_threshold', 6),
            similarity_threshold_domain=scoring_logic.get('similarity_threshold_domain', 80)
        )
        
        # ブラックリストドメインの取得
        blacklist_domains = blacklist_checker.get_blacklist_domains() if blacklist_checker else set()
        
        # ペナルティパスの取得
        penalty_paths = scoring_logic.get('penalty_paths', [
            'blog', 'news', 'recruit', 'contact', 'about'
        ])
        
        return HPScorer(
            config=scoring_config,
            blacklist_domains=blacklist_domains,
            penalty_paths=penalty_paths
        )
        
    except Exception as e:
        logger.error(f"HPScorer作成エラー: {e}")
        # デフォルト設定でフォールバック
        return HPScorer(
            config=ScoringConfig(),
            blacklist_domains=set(),
            penalty_paths=[]
        ) 