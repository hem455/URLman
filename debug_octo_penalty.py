#!/usr/bin/env python3
"""
octo hair の地域ミスマッチペナルティが効かない理由をデバッグ
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from src.search_agent import SearchResult, CompanyInfo
from src.scorer import HPScorer, ScoringConfig
from src.web_content_analyzer import WebContentAnalyzer

def debug_octo_penalty():
    print("🔍 octo hair 地域ミスマッチペナルティ デバッグ")
    print("=" * 60)
    
    # テスト用企業情報
    octo_company = CompanyInfo(
        id="test2",
        company_name="octo hair",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    # 問題のURL
    octo_result = SearchResult(
        url="https://octo-takao.jp/",
        title="octo hair - 美容室",
        description="octo hairです。カット・カラー・パーマ等のヘアサロンサービス",
        rank=1
    )
    
    print(f"🏢 企業: {octo_company.company_name}")
    print(f"🎯 目標県: {octo_company.prefecture}")
    print(f"🔗 URL: {octo_result.url}")
    print()
    
    # 1. Webページ解析を直接テスト
    print("📋 Step 1: Webページ解析テスト")
    analyzer = WebContentAnalyzer(timeout=5)
    location_info = analyzer.extract_location_info(octo_result.url)
    
    print(f"   検出県: {location_info.prefecture}")
    print(f"   信頼度: {location_info.confidence_level}")
    print(f"   抽出方法: {location_info.extraction_method}")
    print(f"   詳細: {location_info}")
    print()
    
    # 2. 地域ミスマッチペナルティ計算を直接テスト
    print("📋 Step 2: 地域ミスマッチペナルティ計算テスト")
    config = ScoringConfig()
    scorer = HPScorer(config=config)
    
    mismatch_penalty = scorer._calculate_geographic_mismatch_penalty(octo_result, octo_company)
    print(f"   計算されたペナルティ: {mismatch_penalty}点")
    print()
    
    # 3. フルスコアリングテスト
    print("📋 Step 3: フルスコアリングテスト")
    full_score = scorer.calculate_score(octo_result, octo_company, "テストクエリ")
    
    print(f"   総合スコア: {full_score.total_score}点")
    print(f"   判定: {full_score.judgment}")
    print(f"   詳細: {full_score.score_details}")
    print()
    
    # 4. 個別要素の分析
    print("📋 Step 4: 個別要素分析")
    print(f"   top_page: {full_score.score_details.get('top_page', 0)}")
    print(f"   domain_similarity_score: {full_score.score_details.get('domain_similarity_score', 0)}")
    print(f"   tld_score: {full_score.score_details.get('tld_score', 0)}")
    print(f"   search_rank: {full_score.score_details.get('search_rank', 0)}")
    print(f"   locality: {full_score.score_details.get('locality', 0)}")
    print(f"   geographic_mismatch_penalty: {full_score.score_details.get('geographic_mismatch_penalty', 0)}")
    print(f"   reachability_penalty: {full_score.score_details.get('reachability_penalty', 0)}")
    print()
    
    # 5. 改善提案
    print("📋 Step 5: 改善提案")
    expected_penalty = -8 if location_info.confidence_level == "high" else -5
    current_total = full_score.total_score
    improved_total = current_total + expected_penalty
    
    print(f"   期待ペナルティ: {expected_penalty}点")
    print(f"   現在の総合: {current_total}点")
    print(f"   改善後期待: {improved_total}点")
    
    if improved_total <= 0:
        print("   ✅ 改善後は「該当なし」になる見込み")
    else:
        print("   ❌ まだ改善が必要")

if __name__ == "__main__":
    debug_octo_penalty() 