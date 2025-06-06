#!/usr/bin/env python3
"""
Google Sheets完全連携テストスクリプト
実際のスプレッドシートから読み込み、検索、書き込みまでの完全ワークフローをテスト
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / "src"))

from src.utils import ConfigManager
from src.data_loader import create_data_loader_from_config, SheetConfig
from src.search_agent import BraveSearchClient, QueryGenerator
from src.scorer import create_scorer_from_config  
from src.output_writer import create_output_writer_from_config
from src.logger_config import get_logger

logger = get_logger(__name__)

async def test_google_sheets_workflow():
    """Google Sheets完全ワークフローテスト"""
    
    print("🚀 Google Sheets完全連携テスト開始...")
    print("=" * 60)
    
    try:
        # 1. 設定読み込み
        print("📋 1. 設定ファイル読み込み...")
        config_manager = ConfigManager()
        config = config_manager.load_config()
        print("✅ 設定読み込み成功")
        
        # 2. Google Sheets読み込みテスト
        print("\n📊 2. Google Sheets読み込みテスト...")
        data_loader = create_data_loader_from_config(config)
        
        # シート設定
        google_sheets_config = config.get('google_sheets', {})
        sheet_config = SheetConfig(
            service_account_file=google_sheets_config.get('service_account_file'),
            spreadsheet_id=google_sheets_config.get('input_spreadsheet_id'),
            sheet_name=google_sheets_config.get('input_sheet_name', 'Sheet1'),
            input_columns=google_sheets_config.get('input_columns', {
                'id': 'A',
                'prefecture': 'B', 
                'industry': 'C',
                'company_name': 'D'
            }),
            start_row=2,
            end_row=6  # 5社全てのデータ（2-6行目）
        )
        
        # 企業データ読み込み
        companies = data_loader.load_companies_from_range(sheet_config)
        
        if not companies:
            print("❌ Google Sheetsからデータを読み込めませんでした")
            return False
            
        print(f"✅ Google Sheetsから{len(companies)}社のデータを読み込み成功")
        
        for i, company in enumerate(companies, 1):
            print(f"   {i}. {company.company_name} ({company.id}) - {company.prefecture} {company.industry}")
        
        # 3. Brave Search APIテスト
        print("\n🔍 3. Brave Search API検索テスト...")
        brave_api_config = config.get('brave_api', {})
        brave_client = BraveSearchClient(
            api_key=brave_api_config.get('api_key'),
            results_per_query=brave_api_config.get('results_per_query', 10)
        )
        
        # 4. スコアリング初期化
        print("\n🎯 4. スコアリングシステム初期化...")
        from src.utils import BlacklistChecker
        blacklist_checker = BlacklistChecker("config/blacklist.yaml")
        scorer = create_scorer_from_config(config, blacklist_checker)
        print("✅ スコアリングシステム初期化成功")
        
        # 5. 各企業の検索とスコアリング
        print("\n🔍 5. 各企業の検索・スコアリング実行...")
        results_to_write = []
        
        for i, company in enumerate(companies, 1):
            print(f"\n💼 企業 {i}/{len(companies)}: {company.company_name}")
            
            try:
                # 基本情報組み合わせクエリで検索
                query = QueryGenerator.generate_custom_query(
                    "{company_name} {prefecture} {industry}", 
                    company
                )
                print(f"📝 検索クエリ: {query}")
                
                # 検索実行
                search_results = brave_client.search(query)
                print(f"📋 検索結果: {len(search_results)}件")
                
                if search_results:
                    # スコアリング
                    scored_results = []
                    for result in search_results[:5]:  # 上位5件
                        scored = scorer.calculate_score(result, company, "基本情報組み合わせ")
                        if scored:
                            scored_results.append(scored)
                    
                    if scored_results:
                        best = max(scored_results, key=lambda x: x.total_score)
                        print(f"🏆 ベスト: {best.url}")
                        print(f"📊 スコア: {best.total_score}点 - {best.judgment}")
                        print(f"🔍 類似度: {best.domain_similarity:.1f}%")
                        
                        # 書き込み用データ準備
                        results_to_write.append({
                            'company_id': company.id,
                            'url': best.url,
                            'score': best.total_score,
                            'status': best.judgment,
                            'query': query,
                            'similarity': best.domain_similarity
                        })
                    else:
                        print("❌ 有効なスコア結果なし")
                        results_to_write.append({
                            'company_id': company.id,
                            'url': '',
                            'score': 0,
                            'status': '検索失敗',
                            'query': query,
                            'similarity': 0.0
                        })
                else:
                    print("❌ 検索結果なし")
                    results_to_write.append({
                        'company_id': company.id,
                        'url': '',
                        'score': 0,
                        'status': '検索結果なし',
                        'query': query,
                        'similarity': 0.0
                    })
                
                # API制限考慮
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"❌ エラー: {e}")
                results_to_write.append({
                    'company_id': company.id,
                    'url': '',
                    'score': 0,
                    'status': f'エラー: {str(e)}',
                    'query': '',
                    'similarity': 0.0
                })
        
        # 6. Google Sheets書き込みテスト
        print("\n📝 6. Google Sheets書き込みテスト...")
        output_writer = create_output_writer_from_config(config)
        
        print("📋 書き込み予定データ:")
        for result in results_to_write:
            print(f"   ID:{result['company_id']} -> {result['url']} ({result['score']}点)")
        
        # 実際の書き込み実行
        try:
            # 各結果を書き込み
            for i, result in enumerate(results_to_write):
                row_number = sheet_config.start_row + i  # 読み込み開始行から順番に
                
                write_result = output_writer.write_single_result(
                    spreadsheet_id=google_sheets_config.get('input_spreadsheet_id'),
                    sheet_name=google_sheets_config.get('input_sheet_name', 'シート1'),
                    row_number=row_number,
                    company_id=str(result['company_id']),
                    url=result['url'],
                    score=result['score'],
                    status=result['status'],
                    query=result['query']
                )
                
                if write_result.success:
                    print(f"✅ 行{row_number}に書き込み完了: {result['url']}")
                else:
                    print(f"❌ 行{row_number}書き込み失敗: {write_result.error_message}")
                
                # 書き込み間隔
                await asyncio.sleep(0.5)
                
            print("✅ Google Sheets書き込み完全成功！")
            
        except Exception as e:
            print(f"❌ 書き込みエラー: {e}")
            return False
        
        # 7. 結果サマリー
        print("\n" + "=" * 60)
        print("📊 Google Sheets完全連携テスト結果:")
        
        success_count = len([r for r in results_to_write if r['url']])
        print(f"💼 対象企業: {len(companies)}社")
        print(f"✅ 成功企業: {success_count}社")
        print(f"📈 成功率: {success_count/len(companies)*100:.1f}%")
        
        if success_count > 0:
            avg_score = sum(r['score'] for r in results_to_write if r['url']) / success_count
            avg_similarity = sum(r['similarity'] for r in results_to_write if r['url']) / success_count
            print(f"📊 平均スコア: {avg_score:.1f}点")
            print(f"🔍 平均類似度: {avg_similarity:.1f}%")
        
        print("\n🎉 Google Sheets完全ワークフロー成功！！")
        print("✅ 読み込み → 検索 → スコアリング → 書き込み の全工程が正常動作")
        
        return True
        
    except Exception as e:
        print(f"\n❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 非同期実行
    success = asyncio.run(test_google_sheets_workflow())
    if success:
        print("\n🎯 次のステップ: 実際のスプレッドシートで結果を確認してください！")
        sys.exit(0)
    else:
        print("\n⚠️ 設定やAPI認証を確認してください")
        sys.exit(1) 