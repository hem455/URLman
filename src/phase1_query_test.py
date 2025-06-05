"""
フェーズ1: クエリテスト支援スクリプト
3つのクエリパターンで検索を実行し、結果を詳細に出力
"""

import asyncio
import aiohttp
import sys
import traceback
from typing import List, Dict, Any, Optional, NamedTuple
from pathlib import Path
import json

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent))

from .logger_config import get_logger
from .utils import ConfigManager, BlacklistChecker
from .search_agent import BraveSearchClient, CompanyInfo, QueryGenerator, SearchAgent
from .data_loader import DataLoader, SheetConfig, create_data_loader_from_config
from .output_writer import OutputWriter, create_output_writer_from_config
from .scorer import HPScorer, create_scorer_from_config

logger = get_logger(__name__)

class QueryPattern(NamedTuple):
    """クエリパターンを表すデータクラス"""
    name: str
    template: str
    description: str

class Phase1QueryTester:
    """フェーズ1クエリテスタークラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.config_manager = ConfigManager(config)
        
        # 各コンポーネントを初期化
        self.blacklist_checker = BlacklistChecker(config)
        
        # Brave Search Client の初期化
        brave_api_config = config.get('brave_api', {})
        self.brave_client = BraveSearchClient(
            api_key=brave_api_config.get('api_key'),
            results_per_query=brave_api_config.get('results_per_query', 10)
        )
        
        # Search Agent の初期化
        self.search_agent = SearchAgent(self.brave_client)
        
        self.data_loader = create_data_loader_from_config(config)
        self.output_writer = create_output_writer_from_config(config)
        self.scorer = create_scorer_from_config(config, self.blacklist_checker)
        
        # フェーズ1用の3つのクエリパターンを定義
        self.query_patterns = [
            QueryPattern(
                name="基本情報組み合わせ",
                template="{company_name} {prefecture} {industry}",
                description="企業名、都道府県、業種の組み合わせ"
            ),
            QueryPattern(
                name="公式サイト指定", 
                template="{company_name} 公式サイト",
                description="企業名 + 公式サイトキーワード"
            ),
            QueryPattern(
                name="ドメイン限定検索",
                template="\"{company_name}\" site:.co.jp OR site:.com",
                description="企業名の完全一致 + ドメイン限定"
            )
        ]
    
    async def run_query_test(self, 
                           spreadsheet_id: str,
                           sheet_name: str,
                           start_row: int = 2,
                           end_row: Optional[int] = None,
                           max_companies: int = 10) -> Dict[str, Any]:
        """
        クエリテスト実行
        
        Args:
            spreadsheet_id: スプレッドシートID
            sheet_name: シート名
            start_row: 開始行
            end_row: 終了行
            max_companies: 最大処理企業数
        
        Returns:
            テスト結果の詳細
        """
        try:
            logger.info("=== フェーズ1 クエリテスト開始 ===")
            
            # 企業データ読み込み
            companies = await self._load_test_companies(
                spreadsheet_id, sheet_name, start_row, end_row, max_companies
            )
            
            if not companies:
                logger.error("テスト対象企業が見つかりませんでした")
                return {"success": False, "error": "No companies found"}
            
            logger.info(f"テスト対象企業: {len(companies)}社")
            
            # 各企業に対してクエリテスト実行
            test_results = []
            
            for i, company in enumerate(companies):
                logger.info(f"--- 企業 {i+1}/{len(companies)}: {company.company_name} ({company.id}) ---")
                
                company_result = await self._test_company_queries(company)
                test_results.append(company_result)
                
                # 適度な間隔を置く
                await asyncio.sleep(0.5)
            
            # 結果サマリー生成
            summary = self._generate_test_summary(test_results)
            
            logger.info("=== フェーズ1 クエリテスト完了 ===")
            return {
                "success": True,
                "summary": summary,
                "detailed_results": test_results
            }
            
        except Exception as e:
            logger.error(f"クエリテスト実行エラー: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _load_test_companies(self, 
                                 spreadsheet_id: str,
                                 sheet_name: str,
                                 start_row: int,
                                 end_row: Optional[int],
                                 max_companies: int) -> List[CompanyInfo]:
        """テスト対象企業の読み込み"""
        try:
            # シート設定作成
            google_sheets_config = self.config.get('google_sheets', {})
            sheet_config = SheetConfig(
                service_account_file=google_sheets_config.get('service_account_file'),
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                input_columns=google_sheets_config.get('input_columns', {
                    'id': 'A',
                    'prefecture': 'B', 
                    'industry': 'C',
                    'company_name': 'D'
                }),
                start_row=start_row,
                end_row=end_row
            )
            
            # 企業データ読み込み
            companies = self.data_loader.load_companies_from_range(sheet_config)
            
            # 最大数制限
            if len(companies) > max_companies:
                companies = companies[:max_companies]
                logger.info(f"企業数を{max_companies}社に制限しました")
            
            return companies
            
        except Exception as e:
            logger.error(f"企業データ読み込みエラー: {e}")
            return []
    
    async def _test_company_queries(self, company: CompanyInfo) -> Dict[str, Any]:
        """1企業に対する全クエリテスト"""
        try:
            company_result = {
                "company": {
                    "id": company.id,
                    "name": company.company_name,
                    "prefecture": company.prefecture,
                    "industry": company.industry
                },
                "query_results": [],
                "best_overall": None
            }
            
            all_scored_urls = []
            
            # 各クエリパターンでテスト
            for pattern in self.query_patterns:
                logger.info(f"  クエリパターン: {pattern.name}")
                
                try:
                    # クエリ生成
                    query_text = QueryGenerator.generate_custom_query(pattern.template, company)
                    logger.info(f"  生成クエリ: {query_text}")
                    
                    # 検索実行
                    search_results = self.brave_client.search(query_text)
                    
                    if not search_results:
                        logger.warning(f"  検索結果なし: {pattern.name}")
                        company_result["query_results"].append({
                            "pattern": pattern._asdict(),
                            "query_text": query_text,
                            "search_results_count": 0,
                            "scored_urls": [],
                            "best_url": None,
                            "error": "No search results"
                        })
                        continue
                    
                    logger.info(f"  検索結果: {len(search_results)}件")
                    
                    # スコアリング実行（非同期対応の場合は適切に修正が必要）
                    scored_urls = []
                    for result in search_results:
                        scored = self.scorer.calculate_score(result, company, pattern.name)
                        if scored:
                            scored_urls.append(scored)
                    
                    # ベストURL選択
                    best_url = max(scored_urls, key=lambda x: x.total_score) if scored_urls else None
                    
                    # 結果保存
                    query_result = {
                        "pattern": pattern._asdict(),
                        "query_text": query_text,
                        "search_results_count": len(search_results),
                        "scored_urls": [self._serialize_hp_candidate(score) for score in scored_urls],
                        "best_url": self._serialize_hp_candidate(best_url) if best_url else None
                    }
                    
                    company_result["query_results"].append(query_result)
                    all_scored_urls.extend(scored_urls)
                    
                    # 結果表示
                    self._display_query_result(pattern, query_text, search_results, scored_urls, best_url)
                    
                except Exception as e:
                    logger.error(f"  クエリテストエラー ({pattern.name}): {e}")
                    company_result["query_results"].append({
                        "pattern": pattern._asdict(),
                        "query_text": "",
                        "search_results_count": 0,
                        "scored_urls": [],
                        "best_url": None,
                        "error": str(e)
                    })
            
            # 全クエリ中のベストURL
            if all_scored_urls:
                best_overall = max(all_scored_urls, key=lambda x: x.total_score)
                company_result["best_overall"] = self._serialize_hp_candidate(best_overall)
                logger.info(f"  🏆 全クエリ中のベスト: {best_overall.url} ({best_overall.total_score}点)")
            
            return company_result
            
        except Exception as e:
            logger.error(f"企業クエリテストエラー: {company.id} - {e}")
            return {
                "company": {
                    "id": company.id,
                    "name": company.company_name,
                    "prefecture": company.prefecture,
                    "industry": company.industry
                },
                "query_results": [],
                "best_overall": None,
                "error": str(e)
            }
    
    def _display_query_result(self, pattern, query_text, search_results, scored_urls, best_url):
        """クエリ結果の表示"""
        logger.info(f"    生成クエリ: {query_text}")
        logger.info(f"    検索結果数: {len(search_results)}")
        logger.info(f"    スコア計算後: {len(scored_urls)}")
        
        if best_url:
            logger.info(f"    ベストURL: {best_url.url}")
            logger.info(f"    スコア: {best_url.total_score}点 ({best_url.judgment})")
            logger.info(f"    トップページ: {'Yes' if best_url.is_top_page else 'No'}")
            logger.info(f"    ドメイン類似度: {best_url.domain_similarity:.1f}%")
            
            # スコア内訳表示
            if best_url.score_details:
                logger.info("    スコア内訳:")
                for component, score in best_url.score_details.items():
                    logger.info(f"      {component}: {score}")
        else:
            logger.warning("    有効なURLが見つかりませんでした")
    
    def _serialize_hp_candidate(self, candidate) -> Dict[str, Any]:
        """HPCandidateオブジェクトをシリアライズ"""
        if not candidate:
            return None
        
        return {
            "url": candidate.url,
            "title": candidate.title,
            "description": candidate.description,
            "search_rank": candidate.search_rank,
            "query_pattern": candidate.query_pattern,
            "domain_similarity": candidate.domain_similarity,
            "is_top_page": candidate.is_top_page,
            "total_score": candidate.total_score,
            "judgment": candidate.judgment,
            "score_details": candidate.score_details
        }
    
    def _generate_test_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """テスト結果サマリー生成"""
        try:
            total_companies = len(test_results)
            successful_companies = len([r for r in test_results if "error" not in r])
            
            # クエリパターン別統計
            pattern_stats = {}
            for pattern in self.query_patterns:
                pattern_name = pattern.name
                pattern_stats[pattern_name] = {
                    "total_searches": 0,
                    "successful_searches": 0,
                    "found_urls": 0,
                    "auto_adopt_count": 0,
                    "needs_review_count": 0,
                    "manual_check_count": 0
                }
            
            # 全体統計
            overall_stats = {
                "best_urls_found": 0,
                "auto_adopt_count": 0,
                "needs_review_count": 0,
                "manual_check_count": 0
            }
            
            # 結果集計
            for result in test_results:
                if "error" in result:
                    continue
                
                # 全体ベストURL統計
                if result.get("best_overall"):
                    overall_stats["best_urls_found"] += 1
                    judgment = result["best_overall"]["judgment"]
                    overall_stats[f"{self._judgment_to_key(judgment)}_count"] += 1
                
                # クエリパターン別統計
                for query_result in result.get("query_results", []):
                    pattern_name = query_result["pattern"]["name"]
                    if pattern_name in pattern_stats:
                        stats = pattern_stats[pattern_name]
                        stats["total_searches"] += 1
                        
                        if "error" not in query_result:
                            stats["successful_searches"] += 1
                            stats["found_urls"] += len(query_result.get("scored_urls", []))
                            
                            if query_result.get("best_url"):
                                judgment = query_result["best_url"]["judgment"]
                                stats[f"{self._judgment_to_key(judgment)}_count"] += 1
            
            return {
                "total_companies": total_companies,
                "successful_companies": successful_companies,
                "success_rate": successful_companies / total_companies if total_companies > 0 else 0,
                "pattern_statistics": pattern_stats,
                "overall_statistics": overall_stats
            }
            
        except Exception as e:
            logger.error(f"サマリー生成エラー: {e}")
            return {"error": str(e)}
    
    def _judgment_to_key(self, judgment: str) -> str:
        """判定結果をキーに変換"""
        mapping = {
            "自動採用": "auto_adopt",
            "要確認": "needs_review", 
            "手動確認": "manual_check"
        }
        return mapping.get(judgment, "unknown")
    
    def save_results_to_file(self, results: Dict[str, Any], output_file: str):
        """結果をJSONファイルに保存"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"結果をファイルに保存しました: {output_file}")
        except Exception as e:
            logger.error(f"結果保存エラー: {e}")

