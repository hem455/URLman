#!/usr/bin/env python3
"""
実際の検索結果でのスコア詳細内訳確認テストスクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをpathに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.search_agent import SearchAgent, CompanyInfo
from src.scorer import HPScorer, ScoringConfig
from src.utils import BlacklistChecker
import logging

# ログレベルを調整
logging.basicConfig(level=logging.INFO)

def test_actual_score_details():
    """実際の企業データでスコア詳細内訳をテスト"""
    
    print("🔍 実際の企業データスコア詳細内訳テスト")
    print("=" * 60)
    
    # 設定初期化
    config = ScoringConfig()
    blacklist_checker = BlacklistChecker("config/blacklist.yaml")
    
    # BraveSearchClientを直接初期化
    from src.search_agent import BraveSearchClient
    brave_client = BraveSearchClient(api_key=os.getenv("BRAVE_API_KEY", "dummy_key"))
    
    # HPScorerを直接使用
    scorer = HPScorer(config, blacklist_checker.get_blacklist_domains())
    
    # テスト企業データ
    test_companies = [
        CompanyInfo(
            id="test1",
            company_name="美髪処 縁‐ENISHI‐",
            prefecture="愛知県",
            industry="ヘアサロン"
        ),
        CompanyInfo(
            id="test2", 
            company_name="octo hair",
            prefecture="愛知県",  # ← 実際のデータでの設定を確認
            industry="ヘアサロン"
        )
    ]
    
    for i, company in enumerate(test_companies, 1):
        print(f"💼 企業 {i}/{len(test_companies)}: {company.company_name}")
        print(f"🏢 所在地: {company.prefecture}")
        print(f"🏭 業種: {company.industry}")
        
        try:
                         # 検索実行（実際のAPIコールは無効化してテスト用結果を使用）
             if company.company_name == "美髪処 縁‐ENISHI‐":
                 # 実際の検索結果を模擬
                 from src.search_agent import SearchResult
                 test_result = SearchResult(
                     url="https://hairenishi.jp",
                     title="美髪処 縁‐ENISHI‐ 愛知県の美容室・ヘアサロン",
                     description="愛知県にある美髪処 縁‐ENISHI‐の公式サイト。カット、カラー、パーマなど",
                     rank=1
                 )
                 
                                  # スコア計算
                 scored_result = scorer.calculate_score(
                     test_result, 
                     company, 
                     f"{company.company_name} {company.prefecture} {company.industry}"
                 )
                
                print(f"🔗 URL: {test_result.url}")
                print(f"📊 総合スコア: {scored_result.total_score}点")
                print(f"🏆 判定: {scored_result.judgment}")
                print("📋 詳細内訳:")
                for key, value in scored_result.score_details.items():
                    score_name = {
                        'top_page': 'トップページボーナス',
                        'domain_similarity_score': 'ドメイン類似度スコア', 
                        'tld_score': 'TLDスコア(.co.jp/com等)',
                        'official_keyword': '公式キーワードボーナス',
                        'search_rank': '検索順位ボーナス(1-3位)',
                        'path_penalty': 'パスペナルティ',
                        'locality': '地域特定スコア',
                        'portal_penalty': 'ポータルペナルティ'
                    }.get(key, key)
                    print(f"   • {score_name}: {value:+}点")
                    
            elif company.company_name == "octo hair":
                # octo hair の実際の検索結果を模擬
                test_result = SearchResult(
                    url="https://octo-takao.jp/",
                    title="octo hair - 美容室",  # 実際のタイトルに近づける
                    description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
                    rank=1
                )
                
                # スコア計算
                scored_result = search_agent.scorer.calculate_score(
                    test_result, 
                    company, 
                    f"{company.company_name} {company.prefecture} {company.industry}"
                )
                
                print(f"🔗 URL: {test_result.url}")
                print(f"📊 総合スコア: {scored_result.total_score}点")
                print(f"🏆 判定: {scored_result.judgment}")
                print("📋 詳細内訳:")
                for key, value in scored_result.score_details.items():
                    score_name = {
                        'top_page': 'トップページボーナス',
                        'domain_similarity_score': 'ドメイン類似度スコア', 
                        'tld_score': 'TLDスコア(.co.jp/com等)',
                        'official_keyword': '公式キーワードボーナス',
                        'search_rank': '検索順位ボーナス(1-3位)',
                        'path_penalty': 'パスペナルティ',
                        'locality': '地域特定スコア',
                        'portal_penalty': 'ポータルペナルティ'
                    }.get(key, key)
                    print(f"   • {score_name}: {value:+}点")
                
                # 地域スコアの詳細分析
                print("\n🚨 地域スコア詳細分析:")
                if scored_result.score_details.get('locality', 0) == 2:
                    print("   ✅ 地域一致ボーナス: +2点")
                    print("   💡 他県ペナルティが適用されていない理由:")
                    print("      → 企業も愛知県、検索も愛知県のため正常")
                elif scored_result.score_details.get('locality', 0) == -10:
                    print("   ❌ 他県ペナルティ: -10点")
                    print("   💡 企業の実際の所在地が愛知県以外の可能性")
                else:
                    print(f"   ⚠️  予期しないスコア: {scored_result.score_details.get('locality', 0)}点")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        print()

def test_prefecture_mismatch():
    """都道府県ミスマッチのテスト"""
    print("🧪 都道府県ミスマッチテスト")
    print("=" * 40)
    
    # octo hairを東京都企業として設定してテスト
    config = ScoringConfig()
    blacklist_checker = BlacklistChecker("config/blacklist.yaml")
    scorer = HPScorer(config, blacklist_checker.get_blacklist_domains())
    
    # 東京都企業のocto hair
    tokyo_company = CompanyInfo(
        id="test_tokyo",
        company_name="octo hair",
        prefecture="東京都",  # ← 東京都に設定
        industry="ヘアサロン"
    )
    
    # 愛知県で検索された結果（地域ミスマッチ）
    from src.search_agent import SearchResult
    mismatch_result = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
        rank=1
    )
    
    # 愛知県検索クエリで東京都企業をスコアリング
    scored_mismatch = scorer.calculate_score(
        mismatch_result, 
        tokyo_company, 
        "octo hair 愛知県 ヘアサロン"  # ← 愛知県で検索
    )
    
    print(f"🏢 企業所在地: {tokyo_company.prefecture}")
    print(f"🔍 検索対象県: 愛知県")
    print(f"🔗 URL: {mismatch_result.url}")
    print(f"📊 総合スコア: {scored_mismatch.total_score}点")
    print(f"🏆 判定: {scored_mismatch.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored_mismatch.score_details.items():
        score_name = {
            'top_page': 'トップページボーナス',
            'domain_similarity_score': 'ドメイン類似度スコア', 
            'tld_score': 'TLDスコア(.co.jp/com等)',
            'official_keyword': '公式キーワードボーナス',
            'search_rank': '検索順位ボーナス(1-3位)',
            'path_penalty': 'パスペナルティ',
            'locality': '地域特定スコア',
            'portal_penalty': 'ポータルペナルティ'
        }.get(key, key)
        print(f"   • {score_name}: {value:+}点")
    
    print(f"\n🎯 地域ペナルティ効果確認:")
    locality_score = scored_mismatch.score_details.get('locality', 0)
    if locality_score <= -8:
        print(f"   ✅ 他県ペナルティ適用: {locality_score}点")
    else:
        print(f"   ❌ 他県ペナルティ未適用: {locality_score}点")

if __name__ == "__main__":
    test_actual_score_details()
    print("\n" + "="*60)
    test_prefecture_mismatch() 