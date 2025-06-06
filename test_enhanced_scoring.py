#!/usr/bin/env python3
"""
強化版スコアリングシステムのテスト
美髪処 縁‐ENISHI‐ と octo hair の問題を検証
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from src.search_agent import SearchResult, CompanyInfo
from src.scorer import HPScorer, ScoringConfig
from src.utils import StringUtils, URLUtils

def test_enhanced_scoring():
    print("🚀 強化版スコアリングシステムテスト")
    print("=" * 60)
    
    # 強化設定でスコアラー初期化
    config = ScoringConfig()
    scorer = HPScorer(config=config)
    
    # テスト用企業情報
    enishi_company = CompanyInfo(
        id="test1",
        company_name="美髪処 縁‐ENISHI‐",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    print(f"🏢 テスト企業: {enishi_company.company_name} ({enishi_company.prefecture})")
    print()
    
    # 🎯 Case 1: 正解サイト (hairenishi.jp)
    print("✅ Case 1: 正解サイト (hairenishi.jp)")
    correct_result = SearchResult(
        url="https://hairenishi.jp/",
        title="美髪処 縁‐ENISHI‐ - 愛知県のヘアサロン",
        description="愛知県にある美髪処 縁‐ENISHI‐の公式サイト。カット、カラー、パーマなど",
        rank=1
    )
    
    correct_score = scorer.calculate_score(correct_result, enishi_company, "テストクエリ")
    print(f"🔗 URL: {correct_result.url}")
    print(f"📊 総合スコア: {correct_score.total_score}点")
    print(f"🏆 判定: {correct_score.judgment}")
    print(f"🔍 類似度: {correct_score.domain_similarity:.1f}%")
    print(f"📋 詳細: {correct_score.score_details}")
    print()
    
    # 🚫 Case 2: 楽天ビューティー (問題のサイト)
    print("🚫 Case 2: 楽天ビューティー (問題のサイト)")
    rakuten_result = SearchResult(
        url="https://beauty.rakuten.co.jp/s0000045369/",
        title="美髪処 縁‐ENISHI‐ - 楽天ビューティー",
        description="美髪処 縁‐ENISHI‐の店舗情報。愛知県。オンライン予約可能",
        rank=2
    )
    
    rakuten_score = scorer.calculate_score(rakuten_result, enishi_company, "テストクエリ")
    print(f"🔗 URL: {rakuten_result.url}")
    print(f"📊 総合スコア: {rakuten_score.total_score}点")
    print(f"🏆 判定: {rakuten_score.judgment}")
    print(f"🔍 類似度: {rakuten_score.domain_similarity:.1f}%")
    print(f"📋 詳細: {rakuten_score.score_details}")
    print()
    
    # 📊 比較結果
    print("📊 比較結果:")
    print(f"   ✅ 正解サイト: {correct_score.total_score}点 ({correct_score.judgment})")
    print(f"   🚫 楽天ビューティー: {rakuten_score.total_score}点 ({rakuten_score.judgment})")
    print(f"   🎯 スコア差: {correct_score.total_score - rakuten_score.total_score}点")
    
    if correct_score.total_score > rakuten_score.total_score:
        print("   ✅ 修正成功！正解サイトが勝利")
    else:
        print("   ❌ まだ問題あり：楽天が勝ってしまう")
    print()
    
    # 🔍 語幹スプリット効果テスト
    print("🔍 語幹スプリット効果テスト")
    print("=" * 40)
    
    # ドメイン類似度の詳細確認
    old_similarity = _calculate_domain_similarity_old("美髪処 縁‐ENISHI‐", "https://hairenishi.jp/")
    new_similarity = scorer._calculate_domain_similarity("美髪処 縁‐ENISHI‐", "https://hairenishi.jp/")
    
    print(f"企業名: 美髪処 縁‐ENISHI‐")
    print(f"ドメイン: hairenishi.jp")
    print(f"旧方式類似度: {old_similarity:.1f}%")
    print(f"新方式類似度: {new_similarity:.1f}%")
    print(f"改善効果: +{new_similarity - old_similarity:.1f}%")
    print()
    
    # octo hair テスト
    print("🔍 octo hair テスト（該当なし期待）")
    print("=" * 40)
    
    octo_company = CompanyInfo(
        id="test2",
        company_name="octo hair",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    # 問題のocto-takao.jp（東京都・タイムアウト）
    octo_result = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
        rank=1
    )
    
    octo_score = scorer.calculate_score(octo_result, octo_company, "テストクエリ")
    print(f"🔗 URL: {octo_result.url}")
    print(f"📊 総合スコア: {octo_score.total_score}点")
    print(f"🏆 判定: {octo_score.judgment}")
    print(f"🔍 類似度: {octo_score.domain_similarity:.1f}%")
    print(f"📋 詳細: {octo_score.score_details}")
    
    if octo_score.total_score < 5:
        print("   ✅ 修正成功！該当なしに適切に判定")
    else:
        print("   ❌ まだ問題あり：高スコアになってしまう")

def test_domain_similarity_comparison():
    """ドメイン類似度の新旧比較"""
    print("\n🧪 ドメイン類似度 新旧比較テスト")
    print("=" * 50)
    
    config = ScoringConfig()
    scorer = HPScorer(config=config)
    
    test_cases = [
        ("美髪処 縁‐ENISHI‐", "hairenishi.jp"),
        ("EIGHT sakae", "eights8.co.jp"),  
        ("octo hair", "octo-takao.jp"),
        ("縁", "hairenishi.jp"),
        ("ENISHI", "hairenishi.jp")
    ]
    
    for company_name, domain in test_cases:
        url = f"https://{domain}/"
        new_similarity = scorer._calculate_domain_similarity(company_name, url)
        
        print(f"企業名: {company_name}")
        print(f"ドメイン: {domain}")
        print(f"新方式類似度: {new_similarity:.1f}%")
        print()

# 旧方式の類似度計算（比較用）
def _calculate_domain_similarity_old(company_name: str, url: str) -> float:
    """旧方式のドメイン類似度計算（比較用）"""
    try:
        from rapidfuzz import fuzz
        from src.utils import URLUtils, StringUtils
        
        url_utils = URLUtils()
        string_utils = StringUtils()
        
        cleaned_name = string_utils.clean_company_name(company_name)
        domain = url_utils.get_domain(url)
        domain_without_tld = domain.split('.')[0]
        
        # 単純なfuzz比較のみ
        similarity = fuzz.ratio(cleaned_name.lower(), domain_without_tld.lower())
        return float(similarity)
        
    except Exception:
        return 0.0

# 旧方式追加は不要（関数として直接呼び出し）

if __name__ == "__main__":
    test_enhanced_scoring()
    test_domain_similarity_comparison() 