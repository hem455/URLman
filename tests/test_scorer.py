"""
Scorer モジュールの単体テスト
HP判定スコアリングロジックとフィルタリング機能のテスト
"""

import pytest
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import List, Dict, Optional

# 適切なパッケージインポート
from src.scorer import HPCandidate, ScoringConfig, HPScorer
from src.search_agent import SearchResult, CompanyInfo


class TestHPCandidate:
    """HPCandidateデータクラスのテスト"""
    
    def test_hp_candidate_creation(self):
        """HPCandidate作成のテスト"""
        candidate = HPCandidate(
            url="https://example.com",
            title="Example Site",
            description="An example website",
            search_rank=1,
            query_pattern="pattern_a",
            domain_similarity=85.5,
            is_top_page=True,
            total_score=12.0,
            judgment="自動採用",
            score_details={"domain": 5, "top_page": 5}
        )
        
        assert candidate.url == "https://example.com"
        assert candidate.title == "Example Site"
        assert candidate.domain_similarity == 85.5
        assert candidate.is_top_page is True
        assert candidate.total_score == 12.0
        assert candidate.judgment == "自動採用"
        assert candidate.score_details["domain"] == 5


class TestScoringConfig:
    """ScoringConfigデータクラスのテスト"""
    
    def test_scoring_config_creation(self):
        """ScoringConfig作成のテスト"""
        config = ScoringConfig(
            top_page_bonus=5,
            domain_exact_match=5,
            domain_similar_match=3,
            tld_co_jp=3,
            tld_com_net=1,
            official_keyword_bonus=2,
            search_rank_bonus=3,
            path_depth_penalty_factor=-10,
            domain_jp_penalty=-2,
            path_keyword_penalty=-2,
            auto_adopt_threshold=9,
            needs_review_threshold=6,
            similarity_threshold_domain=80
        )
        
        assert config.top_page_bonus == 5
        assert config.domain_exact_match == 5
        assert config.auto_adopt_threshold == 9
        assert config.similarity_threshold_domain == 80


