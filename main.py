#!/usr/bin/env python3
"""
🚀 会社HP自動検索・貼り付けツール - メイン実行ファイル

Google Sheetsから企業データを読み込み、HP URLを自動検索・スコアリングして結果を書き込みます。

使用方法:
    python main.py

機能:
    1. Google Sheetsから企業データを読み込み
    2. Brave Search APIで各企業のHP URLを検索
    3. インテリジェントスコアリングで信頼度を判定
    4. 結果をGoogle Sheetsに自動書き込み
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / "src"))

from src.utils import ConfigManager, BlacklistChecker
from src.data_loader import create_data_loader_from_config, SheetConfig
from src.search_agent import BraveSearchClient, QueryGenerator
from src.scorer import create_scorer_from_config  
from src.output_writer import create_output_writer_from_config
from src.logger_config import get_logger

logger = get_logger(__name__)

def print_banner():
    """アプリケーションバナー表示"""
    print("🚀 会社HP自動検索・貼り付けツール")
    print("=" * 60)
    print("📋 Google Sheets統合による完全自動化システム")
    print("🎯 スコアリング精度: 11点（自動採用）達成")
    print("=" * 60)
    print()

def print_status(step: str, message: str, success: bool = None):
    """ステータス表示"""
    if success is True:
        print(f"✅ {step}: {message}")
    elif success is False:
        print(f"❌ {step}: {message}")
    else:
        print(f"🔍 {step}: {message}")

async def main():
    """メイン処理"""
    try:
        print_banner()
        
        # 1. 設定読み込み
        print_status("1. 設定読み込み", "設定ファイルを読み込んでいます...")
        config_manager = ConfigManager()
        config = config_manager.load_config()
        print_status("1. 設定読み込み", "設定読み込み完了", True)
        
        # 2. 各コンポーネント初期化
        print_status("2. システム初期化", "各コンポーネントを初期化しています...")
        
        # データローダー
        data_loader = create_data_loader_from_config(config)
        
        # Brave Search クライアント
        brave_api_config = config.get('brave_api', {})
        brave_client = BraveSearchClient(
            api_key=brave_api_config.get('api_key'),
            results_per_query=brave_api_config.get('results_per_query', 10)
        )
        
        # スコアラー
        blacklist_checker = BlacklistChecker("config/blacklist.yaml")
        scorer = create_scorer_from_config(config, blacklist_checker)
        
        # 出力ライター
        output_writer = create_output_writer_from_config(config)
        
        print_status("2. システム初期化", "システム初期化完了", True)
        
        # 3. 企業データ読み込み
        print_status("3. データ読み込み", "Google Sheetsから企業データを読み込んでいます...")
        
        google_sheets_config = config.get('google_sheets', {})
        sheet_config = SheetConfig(
            service_account_file=google_sheets_config.get('service_account_file'),
            spreadsheet_id=google_sheets_config.get('input_spreadsheet_id'),
            sheet_name=google_sheets_config.get('input_sheet_name', 'シート1'),
            input_columns=google_sheets_config.get('input_columns', {
                'id': 'A',
                'prefecture': 'B', 
                'industry': 'C',
                'company_name': 'D'
            }),
            start_row=google_sheets_config.get('start_row', 2),
            end_row=google_sheets_config.get('end_row', None)
        )
        
        companies = data_loader.load_companies_from_range(sheet_config)
        
        if not companies:
            print_status("3. データ読み込み", "読み込む企業データがありません", False)
            return 1
        
        print_status("3. データ読み込み", f"{len(companies)}社のデータを読み込み完了", True)
        for i, company in enumerate(companies, 1):
            print(f"   {i}. {company.company_name} ({company.id}) - {company.prefecture} {company.industry}")
        print()
        
        # 4. 検索・スコアリング実行
        print_status("4. 検索・スコアリング", "各企業のHP URLを検索・スコアリングしています...")
        print()
        
        results_to_write = []
        successful_count = 0
        
        for i, company in enumerate(companies, 1):
            print(f"💼 企業 {i}/{len(companies)}: {company.company_name}")
            
            try:
                # 地域特定強化クエリで検索
                query = QueryGenerator.generate_location_enhanced_query(company)
                print(f"📝 検索クエリ: {query}")
                
                # 検索実行
                search_results = brave_client.search(query)
                print(f"📋 検索結果: {len(search_results)}件")
                
                if search_results:
                    # スコアリング（全件実行）
                    scored_results = []
                    for result in search_results:  # 全件（最大10件）をスコアリング
                        scored = scorer.calculate_score(result, company, "地域特定強化クエリ")
                        if scored:
                            scored_results.append(scored)
                    
                    if scored_results:
                        best = max(scored_results, key=lambda x: x.total_score)
                        print(f"🏆 ベスト: {best.url}")
                        print(f"📊 スコア: {best.total_score}点 - {best.judgment}")
                        print(f"🔍 類似度: {best.domain_similarity:.1f}%")
                        
                        # HeadMatchボーナスの詳細表示（タイトルのみ版）
                        head_match_score = best.score_details.get('head_match_bonus', 0)
                        if head_match_score != 0:
                            print(f"🔥 HeadMatch(タイトル): {head_match_score:+d}点")
                        
                        # その他の主要スコア詳細
                        print(f"📊 詳細: top={best.score_details.get('top_page', 0)} domain={best.score_details.get('domain_similarity_score', 0)} head={head_match_score} portal={best.score_details.get('portal_penalty', 0)} rank={best.score_details.get('search_rank', 0)}")
                        
                        successful_count += 1
                        
                        # 書き込み用データ準備
                        results_to_write.append({
                            'company': company,
                            'company_id': company.id,
                            'url': best.url,
                            'score': best.total_score,
                            'status': best.judgment,
                            'query': query,
                            'similarity': best.domain_similarity,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                    else:
                        print("❌ 有効なスコア結果なし")
                        results_to_write.append({
                            'company': company,
                            'company_id': company.id,
                            'url': '',
                            'score': 0,
                            'status': '検索失敗',
                            'query': query,
                            'similarity': 0.0,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                else:
                    print("❌ 検索結果なし")
                    results_to_write.append({
                        'company': company,
                        'company_id': company.id,
                        'url': '',
                        'score': 0,
                        'status': '検索結果なし',
                        'query': query,
                        'similarity': 0.0,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # API制限考慮
                await asyncio.sleep(1.5)
                
            except Exception as e:
                logger.error(f"企業 {company.company_name} の処理でエラー: {e}")
                print(f"❌ エラー: {e}")
                results_to_write.append({
                    'company': company,
                    'company_id': company.id,
                    'url': '',
                    'score': 0,
                    'status': f'エラー',
                    'query': '',
                    'similarity': 0.0,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            print()
        
        print_status("4. 検索・スコアリング", f"処理完了（成功: {successful_count}/{len(companies)}社）", True)
        
        # 5. 結果書き込み
        print_status("5. 結果書き込み", "Google Sheetsに結果を書き込んでいます...")
        
        for i, result in enumerate(results_to_write):
            try:
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
                    print(f"✅ {result['company'].company_name}: 書き込み完了")
                else:
                    print(f"❌ {result['company'].company_name}: 書き込み失敗")
                
                # 書き込み間隔
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"書き込みエラー ({result['company'].company_name}): {e}")
                print(f"❌ {result['company'].company_name}: 書き込み失敗")
        
        print_status("5. 結果書き込み", "書き込み完了", True)
        
        # 6. 実行結果サマリー
        print()
        print("=" * 60)
        print("📊 実行結果サマリー:")
        print(f"💼 対象企業: {len(companies)}社")
        print(f"✅ 成功企業: {successful_count}社")
        print(f"📈 成功率: {(successful_count/len(companies)*100):.1f}%")
        
        if successful_count > 0:
            auto_adopt_count = sum(1 for r in results_to_write if r['status'] == '自動採用')
            review_count = sum(1 for r in results_to_write if r['status'] == '要確認')
            manual_count = sum(1 for r in results_to_write if r['status'] == '手動確認')
            
            print(f"🎯 自動採用: {auto_adopt_count}社")
            print(f"⚠️ 要確認: {review_count}社")
            print(f"🔍 手動確認: {manual_count}社")
            
            if results_to_write:
                valid_scores = [r['score'] for r in results_to_write if r['score'] > 0]
                if valid_scores:
                    avg_score = sum(valid_scores) / len(valid_scores)
                    print(f"📊 平均スコア: {avg_score:.1f}点")
                    
                valid_similarities = [r['similarity'] for r in results_to_write if r['similarity'] > 0]
                if valid_similarities:
                    avg_similarity = sum(valid_similarities) / len(valid_similarities)
                    print(f"🔍 平均類似度: {avg_similarity:.1f}%")
        
        print("=" * 60)
        print("🎉 処理が完了しました！Google Sheetsで結果を確認してください。")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ 処理が中断されました")
        return 1
    except Exception as e:
        logger.error(f"メイン処理でエラー: {e}", exc_info=True)
        print(f"❌ エラーが発生しました: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ 処理が中断されました")
        sys.exit(1) 