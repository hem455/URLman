# Google Sheets API 設定完全ガイド

## 🚀 1. Google Cloud Project作成

### 1-1. Google Cloud Consoleにアクセス
- https://console.cloud.google.com/ にアクセス
- Googleアカウントでログイン

### 1-2. 新しいプロジェクト作成
1. 「プロジェクトを選択」をクリック
2. 「新しいプロジェクト」をクリック  
3. プロジェクト名: `company-hp-search-tool`
4. 「作成」をクリック

## 🔧 2. API有効化

### 2-1. Google Sheets API有効化
1. 左メニュー「APIとサービス」→「ライブラリ」
2. 検索で「Google Sheets API」を検索
3. 「Google Sheets API」をクリック
4. 「有効にする」をクリック

### 2-2. Google Drive API有効化
1. 同様に「Google Drive API」を検索
2. 「Google Drive API」をクリック  
3. 「有効にする」をクリック

## 🔑 3. サービスアカウント作成

### 3-1. サービスアカウント作成
1. 左メニュー「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「サービスアカウント」
3. サービスアカウント名: `hp-search-service`
4. サービスアカウントID: `hp-search-service` (自動生成)
5. 「作成して続行」をクリック

### 3-2. 権限設定（スキップ可能）
- 「完了」をクリック（権限は後で設定可能）

### 3-3. JSONキーファイル作成
1. 作成されたサービスアカウントをクリック
2. 「キー」タブをクリック
3. 「鍵を追加」→「新しい鍵を作成」
4. 「JSON」を選択して「作成」
5. **JSONファイルがダウンロードされます** → **重要！安全に保管**

## 📁 4. プロジェクトへの配置

### 4-1. JSONファイルを配置
```bash
# ダウンロードしたJSONファイルをプロジェクトに配置
cp ~/Downloads/company-hp-search-tool-xxxxxxxxx.json config/service_account.json
```

### 4-2. 権限確認
```bash
# ファイルが正しく配置されているか確認
ls -la config/service_account.json
```

## 📊 5. テスト用スプレッドシート作成

### 5-1. 新しいスプレッドシート作成
1. https://sheets.google.com/ にアクセス
2. 「空白」をクリックして新しいシート作成
3. スプレッドシート名: `会社HP検索テスト`

### 5-2. テストデータ入力
以下のようにデータを入力：

| A (ID) | B (都道府県) | C (業種) | D (企業名) | E (HP URL) |
|--------|-------------|---------|------------|------------|
| 7610 | 愛知県 | ヘアサロン | LOREN 栄久屋大通店【ローレン】 | |
| 7611 | 愛知県 | ヘアサロン | tano【タノ】 | |
| 7612 | 愛知県 | ヘアサロン | NORTY【ノーティー】 | |

### 5-3. サービスアカウントに共有権限付与
1. スプレッドシートの「共有」ボタンをクリック
2. サービスアカウントのメールアドレスを入力
   - 形式: `hp-search-service@company-hp-search-tool.iam.gserviceaccount.com`
3. 権限: 「編集者」を選択
4. 「送信」をクリック

### 5-4. スプレッドシートIDを取得
- URLから取得: `https://docs.google.com/spreadsheets/d/{スプレッドシートID}/edit`
- **{スプレッドシートID}**部分をメモ

## ⚙️ 6. 設定ファイル更新

### 6-1. config.yaml更新
```yaml
google_sheets:
  service_account_file: "config/service_account.json"
  input_spreadsheet_id: "取得したスプレッドシートID"
  input_sheet_name: "シート1"
  output_spreadsheet_id: "取得したスプレッドシートID"  # 同じでOK
  output_sheet_name: "シート1"  # 同じでOK
```

## ✅ 7. 動作確認

### 7-1. 読み込みテスト
```bash
python -c "
from src.data_loader import create_data_loader_from_config
from src.utils import ConfigManager
config = ConfigManager().load_config()
loader = create_data_loader_from_config(config)
print('Google Sheets接続テスト成功！')
"
```

### 7-2. 書き込みテスト  
```bash
python -c "
from src.output_writer import create_output_writer_from_config
from src.utils import ConfigManager
config = ConfigManager().load_config()
writer = create_output_writer_from_config(config)
print('Google Sheets書き込みテスト成功！')
"
```

## 🔒 セキュリティ注意事項

### 重要！
- **service_account.json**は絶対に公開しない
- **.gitignore**に必ず含める
- 定期的にキーローテーションを行う
- 不要になったら即座に削除

### .env設定（オプション）
```bash
# .envファイルに追加可能
GOOGLE_APPLICATION_CREDENTIALS="config/service_account.json"
GOOGLE_SHEETS_SPREADSHEET_ID="スプレッドシートID"
```

## 🎯 次のステップ

1. サービスアカウント作成 ✅
2. JSONキー配置 ✅
3. スプレッドシート作成・共有 ✅
4. 設定ファイル更新 ✅
5. **実際のテスト実行** ← 次はここ！

これで完全なGoogle Sheets連携が完成します！🎉 