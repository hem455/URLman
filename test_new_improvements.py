#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新機能テスト：A-E改善の効果確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scorer import HPScorer, ScoringConfig
from src.search_agent import SearchResult, CompanyInfo
from src.url_utils import URLUtils

def test_portal_exclusion():
    """A. ポータル除外リスト（-100点）"""
    print("🔥 A. ポータル除外リスト テスト")
    
    scorer = HPScorer(ScoringConfig(), set(), [])
    
    test_cases = [
        "https://beauty.rakuten.co.jp/s0000045369/",
        "https://beauty.hotpepper.jp/slnH000123456/",
        "https://minimodel.jp/salon/123",
        "https://amazon.co.jp/products",
        "https://facebook.com/pages/salon"
    ]
    
    for url in test_cases:
        penalty = scorer._get_enhanced_portal_penalty(url)
        print(f"   {url} → {penalty}点")
    print()

def test_generic_word_penalty():
    """B. 汎用語ペナルティ"""
    print("🔥 B. 汎用語ペナルティ テスト")
    
    scorer = HPScorer(ScoringConfig(), set(), [])
    
test_cases = [
         ("HAIR SALON Pro", "https://hair-salon.com/"),  # 汎用語のみ
        ("HAIR GROUP", "https://hair-group.com/"),      # 汎用語のみ  
         ("美髪処 縁‐ENISHI‐", "https://hairenishi.jp/"), # 非汎用語あり
         ("ARCHI HAIR", "https://axis-hair.com/"),        # 非汎用語あり
     ]
    
    for company_name, url in test_cases:
        penalty = scorer._calculate_generic_word_penalty(company_name, url)
        print(f"   '{company_name}' vs {url} → {penalty}点")
    print()

def test_tld_reform():
    """C. TLDスコア撤廃"""
    print("🔥 C. TLDスコア撤廃 テスト")
    
    scorer = HPScorer(ScoringConfig(), set(), [])
    
    test_cases = [
        "https://example.co.jp/",      # 従来+3点 → 0点
        "https://example.com/",        # 従来+1点 → 0点
        "https://example.jp/",         # 従来-2点 → 0点
        "https://spam.tk/",            # 怪しいTLD → -3点
        "https://fake.xyz/",           # 怪しいTLD → -3点
    ]
    
    for url in test_cases:
        score = scorer._get_tld_score(url)
        print(f"   {url} → {score}点")
    print()

def test_head_match_bonus():
    """E. HeadMatchボーナス"""
    print("🔥 E. HeadMatchボーナス テスト")
    
    scorer = HPScorer(ScoringConfig(), set(), [])
    
    test_cases = [
        # 強一致（+5点）
        ("美髪処 縁‐ENISHI‐", "美髪処縁 ENISHI | 公式サイト", "縁の美髪処です"),
        # 弱一致（-3点）  
        ("Eze【エズ】", "全然違う会社のサイト", "不動産業界のリーダー"),
        # 中程度（0点）
        ("HAIR ARCHI", "HAIR STYLING ARCHI", "髪のプロ集団"),
    ]
    
    for company_name, title, description in test_cases:
        search_result = SearchResult(
            url="https://example.com/",
            title=title,
            description=description,
            search_rank=1
        )
        bonus = scorer._calculate_head_match_bonus(company_name, search_result)
        print(f"   '{company_name}' vs '{title}' → {bonus}点")
    print()

def test_full_scoring():
    """統合テスト：実際のスコアリング"""
    print("🔥 統合テスト：新機能効果確認")
    
    scorer = HPScorer(ScoringConfig(), set(), [])
    company = CompanyInfo(
        company_name="美髪処 縁‐ENISHI‐",
        prefecture="愛知県"
    )
    
    # ケース1: 正解（hairenishi.jp）
    correct_result = SearchResult(
        url="https://hairenishi.jp/",
        title="美髪処縁 ENISHI | 愛知県の美髪専門サロン",
        description="美髪処縁ENISHIの公式サイトです",
        search_rank=1
    )
    
    # ケース2: ポータル（rakuten）
    portal_result = SearchResult(
        url="https://beauty.rakuten.co.jp/s0000045369/",
        title="美髪処 縁‐ENISHI‐ - 楽天ビューティー",
        description="美髪処の予約はこちら",
        search_rank=2
    )
    
    candidates = [
        scorer.calculate_score(correct_result, company, "basic"),
        scorer.calculate_score(portal_result, company, "basic")
    ]
    
    for i, candidate in enumerate(candidates, 1):
        if candidate:
            print(f"   ケース{i}: {candidate.url}")
            print(f"      総合スコア: {candidate.total_score}点")
            print(f"      判定: {candidate.judgment}")
            print(f"      詳細: {candidate.score_details}")
            print()

if __name__ == "__main__":
    print("🔥 A-E改善機能テスト開始\n")
    
    test_portal_exclusion()
    test_generic_word_penalty()
    test_tld_reform()
    test_head_match_bonus()
    test_full_scoring()
    
    print("🔥 テスト完了") 