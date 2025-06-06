"""
共通ユーティリティモジュール
設定読み込み、URL処理、文字列処理などの共通機能を提供
"""

import os
import yaml
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

class ConfigManager:
    """設定ファイル管理クラス"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self._config = None
        
    def load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            # 環境変数からAPIキーを読み込み（設定ファイルより優先）
            self._load_api_keys_from_env()
            
            return self._config
            
        except FileNotFoundError:
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"設定ファイルの形式が不正です: {e}")
    
    def _load_api_keys_from_env(self):
        """環境変数からAPIキーを読み込む"""
        if not self._config:
            return
            
        # Brave Search APIキー
        brave_api_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if brave_api_key:
            if 'brave_api' not in self._config:
                self._config['brave_api'] = {}
            self._config['brave_api']['api_key'] = brave_api_key
    
    def get(self, key_path: str, default=None):
        """ドット記法で設定値を取得"""
        if not self._config:
            self.load_config()
            
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value

class URLUtils:
    """URL処理関連のユーティリティ"""
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """URLを正規化する"""
        if not url:
            return ""
            
        # httpまたはhttpsプロトコルを追加
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # 末尾のスラッシュを除去
        return url.rstrip('/')
    
    @staticmethod
    def get_domain(url: str) -> str:
        """URLからドメイン名を抽出"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # www.を除去
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    @staticmethod
    def get_path_depth(url: str) -> int:
        """URLのパス深度を計算"""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            if not path:
                return 0
                
            # index.html等のトップページファイルは深度0とみなす
            top_page_files = ['index.html', 'index.htm', 'index.php', 
                            'default.aspx', 'default.asp', 'home.html']
            
            if path.lower() in top_page_files:
                return 0
                
            return len(path.split('/'))
            
        except:
            return 999  # エラーの場合は大きな値を返す
    
    @staticmethod
    def is_top_page(url: str) -> bool:
        """URLがトップページかどうかを判定"""
        return URLUtils.get_path_depth(url) == 0

class StringUtils:
    """文字列処理関連のユーティリティ"""
    
    @staticmethod
    def clean_company_name(company_name: str) -> str:
        """企業名を正規化する"""
        if not company_name:
            return ""
            
        # 【】内の読み仮名を除去
        cleaned = re.sub(r'【.*?】', '', company_name)
        
        # 不要な空白を除去
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    @staticmethod
    def remove_legal_suffixes(company_name: str) -> str:
        """法人格を示す接尾辞を除去"""
        suffixes = ['株式会社', '有限会社', '合同会社', '合資会社', '合名会社', 
                   '一般社団法人', '公益社団法人', '一般財団法人', '公益財団法人',
                   '(株)', '（株）', '(有)', '（有）']
        
        for suffix in suffixes:
            company_name = company_name.replace(suffix, '').strip()
            
        return company_name
    
    @staticmethod
    def extract_katakana(text: str) -> str:
        """カタカナ部分のみを抽出"""
        katakana_pattern = r'[ァ-ヴー]+'
        matches = re.findall(katakana_pattern, text)
        return ' '.join(matches)

class BlacklistChecker:
    """ブラックリスト・ペナルティチェッククラス"""
    
    def __init__(self, blacklist_config_path: str = "config/blacklist.yaml"):
        self.blacklist_config_path = blacklist_config_path
        self._blacklist_config = None
        
    def load_blacklist(self):
        """ブラックリスト設定を読み込む"""
        try:
            with open(self.blacklist_config_path, 'r', encoding='utf-8') as f:
                self._blacklist_config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"ブラックリスト設定ファイルが見つかりません: {self.blacklist_config_path}")
    
    def is_domain_blacklisted(self, url: str) -> bool:
        """ドメインがブラックリストに含まれているかチェック"""
        if not self._blacklist_config:
            self.load_blacklist()
            
        domain = URLUtils.get_domain(url)
        blacklist_domains = self._blacklist_config.get('blacklist_domains', [])
        
        return domain in blacklist_domains
    
    def get_blacklist_domains(self) -> set:
        """ブラックリストドメインのセットを取得"""
        if not self._blacklist_config:
            self.load_blacklist()
            
        blacklist_domains = self._blacklist_config.get('blacklist_domains', [])
        return set(blacklist_domains)
    
    def get_path_penalty_score(self, url: str, penalty_value: int = -2) -> int:
        """URLパスのペナルティスコアを計算"""
        if not self._blacklist_config:
            self.load_blacklist()
            
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            penalty_keywords = self._blacklist_config.get('path_penalty_keywords', [])
            
            for keyword in penalty_keywords:
                if keyword in path:
                    return penalty_value
                    
            return 0
            
        except:
            return 0

def validate_config(config: Dict[str, Any]) -> List[str]:
    """設定ファイルの妥当性をチェック"""
    errors = []
    
    # 必須項目のチェック
    required_fields = [
        'brave_api.api_key',
        'google_sheets.service_account_file',
        'google_sheets.input_spreadsheet_id'
    ]
    
    for field in required_fields:
        keys = field.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                errors.append(f"必須設定項目が不足しています: {field}")
                break
        
        # 値が空でないかチェック
        if isinstance(value, str) and not value.strip():
            errors.append(f"設定項目が空です: {field}")
    
    return errors 