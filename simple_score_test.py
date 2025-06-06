#!/usr/bin/env python3
"""
シンプルなスコア詳細確認テスト
"""

import sys
from pathlib import Path

# プロジェクトルートをpathに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.search_agent import SearchResult, CompanyInfo
from src.scorer import HPScorer, ScoringConfig
from src.utils import BlacklistChecker

def test_score_details():
    """実際の企業データでスコア詳細確認"""
    
    print("🔍 スコア詳細内訳確認")
    print("=" * 50)
    
    # 設定初期化
    config = ScoringConfig()
    blacklist_checker = BlacklistChecker("config/blacklist.yaml")
    scorer = HPScorer(config, blacklist_checker.get_blacklist_domains())
    
    # テスト1: 美髪処 縁‐ENISHI‐ (愛知県)
    print("🎯 Case 1: 美髪処 縁‐ENISHI‐ (愛知県)")
    company1 = CompanyInfo(
        id="test1",
        company_name="美髪処 縁‐ENISHI‐",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    result1 = SearchResult(
        url="https://hairenishi.jp",
        title="美髪処 縁‐ENISHI‐ 愛知県の美容室・ヘアサロン",
        description="愛知県にある美髪処 縁‐ENISHI‐の公式サイト。カット、カラー、パーマなど",
        rank=1
    )
    
    scored1 = scorer.calculate_score(result1, company1, "美髪処 縁‐ENISHI‐ 愛知県 ヘアサロン")
    
    print(f"🔗 URL: {result1.url}")
    print(f"📊 総合スコア: {scored1.total_score}点")
    print(f"🏆 判定: {scored1.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored1.score_details.items():
        print(f"   • {key}: {value:+}点")
    print()
    
    # テスト2: octo hair (愛知県として設定)
    print("🎯 Case 2: octo hair (愛知県)")
    company2 = CompanyInfo(
        id="test2",
        company_name="octo hair",
        prefecture="愛知県",  # 愛知県として設定
        industry="ヘアサロン"
    )
    
    result2 = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
        rank=1
    )
    
    scored2 = scorer.calculate_score(result2, company2, "octo hair 愛知県 ヘアサロン")
    
    print(f"🔗 URL: {result2.url}")
    print(f"📊 総合スコア: {scored2.total_score}点")
    print(f"🏆 判定: {scored2.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored2.score_details.items():
        print(f"   • {key}: {value:+}点")
    print()
    
    # テスト3: octo hair (東京都として設定) ← ミスマッチテスト
    print("🎯 Case 3: octo hair (東京都) ← 愛知県で検索")
    company3 = CompanyInfo(
        id="test3",
        company_name="octo hair",
        prefecture="東京都",  # 東京都として設定
        industry="ヘアサロン"
    )
    
    result3 = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
        rank=1
    )
    
    scored3 = scorer.calculate_score(result3, company3, "octo hair 愛知県 ヘアサロン")
    
    print(f"🏢 企業所在地: {company3.prefecture}")
    print(f"🔍 検索対象: 愛知県")
    print(f"🔗 URL: {result3.url}")
    print(f"📊 総合スコア: {scored3.total_score}点")
    print(f"🏆 判定: {scored3.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored3.score_details.items():
        print(f"   • {key}: {value:+}点")
    
    # 地域ペナルティ効果確認
    print(f"\n🎯 地域ペナルティ効果:")
    print(f"   愛知県企業: {scored2.total_score}点")
    print(f"   東京都企業: {scored3.total_score}点")
    print(f"   差: {scored2.total_score - scored3.total_score:+}点")

if __name__ == "__main__":
    test_score_details() 