class TestHPScorer:
    """HPScorerクラスのテスト"""
    
    def setup_method(self):
        """テスト用の設定"""
        self.config = ScoringConfig(
            top_page_bonus=5,
            domain_exact_match=5,
            domain_similar_match=3,
            tld_co_jp=3,
            tld_com_net=1,
            official_keyword_bonus=2,
            search_rank_bonus=3,
            path_depth_penalty_factor=-10,
            domain_jp_penalty=-2,
            path_keyword_penalty=-2,
            auto_adopt_threshold=9,
            needs_review_threshold=6,
            similarity_threshold_domain=80
        )
        
        self.blacklist_domains = {"hotpepper.jp", "tabelog.com", "indeed.com"}
        self.penalty_paths = ["/recruit/", "/career/", "/blog/", "/news/"]
        
        self.scorer = HPScorer(
            config=self.config,
            blacklist_domains=self.blacklist_domains,
            penalty_paths=self.penalty_paths
        )
        
        self.test_company = CompanyInfo(
            id="001",
            company_name="Barber Boss【バーバー ボス】",
            prefecture="東京都",
            industry="美容業"
        )
    
    def test_scorer_initialization(self):
        """HPScorer初期化のテスト"""
        assert self.scorer.config == self.config
        assert self.scorer.blacklist_domains == self.blacklist_domains
        assert self.scorer.penalty_paths == self.penalty_paths
    
    def test_is_blacklisted_domain(self):
        """ブラックリストドメイン判定のテスト"""
        # ブラックリストドメイン
        assert self.scorer._is_blacklisted_domain("https://hotpepper.jp/page") is True
        assert self.scorer._is_blacklisted_domain("https://tabelog.com/restaurant") is True
        
        # 正常なドメイン
        assert self.scorer._is_blacklisted_domain("https://barberboss.com") is False
        assert self.scorer._is_blacklisted_domain("https://example.co.jp") is False
        
        # www付きドメイン
        assert self.scorer._is_blacklisted_domain("https://www.hotpepper.jp/page") is True
    
    def test_calculate_domain_similarity(self):
        """ドメイン類似度計算のテスト"""
        # 完全一致
        similarity = self.scorer._calculate_domain_similarity(
            "Barber Boss", "barberboss.com"
        )
        assert similarity >= 80  # 高い類似度が期待される
        
        # 部分一致
        similarity = self.scorer._calculate_domain_similarity(
            "ABC Company", "abc.co.jp"
        )
        assert similarity >= 70
        
        # 類似度が低い場合
        similarity = self.scorer._calculate_domain_similarity(
            "Sample Company", "completely-different.com"
        )
        assert similarity < 50
    
    def test_is_top_page(self):
        """トップページ判定のテスト"""
        # トップページ
        assert self.scorer._is_top_page("https://example.com") is True
        assert self.scorer._is_top_page("https://example.com/") is True
        assert self.scorer._is_top_page("https://example.com/index.html") is True
        assert self.scorer._is_top_page("https://example.com/index.php") is True
        
        # サブページ
        assert self.scorer._is_top_page("https://example.com/about") is False
        assert self.scorer._is_top_page("https://example.com/products/item") is False
    
    def test_has_official_keywords(self):
        """公式キーワード判定のテスト"""
        # 公式キーワードあり
        assert self.scorer._has_official_keywords("Example Company 公式サイト") is True
        assert self.scorer._has_official_keywords("Official Site - Example") is True
        assert self.scorer._has_official_keywords("Example オフィシャル") is True
        
        # 公式キーワードなし
        assert self.scorer._has_official_keywords("Example Company") is False
        assert self.scorer._has_official_keywords("Product Information") is False
    
    def test_get_tld_score(self):
        """TLDスコア計算のテスト"""
        # .co.jp
        assert self.scorer._get_tld_score("https://example.co.jp") == 3
        
        # .com, .net
        assert self.scorer._get_tld_score("https://example.com") == 1
        assert self.scorer._get_tld_score("https://example.net") == 1
        
        # .jp (単独)
        assert self.scorer._get_tld_score("https://example.jp") == -2
        
        # その他
        assert self.scorer._get_tld_score("https://example.org") == 0
    
    def test_get_search_rank_bonus(self):
        """検索順位ボーナスのテスト"""
        # 上位3位
        assert self.scorer._get_search_rank_bonus(1) == 3
        assert self.scorer._get_search_rank_bonus(2) == 3
        assert self.scorer._get_search_rank_bonus(3) == 3
        
        # 4位以降
        assert self.scorer._get_search_rank_bonus(4) == 0
        assert self.scorer._get_search_rank_bonus(10) == 0
    
    def test_get_path_penalty(self):
        """パスペナルティ計算のテスト"""
        # ペナルティパス
        assert self.scorer._get_path_penalty("https://example.com/recruit/") == -2
        assert self.scorer._get_path_penalty("https://example.com/blog/post") == -2
        assert self.scorer._get_path_penalty("https://example.com/career/jobs") == -2
        
        # 正常なパス
        assert self.scorer._get_path_penalty("https://example.com/") == 0
        assert self.scorer._get_path_penalty("https://example.com/about") == 0
    
    def test_calculate_score_high_score_case(self):
        """高スコアケースの計算テスト"""
        search_result = SearchResult(
            url="https://barberboss.co.jp",
            title="Barber Boss 公式サイト",
            description="バーバーボス公式ホームページ",
            rank=1
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # 高いスコアが期待される
        assert candidate.total_score >= 9  # 自動採用閾値
        assert candidate.judgment == "自動採用"
        assert candidate.is_top_page is True
        assert candidate.domain_similarity >= 80
    
    def test_calculate_score_blacklisted_domain(self):
        """ブラックリストドメインのテスト"""
        search_result = SearchResult(
            url="https://hotpepper.jp/barber/boss",
            title="Barber Boss - ホットペッパー",
            description="ホットペッパーの店舗情報",
            rank=1
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # ブラックリストドメインは除外される
        assert candidate is None
    
    def test_calculate_score_with_penalty_path(self):
        """ペナルティパスのテスト"""
        search_result = SearchResult(
            url="https://barberboss.com/recruit/",
            title="Barber Boss 求人情報",
            description="求人募集ページ",
            rank=1
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # ペナルティが適用される
        assert candidate.total_score < 5  # 減点により低いスコア
        assert "/recruit/" in candidate.url
    
    def test_calculate_score_needs_review_case(self):
        """要確認ケースのテスト"""
        search_result = SearchResult(
            url="https://similar-name.com/about",
            title="Similar Company",
            description="企業情報ページ",
            rank=5
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # 中程度のスコア
        assert 6 <= candidate.total_score < 9
        assert candidate.judgment == "要確認"
    
    def test_calculate_score_manual_review_case(self):
        """手動確認ケースのテスト"""
        search_result = SearchResult(
            url="https://completely-different.org/deep/path/page",
            title="Different Company",
            description="全く関係ない会社",
            rank=10
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # 低いスコア
        assert candidate.total_score < 6
        assert candidate.judgment == "手動確認"
    
    def test_score_multiple_candidates(self):
        """複数候補のスコアリングテスト"""
        search_results = {
            "pattern_a": [
                SearchResult("https://barberboss.co.jp", "Barber Boss 公式", "公式サイト", 1),
                SearchResult("https://hotpepper.jp/barber", "ホットペッパー掲載", "掲載情報", 2)
            ],
            "pattern_b": [
                SearchResult("https://barberboss.com", "Barber Boss", "会社サイト", 1)
            ]
        }
        
        scored_candidates = self.scorer.score_multiple_candidates(
            search_results, self.test_company
        )
        
        # ブラックリストドメインは除外される
        assert len(scored_candidates) == 2  # hotpepper.jpは除外
        
        # スコア順でソートされている
        assert scored_candidates[0].total_score >= scored_candidates[1].total_score
    
    def test_get_best_candidate_auto_adopt(self):
        """最良候補取得（自動採用）のテスト"""
        search_results = {
            "pattern_a": [
                SearchResult("https://barberboss.co.jp", "Barber Boss 公式サイト", "公式", 1)
            ]
        }
        
        best_candidate = self.scorer.get_best_candidate(search_results, self.test_company)
        
        assert best_candidate is not None
        assert best_candidate.judgment == "自動採用"
        assert best_candidate.total_score >= 9
    
    def test_get_best_candidate_no_good_candidates(self):
        """良い候補がない場合のテスト"""
        search_results = {
            "pattern_a": [
                SearchResult("https://hotpepper.jp/barber", "ホットペッパー", "掲載情報", 1)
            ]
        }
        
        best_candidate = self.scorer.get_best_candidate(search_results, self.test_company)
        
        # ブラックリストドメインのみの場合はNone
        assert best_candidate is None
    
    def test_get_best_candidate_needs_review(self):
        """要確認候補のテスト"""
        search_results = {
            "pattern_a": [
                SearchResult("https://similar-company.com/about", "Similar", "企業情報", 1)
            ]
        }
        
        best_candidate = self.scorer.get_best_candidate(search_results, self.test_company)
        
        assert best_candidate is not None
        assert best_candidate.judgment in ["要確認", "手動確認"]


class TestScoringLogicDetails:
    """スコアリングロジック詳細テスト"""
    
    def setup_method(self):
        """テスト用設定"""
        self.config = ScoringConfig()
        self.scorer = HPScorer(self.config, set(), [])
        
        self.test_company = CompanyInfo(
            id="001",
            company_name="株式会社テスト【テスト】",
            prefecture="東京都", 
            industry="IT業"
        )
    
    def test_domain_similarity_calculation_edge_cases(self):
        """ドメイン類似度計算のエッジケース"""
        # 会社名の正規化テスト
        similarity1 = self.scorer._calculate_domain_similarity(
            "株式会社テスト【テスト】", "test.co.jp"
        )
        similarity2 = self.scorer._calculate_domain_similarity(
            "テスト", "test.co.jp"
        )
        
        # 正規化により類似度が向上することを確認
        assert similarity1 >= 70
        assert similarity2 >= 70
    
    def test_score_calculation_with_all_bonuses(self):
        """全ボーナス適用時のスコア計算"""
        search_result = SearchResult(
            url="https://test.co.jp",  # co.jp +3
            title="株式会社テスト 公式サイト",  # 公式キーワード +2
            description="テスト会社の公式ホームページ",
            rank=1  # 検索上位 +3
        )
        
        candidate = self.scorer.calculate_score(search_result, self.test_company, "pattern_a")
        
        # 各要素のスコアを確認
        details = candidate.score_details
        assert details["tld_score"] == 3  # .co.jp
        assert details["official_keyword"] == 2  # 公式キーワード
        assert details["search_rank"] == 3  # 検索上位
        assert details["top_page"] == 5  # トップページ
        assert details["domain_similarity_score"] >= 3  # ドメイン類似度スコア


if __name__ == "__main__":
    # 単独実行時のテスト
    pytest.main([__file__, "-v"]) 