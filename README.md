# 会社HP自動検索・貼り付けツール

大量の企業・店舗リストに対して公式HPを自動検索し、Googleスプレッドシートに結果を書き込む自動化ツールです。

## 概要

- **処理能力**: 1日1000件の自動処理
- **精度目標**: 90%以上の正確な公式HPトップページ検出
- **API連携**: Brave Search API (Proプラン) + Google Sheets API
- **技術スタック**: Python 3.8+, asyncio, aiohttp, rapidfuzz

## 機能

### フェーズ1: クエリテスト支援
- 複数の検索クエリパターンでのテスト実行
- 結果の目視評価支援

### フェーズ3: 本格自動化（予定）
- 最適化されたスコアリングアルゴリズム
- 自動判定（自動採用/要確認/手動確認）
- 包括的なログ出力

## セットアップ

### 1. 仮想環境の準備
```powershell
python -m venv venv
venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

### 2. API認証設定
1. **Brave Search API**
   - Proプランに登録してAPIキーを取得
   - 環境変数 `BRAVE_SEARCH_API_KEY` に設定

2. **Google Sheets API**
   - Google Cloud Projectを作成
   - Google Sheets API + Google Drive APIを有効化
   - サービスアカウントを作成してJSONキーをダウンロード
   - `config/service_account.json` に配置

### 3. 設定ファイル
```powershell
# 設定ファイルのテンプレートをコピー
Copy-Item config\config.yaml.example config\config.yaml
Copy-Item config\blacklist.yaml.example config\blacklist.yaml
Copy-Item config\query_patterns.yaml.example config\query_patterns.yaml
```

## 使用方法

### フェーズ1: クエリテスト
```powershell
python src\phase1_query_test.py
```

### フェーズ3: 本格実行（予定）
```powershell
python src\main.py
```

## プロジェクト構造

```
.
├── src/                    # ソースコード
│   ├── data_loader.py     # Google Sheets読み込み
│   ├── search_agent.py    # Brave Search API連携
│   ├── scorer.py          # スコアリングロジック
│   ├── output_writer.py   # Google Sheets書き込み
│   ├── logger_config.py   # ログ設定
│   └── utils.py           # 共通ユーティリティ
├── config/                 # 設定ファイル
├── tests/                  # テストコード
├── logs/                   # ログ出力
└── requirements.txt        # 依存ライブラリ
```

## 開発状況

進捗管理は `implementation_plan.md` で行っています。

## 注意事項

- APIキーなどの機密情報はコードにハードコーディングせず、環境変数や設定ファイルで管理してください
- Brave Search APIのレートリミット（50 QPS）を遵守してください
- 大量処理前には必ず小規模テストで動作確認を行ってください

## ライセンス

このプロジェクトは内部利用目的で開発されています。

## サポート

問題が発生した場合は、`logs/` ディレクトリのログファイルを確認してください。 