#!/usr/bin/env python3
"""
scorer.py 改修のテストスクリプト
日本語→ローマ字変換とドメイン類似度計算の検証
"""

import sys
from pathlib import Path

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / 'src'))

from src.scorer import HPScorer, ScoringConfig
from src.search_agent import SearchResult, CompanyInfo
from src.utils import StringUtils, URLUtils

def test_romanization():
    """ローマ字変換のテスト"""
    print("=== ローマ字変換テスト ===")
    
    scorer = HPScorer(ScoringConfig())
    
    test_cases = [
        "グラントホープ",
        "サンプル",
        "テスト会社",
        "バーバーボス",
        "Barber Boss",  # 英語の場合
        ""  # 空文字
    ]
    
    for name in test_cases:
        romanized = scorer._romanize(name)
        print(f"'{name}' → '{romanized}'")

def test_enhanced_cleaning():
    """強化された企業名正規化のテスト"""
    print("\n=== 企業名正規化テスト ===")
    
    scorer = HPScorer(ScoringConfig())
    
    test_cases = [
        "株式会社グラントホープ【グラントホープ】",
        "有限会社サンプル",
        "Barber Boss【バーバー ボス】",
        "㈱テスト",
        "サンプル・テスト株式会社",
        "ABC Holdings (Japan)",
    ]
    
    for name in test_cases:
        cleaned = scorer._enhanced_clean_company_name(name)
        print(f"'{name}' → '{cleaned}'")

def test_domain_similarity():
    """ドメイン類似度計算のテスト"""
    print("\n=== ドメイン類似度計算テスト ===")
    
    scorer = HPScorer(ScoringConfig())
    
    test_cases = [
        ("株式会社グラントホープ", "https://granthope.jp"),
        ("バーバーボス", "https://barberboss.com"),
        ("サンプル株式会社", "https://sample.co.jp"),
        ("テスト", "https://test-company.jp"),
        ("ABC Corporation", "https://abc.com"),
        ("全く関係ない会社", "https://unrelated.com"),
    ]
    
    for company_name, url in test_cases:
        similarity = scorer._calculate_domain_similarity(company_name, url)
        print(f"'{company_name}' vs '{url}' → {similarity:.1f}%")

def test_full_scoring():
    """フルスコアリングのテスト"""
    print("\n=== フルスコアリングテスト ===")
    
    scorer = HPScorer(ScoringConfig())
    
    # テスト用の企業情報
    company = CompanyInfo(
        id="001",
        company_name="株式会社グラントホープ",
        prefecture="東京都",
        industry="IT業"
    )
    
    # テスト用の検索結果
    search_results = [
        SearchResult(
            url="https://granthope.jp",
            title="グラントホープ｜公式サイト",
            description="株式会社グラントホープの公式サイトです。",
            rank=1
        ),
        SearchResult(
            url="https://granthope.co.jp/about",
            title="会社概要 - グラントホープ",
            description="会社概要ページ",
            rank=2
        ),
        SearchResult(
            url="https://unrelated.com",
            title="無関係なサイト",
            description="全く関係のないウェブサイト",
            rank=3
        )
    ]
    
    for result in search_results:
        candidate = scorer.calculate_score(result, company, "test_pattern")
        if candidate:
            print(f"\nURL: {candidate.url}")
            print(f"スコア: {candidate.total_score}")
            print(f"判定: {candidate.judgment}")
            print(f"ドメイン類似度: {candidate.domain_similarity:.1f}%")
            print(f"詳細: {candidate.score_details}")
        else:
            print(f"\n除外: {result.url}")

def test_with_adjusted_threshold():
    """閾値を調整したスコアリングテスト"""
    print("\n=== 閾値調整テスト（70%）===")
    
    # 類似度閾値を70%に下げる
    config = ScoringConfig()
    config.similarity_threshold_domain = 70
    scorer = HPScorer(config)
    
    # テスト用の企業情報
    company = CompanyInfo(
        id="001",
        company_name="株式会社グラントホープ",
        prefecture="東京都",
        industry="IT業"
    )
    
    # テスト用の検索結果
    result = SearchResult(
        url="https://granthope.jp",
        title="グラントホープ｜公式サイト",
        description="株式会社グラントホープの公式サイトです。",
        rank=1
    )
    
    candidate = scorer.calculate_score(result, company, "test_pattern")
    if candidate:
        print(f"URL: {candidate.url}")
        print(f"スコア: {candidate.total_score}")
        print(f"判定: {candidate.judgment}")
        print(f"ドメイン類似度: {candidate.domain_similarity:.1f}%")
        print(f"詳細: {candidate.score_details}")
        
        # 76.2%の場合、domain_similar_match(3点)が付与されることを確認
        expected_domain_score = 3 if candidate.domain_similarity >= 70 else 0
        actual_domain_score = candidate.score_details.get('domain_similarity_score', 0)
        print(f"期待ドメインスコア: {expected_domain_score}, 実際: {actual_domain_score}")

def main():
    """メイン関数"""
    print("scorer.py 改修テスト開始")
    
    try:
        test_romanization()
        test_enhanced_cleaning()
        test_domain_similarity()
        test_full_scoring()
        test_with_adjusted_threshold()
        
        print("\n✅ 全テスト完了")
        
    except Exception as e:
        print(f"\n❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 