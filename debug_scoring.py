#!/usr/bin/env python3
"""
スコアリングアルゴリズムのデバッグ用スクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src import utils as _utils
from src.search_agent import CompanyInfo, SearchResult
from src.scorer import create_scorer_from_config
from src.utils import BlacklistChecker


def debug_scoring():
    """スコアリングの詳細を調査する"""
    print("=" * 60)
    print()
    
    # 設定読み込み
    config_manager = _utils.ConfigManager()
    config = config_manager.load_config()
    
    # スコアリングエンジン初期化  
    blacklist_checker = BlacklistChecker("config/blacklist.yaml")
    scorer = create_scorer_from_config(config, blacklist_checker)
    
    # テストケース1: en-te:am
    print("📊 ケース 1: en-te:am")
    print("🔗 URL: https://en-te.jp/")
    print("-" * 40)
    
    company = CompanyInfo(
        id="7626",
        company_name="en-te:am",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    search_result = SearchResult(
        url="https://en-te.jp/",
        title="en-te:am【エンテーアム】愛知県名古屋市東区の美容室・美容院",
        description="名古屋市東区の美容室en-te:am【エンテーアム】。カット、カラー、パーマなど",
        rank=1
    )
    
    hp_candidate = scorer.calculate_score(search_result, company, "基本情報組み合わせ")
    
    if hp_candidate:
        print(f"🎯 総合スコア: {hp_candidate.total_score}点")
        print(f"📈 判定: {hp_candidate.judgment}")
        print(f"🔍 類似度: {hp_candidate.domain_similarity:.1f}%")
        print(f"📄 詳細スコア: {hp_candidate.score_details}")
    else:
        print("❌ スコア計算失敗")
    
    print()
    if hp_candidate:
        print("📋 スコア項目別詳細:")
        for key, value in hp_candidate.score_details.items():
            print(f"   {key}: {value}点")
    
    print()
    print("🔗 URL分析:")
    print(f"   ドメイン: en-te.jp")
    print(f"   パス: /")
    print(f"   TLD: jp")
    
    print()
    print("=" * 60)
    print()
    
    # テストケース2: EIGHT sakae
    print("📊 ケース 2: EIGHT sakae 栄店")
    print("🔗 URL: https://eights8.co.jp/shop/eight-sakae/")
    print("-" * 40)
    
    company2 = CompanyInfo(
        id="7627",
        company_name="EIGHT sakae 栄店 【エイト】",
        prefecture="愛知県",
        industry="ヘアサロン"
    )
    
    search_result2 = SearchResult(
        url="https://eights8.co.jp/shop/eight-sakae/",
        title="EIGHT sakae 栄店【エイト】│愛知県名古屋市中区の美容院・美容室・ヘアサロン",
        description="愛知県名古屋市中区栄のヘアサロンEIGHT sakae 栄店【エイト】。カット、カラー、パーマなど",
        rank=1
    )
    
    hp_candidate2 = scorer.calculate_score(search_result2, company2, "基本情報組み合わせ")
    
    if hp_candidate2:
        print(f"🎯 総合スコア: {hp_candidate2.total_score}点")
        print(f"📈 判定: {hp_candidate2.judgment}")
        print(f"🔍 類似度: {hp_candidate2.domain_similarity:.1f}%")
        print(f"📄 詳細スコア: {hp_candidate2.score_details}")
        
        print()
        print("📋 スコア項目別詳細:")
        for key, value in hp_candidate2.score_details.items():
            print(f"   {key}: {value}点")
    else:
        print("❌ スコア計算失敗")
    
    print()
    print("🔗 URL分析:")
    print(f"   ドメイン: eights8.co.jp")
    print(f"   パス: /shop/eight-sakae/")
    print(f"   TLD: jp")
    
    print()
    print("=" * 60)
    
    # 設定確認
    print("⚙️ 現在の設定:")
    scoring_config = config['scoring_logic']
    weights = scoring_config['weights']
    print(f"   JP domain penalty: {weights['domain_jp_penalty']}")
    print(f"   Similarity threshold: {scoring_config['similarity_threshold_domain']}")
    print(f"   Domain similarity weight: {weights['domain_similarity']}")
    print(f"   TLD score enabled: {weights.get('tld_match', 'N/A')}")


if __name__ == "__main__":
    debug_scoring() 