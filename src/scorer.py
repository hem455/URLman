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
        ドメイン名と企業名の類似度計算（語幹スプリット強化版）
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
            
            # 🚀 5. 語幹スプリット強化（NEW）
            # ドメインを単語に分割してそれぞれと比較
            domain_tokens = self._split_domain_tokens(domain_without_tld)
            
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
                
                # 従来の全体比較
                wratio_score = fuzz.WRatio(
                    candidate, domain_without_tld,
                    processor=fuzz_utils.default_process
                )
                
                token_sort_score = fuzz.token_sort_ratio(
                    candidate, domain_without_tld,
                    processor=fuzz_utils.default_process
                )
                
                # 🚀 語幹スプリット比較（NEW）
                split_score = self._calculate_token_split_similarity(candidate, domain_tokens)
                
                # 最高スコアを採用
                score = max(wratio_score, token_sort_score, split_score)
                scores_log.append(f"{candidate}→{score}(W:{wratio_score}/T:{token_sort_score}/S:{split_score})")
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            # デバッグログ出力
            logger.debug(f"[SIM] name='{company_name}' domain='{domain_without_tld}' tokens={domain_tokens} "
                        f"best={best_score} via '{best_candidate}' scores=[{', '.join(scores_log)}]")
            
            return float(best_score)
            
        except Exception as e:
            logger.warning(f"ドメイン類似度計算エラー: Name='{company_name}', URL='{url}' - {e}", exc_info=True)
            return 0.0
    
    def _split_domain_tokens(self, domain: str) -> List[str]:
        """
        ドメインを意味のある単語トークンに分割
        
        Args:
            domain: ドメイン名（TLD除去済み）
        
        Returns:
            分割されたトークンのリスト
        """
        try:
            # 区切り文字での分割
            tokens = re.split(r'[-_\.]', domain.lower())
            
            # 空文字列と短すぎるトークンを除去
            tokens = [token for token in tokens if token and len(token) >= 2]
            
            return tokens
            
        except Exception as e:
            logger.warning(f"ドメイントークン分割エラー: domain='{domain}' - {e}")
            return [domain.lower()]
    
    def _calculate_token_split_similarity(self, candidate: str, domain_tokens: List[str]) -> float:
        """
        語幹スプリット類似度計算
        
        Args:
            candidate: 比較対象の企業名候補
            domain_tokens: ドメインのトークンリスト
        
        Returns:
            最高類似度スコア
        """
        try:
            if not domain_tokens or not candidate:
                return 0.0
            
            # 候補文字列も分割
            candidate_tokens = re.split(r'[\s\-_]', candidate.lower())
            candidate_tokens = [token for token in candidate_tokens if token and len(token) >= 2]
            
            if not candidate_tokens:
                candidate_tokens = [candidate.lower()]
            
            max_score = 0.0
            
            # 各ドメイントークンと各候補トークンの最高類似度を計算
            for domain_token in domain_tokens:
                for candidate_token in candidate_tokens:
                    # 完全一致ボーナス
                    if domain_token == candidate_token:
                        max_score = max(max_score, 100.0)
                        continue
                    
                    # fuzzy マッチング
                    token_score = fuzz.ratio(candidate_token, domain_token)
                    max_score = max(max_score, token_score)
            
            # 全体との比較も実施
            full_domain = ''.join(domain_tokens)
            full_candidate = ''.join(candidate_tokens)
            full_score = fuzz.ratio(full_candidate, full_domain)
            max_score = max(max_score, full_score)
            
            return float(max_score)
            
        except Exception as e:
            logger.warning(f"トークンスプリット類似度計算エラー: candidate='{candidate}' tokens={domain_tokens} - {e}")
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
            
            # 🚀 死活確認（NEW）
            if not self._is_reachable(search_result.url):
                logger.debug(f"死活確認失敗、減点対象: {search_result.url}")
                # 完全除外ではなく大幅減点で対応
            
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
            
            # 🎯 地域特定強化スコアリング
            locality_score = self._calculate_locality_score(search_result, company)
            score_details["locality"] = locality_score
            total_score += locality_score
            
            # 🚫 ポータルドメインペナルティ（強化版）
            portal_penalty = self._get_enhanced_portal_penalty(search_result.url)
            score_details["portal_penalty"] = portal_penalty
            total_score += portal_penalty
            
            # 🚀 死活確認ペナルティ（NEW）
            reachability_penalty = 0
            if not self._is_reachable(search_result.url):
                reachability_penalty = -6  # 大幅減点
                logger.debug(f"死活確認失敗による減点: {search_result.url}")
            score_details["reachability_penalty"] = reachability_penalty
            total_score += reachability_penalty
            
            # 🚀 地域ミスマッチ強化ペナルティ（NEW）
            # 他県で検出された場合、さらに追加ペナルティ
            mismatch_penalty = self._calculate_geographic_mismatch_penalty(search_result, company)
            score_details["geographic_mismatch_penalty"] = mismatch_penalty
            total_score += mismatch_penalty
            
            # 🔥 汎用語ペナルティ（NEW）
            # hair・groupなど汎用語のみの一致は減点
            generic_penalty = self._calculate_generic_word_penalty(company.company_name, search_result.url)
            score_details["generic_word_penalty"] = generic_penalty
            total_score += generic_penalty
            
            # 🔥 HeadMatchボーナス（NEW）- タイトルのみ
            # <title>タグとの一致判定
            head_match_bonus = self._calculate_head_match_bonus(company.company_name, search_result)
            score_details["head_match_bonus"] = head_match_bonus
            total_score += head_match_bonus
            
            judgment = self._determine_judgment(total_score)
            
            # 詳細ログ出力（INFOレベルに変更）
            logger.info(f"[SCORE] {company.company_name} -> {search_result.url[:50]}... "
                       f"total={total_score} judgment={judgment} "
                       f"top={score_details.get('top_page', 0)} domain={score_details.get('domain_similarity_score', 0)} "
                       f"head={score_details.get('head_match_bonus', 0)} portal={score_details.get('portal_penalty', 0)} "
                       f"rank={score_details.get('search_rank', 0)}")
            
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
    
    def _calculate_locality_score(self, search_result: SearchResult, company: CompanyInfo) -> int:
        """
        地域特定スコア計算（3段階ロジック統合版）
        
        Args:
            search_result: 検索結果
            company: 企業情報
        
        Returns:
            地域スコア
        """

        try:
            # タイトル + 説明文を結合
            text = f"{search_result.title} {search_result.description}".lower()
            score = 0
            
            # 都道府県から市外局番を取得
            area_code = self._get_area_code_for_scoring(company.prefecture)
            
            # ① 県名・市名がテキストに含まれる（+2点）
            prefecture_clean = company.prefecture.replace('県', '').replace('府', '').replace('都', '').replace('道', '')
            if prefecture_clean.lower() in text or company.prefecture.lower() in text:
                score += 2
            
            # ② 市外局番一致（+3点）
            if area_code:
                import re
                # 市外局番パターン（ハイフンありなし両対応）
                pattern = rf'{area_code}[-\s]?[0-9]{{7,8}}'
                if re.search(pattern, text):
                    score += 3
            
            # ③ 地域以外の都道府県ミスマッチペナルティ（-10点）
            other_prefecture_penalty = self._check_other_prefecture_penalty(text, company.prefecture)
            score += other_prefecture_penalty
            
            # ④ Webページ解析による地域判定（情報が薄い場合の補強）
            if score == 0:  # タイトル・説明文から地域情報が取得できない場合
                # 🚀 ポータルサイトでは地域解析を無効化（NEW）
                domain = self.url_utils.get_domain(search_result.url).lower()
                is_portal = any(portal in domain for portal in [
                    'hotpepper.jp', 'rakuten.co.jp', 'minimodel.jp', 'relax.jp', 
                    'yahoo.co.jp', 'google.com', 'tabelog.com'
                ])
                
                if not is_portal:
                    web_location_score = self._calculate_web_location_score(search_result.url, company.prefecture)
                    score += web_location_score
                else:
                    logger.debug(f"ポータルサイトのため地域解析をスキップ: {search_result.url}")
            
            return score
            
        except Exception as e:
            logger.warning(f"地域スコア計算エラー: {search_result.url} - {e}")
            return 0
    
    def _calculate_web_location_score(self, url: str, target_prefecture: str) -> int:
        """
        Webページ解析による地域スコア計算（3段階ロジック）
        
        Args:
            url: 解析対象URL
            target_prefecture: 目標都道府県
            
        Returns:
            地域スコア
        """
        try:
            from .web_content_analyzer import WebContentAnalyzer
            
            analyzer = WebContentAnalyzer(timeout=5)  # 短めのタイムアウト
            location_info = analyzer.extract_location_info(url)
            
            if not location_info.prefecture:
                return 0
            
            # 地域一致判定
            if location_info.prefecture == target_prefecture:
                # 精度レベルに応じたボーナス
                if location_info.confidence_level == "high":
                    return 4  # JSON-LD構造化データ（+4点）
                elif location_info.confidence_level == "medium":
                    return 3  # HTMLフッター/正規表現（+3点）
                elif location_info.confidence_level == "low":
                    return 2  # お問い合わせページ（+2点）
            else:
                # 地域不一致ペナルティ
                if location_info.confidence_level == "high":
                    return -4  # JSON-LD構造化データ（-4点）
                elif location_info.confidence_level == "medium":
                    return -3  # HTMLフッター/正規表現（-3点）
                elif location_info.confidence_level == "low":
                    return -2  # お問い合わせページ（-2点）
            
            return 0
            
        except Exception as e:
            logger.warning(f"Web地域解析エラー: {url} - {e}")
            return 0
    
    def _get_area_code_for_scoring(self, prefecture: str) -> str:
        """
        都道府県から代表的な市外局番を取得（スコアリング用）
        
        Args:
            prefecture: 都道府県名
        
        Returns:
            市外局番（該当なしの場合は空文字）
        """
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
        }
        return area_code_map.get(prefecture, '')
    
    def _check_other_prefecture_penalty(self, text: str, target_prefecture: str) -> int:
        """
        他の都道府県が含まれている場合のペナルティ計算
        
        Args:
            text: 検索結果のタイトル+説明文
            target_prefecture: 目標の都道府県
        
        Returns:
            ペナルティスコア（0 または -10）
        """
        try:
            # 全47都道府県リスト
            all_prefectures = [
                '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
                '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
                '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
                '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
                '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
                '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
                '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
            ]
            
            # 目標都道府県以外が含まれているかチェック
            for prefecture in all_prefectures:
                if prefecture != target_prefecture:
                    # 都道府県名（県なし）でもチェック
                    prefecture_short = prefecture.replace('県', '').replace('府', '').replace('都', '').replace('道', '')
                    if prefecture.lower() in text.lower() or prefecture_short.lower() in text.lower():
                        return -100
            
            return 0
            
        except Exception as e:
            logger.warning(f"他県ペナルティ計算エラー: {target_prefecture} - {e}")
            return 0
    
    def _get_portal_domain_penalty(self, url: str) -> int:
        """
        ポータルドメインペナルティを計算
        
        Args:
            url: 検索結果のURL
        
        Returns:
            ペナルティスコア（0 または -2〜-4）
        """
        try:
            domain = self.url_utils.get_domain(url).lower()
            
            # ポータルサイトのペナルティマップ
            portal_penalties = {
                'hotpepper.jp': -4,
                'beauty.hotpepper.jp': -4,
                'relax.jp': -3,
                'rakuten.co.jp': -2,
                'yahoo.co.jp': -2,
                'google.com': -2,
            }
            
            for portal_domain, penalty in portal_penalties.items():
                if portal_domain in domain:
                    return penalty
            
            return 0
            
        except Exception as e:
            logger.warning(f"ポータルドメインペナルティ計算エラー: {url} - {e}")
            return 0
    
    def _get_enhanced_portal_penalty(self, url: str) -> int:
        """
        🔥 完全除外級ポータルドメインペナルティ
        
        Args:
            url: 検索結果のURL
        
        Returns:
            ペナルティスコア（0 または -100）
        """
        try:
            domain = self.url_utils.get_domain(url).lower()
            
            # 🔥 ポータルサイト完全除外リスト（-100点）
            portal_domains = {
                # 美容系ポータル
                'beauty.hotpepper.jp',
                'hotpepper.jp', 
                'beauty.rakuten.co.jp',
                'rakuten.co.jp',
                'minimodel.jp',
                'relax.jp',
                'beauty.biglobe.ne.jp',
                'epark.jp',
                'salonia.com',
                
                # 汎用ポータル
                'yahoo.co.jp',
                'google.com',
                'gnaviapp.com', 
                'tabelog.com',
                'yelp.com',
                'itp.ne.jp',        # タウンページ
                'mapion.co.jp',     # マピオン
                'navitime.co.jp',   # ナビタイム
                
                # SNS・まとめ系
                'facebook.com',
                'instagram.com', 
                'twitter.com',
                'ameblo.jp',
                'fc2.com',
                'livedoor.jp',
                'blogger.com',
                'wordpress.com',
                
                # 求人系
                'rikunabi.com',
                'mynavi.jp',
                'indeed.com',
                'doda.jp',
                'baitoru.com',
                
                # EC・レビュー系
                'amazon.co.jp',
                'mercari.com',
                'kakaku.com',
                '@cosme.net',
            }
            
            for portal_domain in portal_domains:
                if portal_domain in domain:
                    logger.debug(f"🔥 ポータルサイト完全除外: {domain} (-100点)")
                    return -100
            
            return 0
            
        except Exception as e:
            logger.warning(f"ポータルドメインペナルティ計算エラー: {url} - {e}")
            return 0
    
    def _is_reachable(self, url: str, timeout: int = 4) -> bool:
        """
        URLの死活確認
        
        Args:
            url: 確認対象のURL
            timeout: タイムアウト秒数
        
        Returns:
            到達可能かどうか
        """
        try:
            import requests
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except Exception as e:
            logger.debug(f"死活確認失敗: {url} - {e}")
            return False
    
    def _calculate_geographic_mismatch_penalty(self, search_result: SearchResult, company: CompanyInfo) -> int:
        """
        地域ミスマッチ強化ペナルティを計算
        Webページ解析で他県が検出された場合の追加ペナルティ
        
        Args:
            search_result: 検索結果
            company: 企業情報
        
        Returns:
            ペナルティスコア（0 または -5〜-8）
        """
        try:
            # Webページ解析で地域を取得
            from .web_content_analyzer import WebContentAnalyzer
            
            analyzer = WebContentAnalyzer(timeout=3)
            location_info = analyzer.extract_location_info(search_result.url)
            
            if not location_info.prefecture:
                return 0
            
            # 目標県と一致しない場合
            if location_info.prefecture != company.prefecture:
                # 🔥 地域違いは完全除外級のペナルティ！
                if location_info.confidence_level == "high":
                    penalty = -100  # JSON-LD等で確実に検出 → 完全除外
                elif location_info.confidence_level == "medium":
                    penalty = -50   # HTML解析で検出 → 大幅減点
                else:
                    penalty = -20   # 連絡先ページで検出 → 厳重減点
                
                logger.debug(f"地域ミスマッチペナルティ: {search_result.url} "
                           f"検出={location_info.prefecture} vs 目標={company.prefecture} "
                           f"信頼度={location_info.confidence_level} ペナルティ={penalty}")
                
                return penalty
            
            return 0
            
        except Exception as e:
            logger.debug(f"地域ミスマッチペナルティ計算エラー: {search_result.url} - {e}")
            return 0
    
    def _calculate_generic_word_penalty(self, company_name: str, url: str) -> int:
        """
        汎用語ペナルティ計算
        hair・groupなど汎用語のみの一致は減点
        
        Args:
            company_name: 企業名
            url: 検索結果のURL
        
        Returns:
            ペナルティスコア（0 または -5）
        """
        try:
            # 汎用語リスト
            generic_words = {
                # 美容系汎用語
                'hair', 'salon', 'beauty', 'cut', 'style', 'nail', 'spa',
                'esthetic', 'relax', 'care', 'clinic', 'total', 'private',
                
                # 一般汎用語
                'group', 'company', 'corp', 'co', 'inc', 'ltd', 'shop',
                'store', 'center', 'studio', 'design', 'creative', 'pro',
                'plus', 'premium', 'select', 'special', 'new', 'fresh',
                'modern', 'urban', 'royal', 'grand', 'first', 'main',
                
                # 地域系汎用語
                'tokyo', 'osaka', 'nagoya', 'yokohama', 'kyoto', 'kobe',
                'shibuya', 'shinjuku', 'ikebukuro', 'ginza', 'omotesando'
            }
            
            # 企業名から英語部分を抽出
            import re
            company_english = re.findall(r'[a-zA-Z]+', company_name.lower())
            
            # ドメイン名から英語部分を抽出
            domain = self.url_utils.get_domain(url)
            domain_without_tld = domain.split('.')[0].lower()
            domain_words = re.findall(r'[a-zA-Z]+', domain_without_tld)
            
            if not company_english or not domain_words:
                return 0
            
            # 一致する単語をチェック
            matched_words = []
            for comp_word in company_english:
                for domain_word in domain_words:
                    if comp_word == domain_word and comp_word in generic_words:
                        matched_words.append(comp_word)
            
            # 汎用語のみの一致かチェック
            if matched_words:
                # 非汎用語の一致があるかチェック
                non_generic_match = False
                for comp_word in company_english:
                    for domain_word in domain_words:
                        if comp_word == domain_word and comp_word not in generic_words:
                            non_generic_match = True
                            break
                    if non_generic_match:
                        break
                
                # 汎用語のみの一致の場合はペナルティ
                if not non_generic_match:
                    logger.debug(f"🔥 汎用語のみ一致ペナルティ: {matched_words} (-5点)")
                    return -5
            
            return 0
            
        except Exception as e:
            logger.warning(f"汎用語ペナルティ計算エラー: company='{company_name}' url='{url}' - {e}")
            return 0
    
    def _calculate_head_match_bonus(self, company_name: str, search_result: SearchResult) -> int:
        """
        HeadMatchボーナス計算（タイトルのみ版）
        企業名がタイトルに含まれているかで判定
        
        Args:
            company_name: 企業名
            search_result: 検索結果
        
        Returns:
            ボーナス・ペナルティスコア（-5～+10）
        """
        try:
            # 比較対象テキストの収集（タイトルのみ）
            head_texts = []
            
            # タイトルのみを対象とする
            if search_result.title:
                head_texts.append(search_result.title)
                # デバッグ用：タイトル文字数を確認
                logger.debug(f"HeadMatch - タイトル文字数: {len(search_result.title)} - '{search_result.title}'")
            
            if not head_texts:
                logger.debug("HeadMatch - タイトルが空のためスキップ")
                return 0
            
            # 企業名の正規化（HeadMatch専用追加処理）
            cleaned_company = self._enhanced_clean_company_name(company_name)
            
            # 🚀 業種接頭語を除去（HeadMatch専用）
            business_prefixes = ['美容室', 'サロン', 'ヘアサロン', '理容室', '理容店', 'バーバー', 'エステ', 'ネイル']
            for prefix in business_prefixes:
                if cleaned_company.startswith(prefix):
                    cleaned_company = cleaned_company[len(prefix):].strip()
                    break
            
            # ポータルサイト判定
            domain = self.url_utils.get_domain(search_result.url).lower()
            is_portal = any(portal in domain for portal in [
                'hotpepper.jp', 'rakuten.co.jp', 'minimodel.jp', 'relax.jp', 
                'yahoo.co.jp', 'google.com', 'tabelog.com', 'gnavi.co.jp',
                'beauty.hotpepper.jp', 'hairbook.jp'
            ])
            
            # 企業名が含まれているかチェック
            found_in_text = False
            matched_text = ""
            
            for text in head_texts:
                if not text:
                    continue
                
                # HTMLタグを除去してテキストを正規化
                import re
                clean_text = re.sub(r'<[^>]+>', '', text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                # 企業名が含まれているかチェック（大文字小文字無視）
                
                # 1. 完全一致チェック
                if cleaned_company.lower() in clean_text.lower():
                    found_in_text = True
                    matched_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
                    break
                
                # 2. より柔軟な一致（スペース・記号無視）
                company_no_space = re.sub(r'[\s\-_×&]', '', cleaned_company.lower())
                text_no_space = re.sub(r'[\s\-_×&]', '', clean_text.lower())
                
                if company_no_space in text_no_space and len(company_no_space) >= 3:
                    found_in_text = True
                    matched_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
                    break
                
                # 3. 🚀 部分単語一致（NEW）- 企業名の重要部分だけでも一致
                # 企業名を単語に分割して、各単語がテキストに含まれているかチェック
                company_words = [w.strip() for w in re.split(r'[\s\-_×&・]', cleaned_company) if w.strip() and len(w.strip()) >= 2]
                company_words_lower = [w.lower() for w in company_words]
                text_lower = clean_text.lower()
                
                matched_words = []
                for word in company_words_lower:
                    if word in text_lower and word not in ['店', '美容室', 'サロン', 'hair', 'beauty']:  # 汎用語は除外
                        matched_words.append(word)
                
                # 重要単語が1つ以上一致し、3文字以上の場合
                if matched_words and any(len(w) >= 3 for w in matched_words):
                    found_in_text = True
                    matched_text = clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
                    break
            
            # 得点判定
            if found_in_text:
                if is_portal:
                    # ポータルサイトの場合は中程度のボーナス
                    logger.info(f"🔥 HeadMatch(ポータル): '{matched_text}' (+5点)")
                    return 5
                else:
                    # 公式サイトの可能性が高い場合は高得点
                    logger.info(f"🔥 HeadMatch(公式可能性): '{matched_text}' (+10点)")
                    return 10
            else:
                # 企業名が含まれていない場合
                if is_portal:
                    # ポータルサイトなら軽微なペナルティ
                    logger.info(f"HeadMatch(ポータル・不一致): '{head_texts[0][:30] if head_texts else 'N/A'}...' (-2点)")
                    return -2
                else:
                    # 公式サイトなのに企業名がない場合は重いペナルティ
                    logger.info(f"🔥 HeadMatch(不一致): '{head_texts[0][:30] if head_texts else 'N/A'}...' (-5点)")
                    return -5
            
        except Exception as e:
            logger.warning(f"HeadMatchボーナス計算エラー: company='{company_name}' url='{search_result.url}' - {e}")
            return 0
    
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
        """
        🔥 TLDスコア改革版
        co.jpの加点は撤廃、怪しいTLDのみ減点
        """
        try:
            domain = self.url_utils.get_domain(url) # 既に小文字化されている
            
            # 🔥 怪しいTLDのみペナルティ
            suspicious_tlds = {'.tk', '.ml', '.ga', '.cf', '.xyz', '.click', '.download'}
            
            for tld in suspicious_tlds:
                if domain.endswith(tld):
                    logger.debug(f"🔥 怪しいTLD減点: {domain} (-3点)")
                    return -3
            
            # その他のTLD（.co.jp, .com, .net, .jp等）は全て0点
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
        elif total_score <= 0:
            return "該当なし"  # 🚀 0点以下は該当なし（NEW）
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