async def main():
    """メイン関数"""
    try:
        # 設定読み込み
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # フェーズ1テスター初期化
        tester = Phase1QueryTester(config)
        
        # テスト設定（環境に合わせて変更）
        spreadsheet_id = config.get('google_sheets', {}).get('input_spreadsheet_id', '')
        sheet_name = config.get('google_sheets', {}).get('input_sheet_name', 'Sheet1')
        
        if not spreadsheet_id:
            logger.error("設定ファイルにinput_spreadsheet_idが指定されていません")
            return
        
        # クエリテスト実行
        results = await tester.run_query_test(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            start_row=2,
            end_row=11,  # 10社でテスト
            max_companies=10
        )
        
        if results["success"]:
            logger.info("=== テスト結果サマリー ===")
            summary = results["summary"]
            logger.info(f"対象企業数: {summary['total_companies']}")
            logger.info(f"成功企業数: {summary['successful_companies']}")
            logger.info(f"成功率: {summary['success_rate']:.1%}")
            
            # パターン別結果
            for pattern_name, stats in summary["pattern_statistics"].items():
                logger.info(f"\n[{pattern_name}]")
                logger.info(f"  検索実行: {stats['successful_searches']}/{stats['total_searches']}")
                logger.info(f"  URL発見: {stats['found_urls']}件")
                logger.info(f"  自動採用: {stats['auto_adopt_count']}件")
                logger.info(f"  要確認: {stats['needs_review_count']}件")
                logger.info(f"  手動確認: {stats['manual_check_count']}件")
            
            # 結果保存
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"logs/phase1_query_test_results_{timestamp}.json"
            tester.save_results_to_file(results, output_file)
        else:
            logger.error(f"テスト失敗: {results.get('error')}")
    
    except Exception as e:
        logger.error(f"メイン処理エラー: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 