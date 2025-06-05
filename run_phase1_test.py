#!/usr/bin/env python3
"""
フェーズ1クエリテスト支援スクリプト実行ファイル
"""

import os
import sys
import asyncio
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.phase1_query_test import Phase1QueryTester

async def main():
    """メイン実行関数"""
    
    # 設定ファイルチェック
    config_path = PROJECT_ROOT / "config" / "config.yaml"
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
        from src.utils import ConfigManager
        config_manager = ConfigManager(str(config_path))
        config = config_manager.get_config()
        
        # テスター初期化
        tester = Phase1QueryTester(config)
        
        # テスト実行（例：単一企業テスト）
        test_company = {
            "company_id": "TEST001",
            "company_name": "サンプル株式会社",
            "prefecture": "東京都", 
            "industry": "IT"
        }
        
        print(f"📊 テスト対象企業: {test_company['company_name']}")
        print(f"📍 所在地: {test_company['prefecture']}")
        print(f"🏭 業種: {test_company['industry']}")
        print("-" * 60)
        
        # テスト実行
        results = await tester.test_single_company(test_company)
        
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