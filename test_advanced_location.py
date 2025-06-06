#!/usr/bin/env python3
"""
3段階地域判定システムテスト
"""

import sys
from pathlib import Path

# プロジェクトルートをpathに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.search_agent import SearchResult, CompanyInfo
from src.scorer import HPScorer, ScoringConfig
from src.utils import BlacklistChecker

def test_advanced_location_scoring():
    """高度な地域判定システムテスト"""
    
    print("🔍 3段階地域判定システムテスト")
    print("=" * 50)
    
    # 設定初期化
    config = ScoringConfig()
    blacklist_checker = BlacklistChecker("config/blacklist.yaml")
    scorer = HPScorer(config, blacklist_checker.get_blacklist_domains())
    
    # テスト企業（愛知県）
    company = CompanyInfo(
        id="test",
        company_name="octo hair",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    # ケース1: タイトル・説明文に地域情報なし（Webページ解析が発動）
    print("🎯 Case 1: 地域情報薄い場合（Webページ解析発動）")
    result1 = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",  # 地域情報なし
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",  # 地域情報なし
        rank=1
    )
    
    scored1 = scorer.calculate_score(result1, company, "octo hair 愛知県 ヘアサロン")
    
    print(f"🔗 URL: {result1.url}")
    print(f"📊 総合スコア: {scored1.total_score}点")
    print(f"🏆 判定: {scored1.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored1.score_details.items():
        print(f"   • {key}: {value:+}点")
    
    # 地域スコアの詳細説明
    locality_score = scored1.score_details.get('locality', 0)
    print(f"\n🎯 地域スコア詳細分析: {locality_score}点")
    if locality_score > 0:
        if locality_score == 4:
            print("   ✅ JSON-LD構造化データで地域一致確認（+4点）")
        elif locality_score == 3:
            print("   ✅ HTMLフッター/正規表現で地域一致確認（+3点）")
        elif locality_score == 2:
            print("   ✅ お問い合わせページで地域一致確認（+2点）")
        else:
            print("   ✅ 基本地域一致ボーナス（+2点）")
    elif locality_score < 0:
        if locality_score == -4:
            print("   ❌ JSON-LD構造化データで地域不一致確認（-4点）")
        elif locality_score == -3:
            print("   ❌ HTMLフッター/正規表現で地域不一致確認（-3点）")
        elif locality_score <= -10:
            print("   ❌ 他県ミスマッチペナルティ適用（-10点）")
        else:
            print(f"   ❌ 地域不一致ペナルティ（{locality_score}点）")
    else:
        print("   ⚠️  地域情報を特定できませんでした")
    
    print()
    
    # ケース2: タイトル・説明文に愛知県情報あり（従来ロジック優先）
    print("🎯 Case 2: タイトル・説明文に地域情報あり（従来ロジック）")
    result2 = SearchResult(
        url="https://hairenishi.jp",
        title="美髪処 縁‐ENISHI‐ 愛知県の美容室・ヘアサロン",  # 愛知県記載
        description="愛知県にある美髪処 縁‐ENISHI‐の公式サイト。052-123-4567",  # 052局番記載
        rank=1
    )
    
    scored2 = scorer.calculate_score(result2, company, "美髪処 縁‐ENISHI‐ 愛知県 ヘアサロン")
    
    print(f"🔗 URL: {result2.url}")
    print(f"📊 総合スコア: {scored2.total_score}点")
    print(f"🏆 判定: {scored2.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored2.score_details.items():
        print(f"   • {key}: {value:+}点")
    
    locality_score2 = scored2.score_details.get('locality', 0)
    print(f"\n🎯 地域スコア詳細分析: {locality_score2}点")
    print("   ✅ 従来ロジック: 県名一致(+2) + 052局番一致(+3) = +5点")
    print("   💡 Webページ解析はスキップされます")
    
    print()
    
    # ケース3: 東京都企業が愛知県で検索された場合
    print("🎯 Case 3: 地域ミスマッチ（東京都企業 vs 愛知県検索）")
    tokyo_company = CompanyInfo(
        id="test_tokyo",
        company_name="octo hair",
        prefecture="東京都",
        industry="ヘアサロン"
    )
    
    result3 = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。東京都渋谷区のヘアサロン 03-1234-5678",  # 東京都・03局番記載
        rank=1
    )
    
    scored3 = scorer.calculate_score(result3, tokyo_company, "octo hair 愛知県 ヘアサロン")
    
    print(f"🏢 企業所在地: {tokyo_company.prefecture}")
    print(f"🔍 検索対象: 愛知県")
    print(f"🔗 URL: {result3.url}")
    print(f"📊 総合スコア: {scored3.total_score}点")
    print(f"🏆 判定: {scored3.judgment}")
    print("📋 詳細内訳:")
    for key, value in scored3.score_details.items():
        print(f"   • {key}: {value:+}点")
    
    locality_score3 = scored3.score_details.get('locality', 0)
    print(f"\n🎯 地域スコア詳細分析: {locality_score3}点")
    if locality_score3 <= -10:
        print("   ❌ 他県ペナルティ: 東京都情報検出により-10点")
    else:
        print(f"   ⚠️  予期しないスコア: {locality_score3}点")
    
    # 総合効果確認
    print(f"\n📊 3段階地域判定システム効果確認:")
    print(f"   🔧 地域情報薄い場合: {scored1.total_score}点")
    print(f"   ✅ 地域情報十分な場合: {scored2.total_score}点")
    print(f"   ❌ 地域ミスマッチ: {scored3.total_score}点")
    print(f"\n🎯 スコア差:")
    print(f"   正確vs薄い: {scored2.total_score - scored1.total_score:+}点")
    print(f"   正確vsミスマッチ: {scored2.total_score - scored3.total_score:+}点")

if __name__ == "__main__":
    test_advanced_location_scoring() 