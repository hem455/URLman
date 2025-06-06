#!/usr/bin/env python3
"""
Webページコンテンツ解析モジュール
地域情報抽出のための3段階ロジック実装
"""

import requests
import json
import re
from typing import Dict, Optional, Tuple, Any
from bs4 import BeautifulSoup
from dataclasses import dataclass
from .logger_config import get_logger

logger = get_logger(__name__)

@dataclass
class LocationInfo:
    """抽出された地域情報"""
    prefecture: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    phone_number: Optional[str] = None
    confidence_level: str = "none"  # "high", "medium", "low", "none"
    extraction_method: str = "none"  # "json_ld", "html_footer", "contact_page", "none"

class WebContentAnalyzer:
    """Webページから地域情報を抽出する分析クラス"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_location_info(self, url: str) -> LocationInfo:
        """
        URLから地域情報を3段階ロジックで抽出
        
        Args:
            url: 解析対象のURL
            
        Returns:
            LocationInfo: 抽出された地域情報
        """
        try:
            # HTMLを取得
            html_content = self._fetch_html(url)
            if not html_content:
                return LocationInfo()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 段階A: JSON-LD構造化データ抽出（高精度）
            location_info = self._extract_from_json_ld(soup)
            if location_info.confidence_level == "high":
                return location_info
            
            # 段階B: HTMLフッター/お問い合わせページ解析（中精度）
            location_info = self._extract_from_html_content(soup, url)
            if location_info.confidence_level in ["high", "medium"]:
                return location_info
            
            # 段階C: 追加ページ（お問い合わせ等）の解析
            location_info = self._extract_from_contact_pages(soup, url)
            return location_info
            
        except Exception as e:
            logger.warning(f"地域情報抽出エラー: {url} - {e}")
            return LocationInfo()
    
    def _fetch_html(self, url: str) -> Optional[str]:
        """HTMLコンテンツを取得"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning(f"HTML取得エラー: {url} - {e}")
            return None
    
    def _extract_from_json_ld(self, soup: BeautifulSoup) -> LocationInfo:
        """
        段階A: JSON-LD構造化データから地域情報を抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            LocationInfo: 抽出結果（高精度）
        """
        try:
            # JSON-LDスクリプトタグを検索
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    location_info = self._parse_json_ld_data(data)
                    if location_info:
                        location_info.confidence_level = "high"
                        location_info.extraction_method = "json_ld"
                        logger.info(f"JSON-LD地域情報抽出成功: {location_info.prefecture}")
                        return location_info
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.warning(f"JSON-LD解析エラー: {e}")
        
        return LocationInfo()
    
    def _parse_json_ld_data(self, data: Any) -> Optional[LocationInfo]:
        """JSON-LDデータから地域情報をパース"""
        try:
            # 単一オブジェクトまたはリストの処理
            if isinstance(data, list):
                for item in data:
                    result = self._parse_json_ld_data(item)
                    if result:
                        return result
                return None
            
            if not isinstance(data, dict):
                return None
            
            location_info = LocationInfo()
            
            # address フィールドを検索
            address = data.get('address')
            if address:
                if isinstance(address, dict):
                    location_info.prefecture = self._normalize_prefecture(
                        address.get('addressRegion') or address.get('addressLocality')
                    )
                    location_info.city = address.get('addressLocality')
                    location_info.postal_code = address.get('postalCode')
                elif isinstance(address, str):
                    # 文字列の場合は正規表現で解析
                    location_info.prefecture = self._extract_prefecture_from_text(address)
            
            # telephone フィールドを検索
            telephone = data.get('telephone')
            if telephone:
                location_info.phone_number = telephone
                # 電話番号から都道府県を推定
                if not location_info.prefecture:
                    location_info.prefecture = self._infer_prefecture_from_phone(telephone)
            
            # contactPoint配下も確認
            contact_point = data.get('contactPoint')
            if contact_point and isinstance(contact_point, dict):
                telephone = contact_point.get('telephone')
                if telephone:
                    location_info.phone_number = telephone
                    if not location_info.prefecture:
                        location_info.prefecture = self._infer_prefecture_from_phone(telephone)
            
            return location_info if location_info.prefecture else None
            
        except Exception as e:
            logger.warning(f"JSON-LDパースエラー: {e}")
            return None
    
    def _extract_from_html_content(self, soup: BeautifulSoup, base_url: str) -> LocationInfo:
        """
        段階B: HTMLフッター/本文から正規表現で地域情報を抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            base_url: ベースURL
            
        Returns:
            LocationInfo: 抽出結果（中精度）
        """
        try:
            location_info = LocationInfo()
            
            # フッター要素を優先的に検索
            footer_elements = soup.find_all(['footer', 'div'], class_=re.compile(r'footer|contact|info', re.I))
            
            # フッターが見つからない場合は全体から検索
            if not footer_elements:
                footer_elements = [soup]
            
            for element in footer_elements:
                text_content = element.get_text() if element else ""
                
                # 電話番号パターンで地域推定（愛知県: 052-, 東京都: 03-等）
                phone_match = re.search(r'(\d{2,4})-\d{4}-?\d{4}', text_content)
                if phone_match:
                    area_code = phone_match.group(1)
                    location_info.phone_number = phone_match.group(0)
                    location_info.prefecture = self._infer_prefecture_from_area_code(area_code)
                
                # 郵便番号パターン（愛知県: 4xx-xxxx）
                postal_match = re.search(r'[〒]?(\d{3}-\d{4})', text_content)
                if postal_match:
                    postal_code = postal_match.group(1)
                    location_info.postal_code = postal_code
                    if not location_info.prefecture:
                        location_info.prefecture = self._infer_prefecture_from_postal(postal_code)
                
                # 直接的な都道府県名マッチ
                if not location_info.prefecture:
                    location_info.prefecture = self._extract_prefecture_from_text(text_content)
                
                if location_info.prefecture:
                    location_info.confidence_level = "medium"
                    location_info.extraction_method = "html_footer"
                    logger.info(f"HTML地域情報抽出成功: {location_info.prefecture}")
                    return location_info
            
        except Exception as e:
            logger.warning(f"HTML解析エラー: {e}")
        
        return LocationInfo()
    
    def _extract_from_contact_pages(self, soup: BeautifulSoup, base_url: str) -> LocationInfo:
        """
        段階C: お問い合わせページなど追加ページから情報抽出
        
        Args:
            soup: BeautifulSoupオブジェクト
            base_url: ベースURL
            
        Returns:
            LocationInfo: 抽出結果（低精度）
        """
        try:
            # お問い合わせページのリンクを検索
            contact_links = soup.find_all('a', href=re.compile(r'contact|about|company|info', re.I))
            
            for link in contact_links[:3]:  # 最大3ページまで確認
                href = link.get('href')
                if href:
                    # 相対URLを絶対URLに変換
                    if href.startswith('/'):
                        contact_url = f"{base_url.rstrip('/')}{href}"
                    elif href.startswith('http'):
                        contact_url = href
                    else:
                        continue
                    
                    # お問い合わせページを解析
                    contact_html = self._fetch_html(contact_url)
                    if contact_html:
                        contact_soup = BeautifulSoup(contact_html, 'html.parser')
                        location_info = self._extract_from_html_content(contact_soup, contact_url)
                        if location_info.prefecture:
                            location_info.confidence_level = "low"
                            location_info.extraction_method = "contact_page"
                            logger.info(f"お問い合わせページ地域情報抽出: {location_info.prefecture}")
                            return location_info
            
        except Exception as e:
            logger.warning(f"お問い合わせページ解析エラー: {e}")
        
        return LocationInfo()
    
    def _normalize_prefecture(self, text: str) -> Optional[str]:
        """都道府県名を正規化"""
        if not text:
            return None
        
        # 全角・半角統一
        normalized = text.strip()
        
        # 都道府県名マッピング
        prefecture_map = {
            'aichi': '愛知県', 'tokyo': '東京都', 'osaka': '大阪府',
            'kanagawa': '神奈川県', 'kyoto': '京都府', 'hyogo': '兵庫県'
        }
        
        # 英語名から日本語名に変換
        if normalized.lower() in prefecture_map:
            return prefecture_map[normalized.lower()]
        
        # 既に日本語の場合はそのまま返す
        all_prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
        ]
        
        for prefecture in all_prefectures:
            if prefecture in normalized or prefecture.replace('県', '').replace('府', '').replace('都', '') in normalized:
                return prefecture
        
        return None
    
    def _extract_prefecture_from_text(self, text: str) -> Optional[str]:
        """テキストから都道府県名を抽出"""
        all_prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
        ]
        
        for prefecture in all_prefectures:
            if prefecture in text:
                return prefecture
        
        return None
    
    def _infer_prefecture_from_phone(self, phone: str) -> Optional[str]:
        """電話番号から都道府県を推定"""
        return self._infer_prefecture_from_area_code(phone[:3])
    
    def _infer_prefecture_from_area_code(self, area_code: str) -> Optional[str]:
        """市外局番から都道府県を推定"""
        area_code_map = {
            '052': '愛知県', '03': '東京都', '06': '大阪府',
            '045': '神奈川県', '078': '兵庫県', '075': '京都府',
            '092': '福岡県', '011': '北海道', '022': '宮城県',
            '082': '広島県', '054': '静岡県', '043': '千葉県',
            '048': '埼玉県'
        }
        return area_code_map.get(area_code)
    
    def _infer_prefecture_from_postal(self, postal_code: str) -> Optional[str]:
        """郵便番号から都道府県を推定（上位3桁）"""
        prefix = postal_code[:3]
        postal_prefix_map = {
            '4': '愛知県',  # 400-499
            '1': '東京都',  # 100-199  
            '5': '大阪府',  # 500-599
            '2': '神奈川県',  # 200-299
            '6': '兵庫県',  # 600-699
        }
        return postal_prefix_map.get(prefix[0]) if prefix.isdigit() else None 