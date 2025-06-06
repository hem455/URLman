#!/usr/bin/env python3
"""
フェーズ1クエリテスト支援スクリプト実行ファイル
"""

import os
import sys
import asyncio
from pathlib import Path

# パッケージ化されたプロジェクトのため、src prefixで統一
from src import phase1_query_test
from src import utils as src_utils

async def main():
    """メイン実行関数"""
    
    # 設定ファイルチェック
    project_root = Path(__file__).parent
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        print("❌ エラー: config/config.yaml が見つかりません")
        print("📋 作成手順:")
        print("  Copy-Item config\\config.yaml.example config\\config.yaml")
        print("  その後、APIキーを設定してください")
        return 1
    
    # 環境変数チェック
    if not os.getenv("BRAVE_SEARCH_API_KEY"):
        print("❌ エラー: BRAVE_SEARCH_API_KEY 環境変数が設定されていません")
        print("📋 設定手順 (PowerShell):")
        print("  $env:BRAVE_SEARCH_API_KEY = \"YOUR_API_KEY\"")
        return 1
    
    print("🚀 フェーズ1クエリテスト支援スクリプトを開始します...")
    print("=" * 60)
    
    try:
        # 設定読み込み
        config_manager = src_utils.ConfigManager(str(config_path))
        config = config_manager.load_config()
        
        # テスター初期化
        tester = phase1_query_test.Phase1QueryTester(config)
        
        # サンプル企業データ（テスト用）
        sample_companies = [
            {
                "id": "7610",
                "company_name": "LOREN 栄久屋大通店【ローレン】",
                "prefecture": "愛知県", 
                "industry": "ヘアサロン"
            },
            {
                "id": "7611",
                "company_name": "tano【タノ】",
                "prefecture": "愛知県",
                "industry": "ヘアサロン"
            },
            {
                "id": "7612", 
                "company_name": "NORTY【ノーティー】",
                "prefecture": "愛知県",
                "industry": "ヘアサロン"
            },
            {
                "id": "7613",
                "company_name": "giulietta【ジュリエッタ】", 
                "prefecture": "愛知県",
                "industry": "ヘアサロン"
            },
            {
                "id": "7614",
                "company_name": "SALON・GRECO",
                "prefecture": "愛知県", 
                "industry": "ヘアサロン"
            }
        ]
        
        print("📊 テスト対象企業:")
        for i, company in enumerate(sample_companies, 1):
            print(f"{i}. {company['company_name']} (ID: {company['id']})")
        print("-" * 60)
        
        # 複数企業での実際のAPI検索テスト
        print("🔍 複数企業での実際のAPI検索を実行中...")
        
        # 各企業に対してクエリテスト実行
        from src.search_agent import QueryGenerator, CompanyInfo
        overall_results = []
        
        for i, company in enumerate(sample_companies, 1):
            print(f"\n💼 企業 {i}/{len(sample_companies)}: {company['company_name']}")
            print(f"📍 所在地: {company['prefecture']}")
            print(f"🏭 業種: {company['industry']}")
            print("-" * 60)
            
            company_info = CompanyInfo(
                id=company["id"],
                company_name=company["company_name"],
                prefecture=company["prefecture"],
                industry=company["industry"]
            )
            
            # 最適化されたクエリパターン（基本情報組み合わせに特化）
            query_patterns = [
                ("{company_name} {prefecture} {industry}", "基本情報組み合わせ")
            ]
            
            company_results = []
            
            for pattern_template, pattern_name in query_patterns:
                print(f"\n🔍 パターン: {pattern_name}")
                query = QueryGenerator.generate_custom_query(pattern_template, company_info)
                print(f"📝 検索クエリ: {query}")
                
                try:
                    # Brave Search実行
                    search_results = tester.brave_client.search(query)
                    print(f"📋 検索結果: {len(search_results)}件取得")
                    
                    if search_results:
                        # 各結果をスコアリング
                        scored_results = []
                        for result in search_results[:5]:  # 上位5件をチェック
                            scored = tester.scorer.calculate_score(result, company_info, pattern_name)
                            if scored:
                                scored_results.append(scored)
                        
                        if scored_results:
                            best = max(scored_results, key=lambda x: x.total_score)
                            print(f"🏆 ベスト: {best.url}")
                            print(f"📊 スコア: {best.total_score}点 - {best.judgment}")
                            print(f"🔍 類似度: {best.domain_similarity:.1f}%")
                            
                            company_results.append({
                                "pattern": pattern_name,
                                "query": query,
                                "best_result": {
                                    "url": best.url,
                                    "score": best.total_score,
                                    "judgment": best.judgment,
                                    "similarity": best.domain_similarity
                                },
                                "total_found": len(scored_results)
                            })
                        else:
                            print("❌ 有効なスコア結果なし")
                            company_results.append({
                                "pattern": pattern_name,
                                "query": query,
                                "best_result": None,
                                "total_found": 0
                            })
                    else:
                        print("❌ 検索結果が見つかりませんでした")
                        company_results.append({
                            "pattern": pattern_name,
                            "query": query,
                            "best_result": None,
                            "total_found": 0
                        })
                        
                    # API制限を考慮して少し待機
                    await asyncio.sleep(1.5)
                    
                except Exception as e:
                    print(f"❌ エラー: {e}")
                    company_results.append({
                        "pattern": pattern_name,
                        "query": query,
                        "best_result": None,
                        "total_found": 0,
                        "error": str(e)
                    })
            
            # 企業全体のベスト結果
            all_best_results = [r["best_result"] for r in company_results if r["best_result"]]
            overall_best = None
            if all_best_results:
                overall_best = max(all_best_results, key=lambda x: x["score"])
                print(f"\n🎯 この企業の総合ベスト:")
                print(f"   URL: {overall_best['url']}")
                print(f"   スコア: {overall_best['score']}点 - {overall_best['judgment']}")
                print(f"   類似度: {overall_best['similarity']:.1f}%")
            
            overall_results.append({
                "company": company,
                "results": company_results,
                "overall_best": overall_best
            })
            
            print("=" * 60)
        
        # 全体サマリー
        print(f"\n📊 全体結果サマリー:")
        successful_companies = len([r for r in overall_results if r["overall_best"]])
        print(f"💼 対象企業: {len(sample_companies)}社")
        print(f"✅ 成功企業: {successful_companies}社")
        print(f"📈 成功率: {successful_companies/len(sample_companies)*100:.1f}%")
        
        # 最適化パターンの詳細分析
        print(f"\n📋 基本情報組み合わせパターンの詳細分析:")
        high_confidence = 0  # 9点以上（自動採用）
        medium_confidence = 0  # 6-8点（要確認）
        low_confidence = 0  # 5点以下（手動確認）
        
        for company_result in overall_results:
            if company_result["overall_best"]:
                score = company_result["overall_best"]["score"]
                if score >= 9:
                    high_confidence += 1
                elif score >= 6:
                    medium_confidence += 1
                else:
                    low_confidence += 1
        
        print(f"   🟢 自動採用（9点以上）: {high_confidence}/{len(sample_companies)} ({high_confidence/len(sample_companies)*100:.1f}%)")
        print(f"   🟡 要確認（6-8点）: {medium_confidence}/{len(sample_companies)} ({medium_confidence/len(sample_companies)*100:.1f}%)")
        print(f"   🔴 手動確認（5点以下）: {low_confidence}/{len(sample_companies)} ({low_confidence/len(sample_companies)*100:.1f}%)")
        
        # ドメイン類似度の分析
        similarities = [r["overall_best"]["similarity"] for r in overall_results if r["overall_best"]]
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            print(f"\n📊 平均ドメイン類似度: {avg_similarity:.1f}%")
            print(f"📊 類似度範囲: {min(similarities):.1f}% - {max(similarities):.1f}%")
        
        # モックテスト（従来通り）も実行
        print("\n" + "=" * 60)
        print("🧪 モックテスト（参考比較用）:")
        test_url = "https://granthope.jp/"
        print(f"🔍 テストURL: {test_url}")
        
        # SearchResultオブジェクトを作成
        from src.search_agent import SearchResult
        search_result = SearchResult(
            url=test_url,
            title="グラントホープ株式会社",
            description="グラントホープ株式会社の公式サイト",
            rank=1
        )
        
        score_result = tester.scorer.calculate_score(search_result, company_info, "test_pattern")
        if score_result:
            print(f"📊 スコア結果: {score_result.total_score}点 - {score_result.judgment}")
            print(f"🔍 ドメイン類似度: {score_result.domain_similarity:.1f}%")
            print(f"📄 スコア詳細: {score_result.score_details}")
        else:
            print("❌ スコア計算に失敗しました")
        
        results = {
            "success": True, 
            "test_score": score_result.total_score if score_result else 0, 
            "test_judgment": score_result.judgment if score_result else "失敗",
            "domain_similarity": score_result.domain_similarity if score_result else 0.0,
            "api_results_count": len(search_results) if 'search_results' in locals() else 0
        }
        
        print("✅ テスト完了！")
        print(f"📄 結果ファイル: {results.get('output_file', 'N/A')}")
        
        return 0
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return 1

def setup_environment():
    """環境セットアップの説明を表示"""
    print("🔧 環境セットアップガイド")
    print("=" * 40)
    print("1. 設定ファイルのコピー:")
    print("   Copy-Item config\\*.example config\\")
    print("   (拡張子の .example を削除)")
    print("")
    print("2. APIキー設定:")
    print("   - config/config.yaml の brave_search.api_key を設定")
    print("   - または環境変数 BRAVE_SEARCH_API_KEY を設定")
    print("")
    print("3. Google Sheets API設定:")
    print("   - Google Cloud Consoleでサービスアカウント作成")
    print("   - JSONキーファイルをダウンロード")
    print("   - config/config.yaml の google_sheets.service_account_file に配置")
    print("")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        setup_environment()
        sys.exit(0)
    
    # 非同期実行
    result = asyncio.run(main())
    sys.exit(result) 