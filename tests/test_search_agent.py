"""
Search Agent モジュールの単体テスト
Brave Search API連携とクエリ生成のテスト
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json

# 適切なパッケージインポート
from src.search_agent import (
    SearchAgent, CompanyInfo, SearchResult, QueryGenerator, 
    BraveSearchClient
)


class TestCompanyInfo:
    """CompanyInfoデータクラスのテスト"""
    
    def test_company_info_creation(self):
        """CompanyInfo作成のテスト"""
        company = CompanyInfo(
            id="001",
            company_name="Barber Boss【バーバー ボス】",
            prefecture="東京都",
            industry="美容業"
        )
        
        assert company.id == "001"
        assert company.company_name == "Barber Boss【バーバー ボス】"
        assert company.prefecture == "東京都"
        assert company.industry == "美容業"
    
    def test_company_info_equality(self):
        """CompanyInfo等価比較のテスト"""
        company1 = CompanyInfo("001", "Test Company", "東京都", "IT業")
        company2 = CompanyInfo("001", "Test Company", "東京都", "IT業")
        company3 = CompanyInfo("002", "Test Company", "東京都", "IT業")
        
        assert company1 == company2
        assert company1 != company3


class TestSearchResult:
    """SearchResultデータクラスのテスト"""
    
    def test_search_result_creation(self):
        """SearchResult作成のテスト"""
        result = SearchResult(
            url="https://example.com",
            title="Example Site",
            description="This is an example site",
            rank=1
        )
        
        assert result.url == "https://example.com"
        assert result.title == "Example Site"
        assert result.description == "This is an example site"
        assert result.rank == 1


class TestBraveSearchClient:
    """BraveSearchClientクラスのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.api_key = "test_api_key"
        self.client = BraveSearchClient(api_key=self.api_key)
    
    def test_initialization(self):
        """BraveSearchClient初期化のテスト"""
        assert self.client.api_key == self.api_key
        assert "X-Subscription-Token" in self.client.session.headers
        assert self.client.session.headers["X-Subscription-Token"] == self.api_key
    
    @patch('requests.Session.get')
    def test_search_success(self, mock_get):
        """検索成功のテスト"""
        # モックレスポンスの設定
        mock_response_data = {
            "web": {
                "results": [
                    {
                        "url": "https://barberboss.jp",
                        "title": "Barber Boss【バーバー ボス】公式サイト",
                        "description": "東京の理髪店 Barber Boss"
                    },
                    {
                        "url": "https://example2.com",
                        "title": "Example 2",
                        "description": "Another example"
                    }
                ]
            }
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # テスト実行
        results = self.client.search("Barber Boss 東京都 美容業 公式サイト")
        
        # 結果確認
        assert len(results) == 2
        assert results[0].url == "https://barberboss.jp"
        assert results[0].title == "Barber Boss【バーバー ボス】公式サイト"
        assert results[1].url == "https://example2.com"
        
        # API呼び出し確認
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_search_no_results(self, mock_get):
        """検索結果なしのテスト"""
        mock_response_data = {"web": {"results": []}}
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        results = self.client.search("存在しない企業名")
        
        assert len(results) == 0


class TestQueryGenerator:
    """QueryGeneratorクラスのテスト"""
    
    def test_generate_queries_default(self):
        """デフォルトクエリ生成のテスト"""
        company = CompanyInfo(
            id="001",
            company_name="Barber Boss【バーバー ボス】",
            prefecture="東京都",
            industry="美容業"
        )
        
        queries = QueryGenerator.generate_phase1_queries(company)
        
        # 3つのパターンが生成されることを確認
        assert len(queries) == 3
        assert "pattern_a" in queries
        assert "pattern_b" in queries  
        assert "pattern_c" in queries
        
        # 各パターンに企業情報が含まれることを確認
        for pattern_key, query in queries.items():
            assert "Barber Boss" in query
            # 業種または都道府県が含まれることを確認
            assert "美容業" in query or "東京都" in query
    
    def test_generate_queries_with_custom_queries(self):
        """カスタムクエリ生成のテスト"""
        company = CompanyInfo("001", "Test Company", "東京都", "IT業")
        
        query1 = QueryGenerator.generate_custom_query("{company_name} 公式", company)
        query2 = QueryGenerator.generate_custom_query('"{company_name}" {prefecture}', company)
        
        assert query1 == "Test Company 公式"
        assert query2 == '"Test Company" 東京都'
    
    def test_generate_single_query_pattern_a(self):
        """パターンA単体生成のテスト"""
        company = CompanyInfo("001", "Sample Corp", "大阪府", "製造業")
        
        queries = QueryGenerator.generate_phase1_queries(company)
        query_a = queries["pattern_a"]
        
        assert "Sample Corp" in query_a
        assert "製造業" in query_a and "大阪府" in query_a


class TestSearchAgent:
    """SearchAgentクラスのテスト"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.mock_client = Mock(spec=BraveSearchClient)
        self.agent = SearchAgent(brave_client=self.mock_client)
    
    def test_initialization(self):
        """SearchAgent初期化のテスト"""
        assert self.agent.brave_client == self.mock_client
    
    @patch('time.sleep')
    def test_search_company_single_pattern(self, mock_sleep):
        """企業検索のテスト"""
        company = CompanyInfo("001", "Test Company", "東京都", "IT業")
        
        # モックの設定
        mock_results_a = [SearchResult("https://test-a.com", "Test A", "Desc A", 1)]
        mock_results_b = [SearchResult("https://test-b.com", "Test B", "Desc B", 1)]
        mock_results_c = [SearchResult("https://test-c.com", "Test C", "Desc C", 1)]
        
        self.mock_client.search.side_effect = [mock_results_a, mock_results_b, mock_results_c]
        
        # テスト実行
        results = self.agent.search_company(company)
        
        # 結果確認
        assert len(results) == 3
        assert "pattern_a" in results
        assert "pattern_b" in results
        assert "pattern_c" in results
        assert len(results["pattern_a"]) == 1
        assert results["pattern_a"][0].url == "https://test-a.com"
        
        # 3回検索が呼ばれることを確認
        assert self.mock_client.search.call_count == 3
    
    @patch('time.sleep')
    def test_search_company_all_patterns(self, mock_sleep):
        """カスタムクエリでの企業検索のテスト"""
        company = CompanyInfo("001", "Test Company", "東京都", "IT業")
        
        # モックの設定
        custom_templates = [
            "{company_name} 公式",
            '"{company_name}" {prefecture}'
        ]
        mock_results_1 = [SearchResult("https://test-1.com", "Test 1", "Desc 1", 1)]
        mock_results_2 = [SearchResult("https://test-2.com", "Test 2", "Desc 2", 1)]
        
        self.mock_client.search.side_effect = [mock_results_1, mock_results_2]
        
        # テスト実行
        all_results = self.agent.search_with_custom_queries(company, custom_templates)
        
        # 結果確認
        assert len(all_results) == 2
        assert "custom_1" in all_results
        assert "custom_2" in all_results
        assert len(all_results["custom_1"]) == 1
        assert all_results["custom_1"][0].url == "https://test-1.com"
        assert len(all_results["custom_2"]) == 1
        assert all_results["custom_2"][0].url == "https://test-2.com"
        
        # モック呼び出し確認
        assert self.mock_client.search.call_count == 2 # custom_templates の数だけ呼ばれる
        mock_sleep.assert_has_calls([call(1.2)] * 2) # patch.call を call に修正
    
    @patch('time.sleep') # time.sleep をモック
    def test_search_company_custom_queries(self, mock_sleep): # async def を def に、mock_sleep を引数に追加
        """カスタムクエリでの企業検索のテスト"""
        company = CompanyInfo("001", "Test Company", "東京都", "IT業")
        custom_templates = ["{company_name} 公式", "{company_name} {prefecture}"]
        
        # モックの設定
        mock_results_1 = [SearchResult("https://custom1.com", "Custom 1", "Desc 1", 1)] # rank を追加
        mock_results_2 = [SearchResult("https://custom2.com", "Custom 2", "Desc 2", 1)] # rank を追加
        
        self.mock_client.search.side_effect = [mock_results_1, mock_results_2]
        
        # テスト実行
        results = self.agent.search_with_custom_queries(company, custom_templates) # await を削除
        
        # 結果確認
        assert len(results) == 2
        assert "custom_1" in results
        assert "custom_2" in results
        assert len(results["custom_1"]) == 1
        assert results["custom_1"][0].url == "https://custom1.com"
        
        # 2回検索が呼ばれることを確認
        assert self.mock_client.search.call_count == 2
        mock_sleep.assert_has_calls([call(1.2)] * 2) # patch.call を call に修正


class TestSearchAgentIntegration:
    """SearchAgentの統合テスト"""
    
    @patch('requests.Session.get') # aiohttp.ClientSession.get を requests.Session.get に変更
    @patch('time.sleep') # time.sleep をモック
    def test_full_search_flow(self, mock_sleep, mock_get): # async def を def に、mock_sleep を引数に追加
        """完全な検索フローの統合テスト"""
        # 実際のクライアントとジェネレータを使用
        client = BraveSearchClient("test_api_key")
        # generator = QueryGenerator() # QueryGeneratorはSearchAgent内でstaticに呼ばれるため不要
        agent = SearchAgent(brave_client=client) # query_generator を削除
        
        # モックレスポンスの設定
        mock_response_data_a = {
            "web": {
                "results": [
                    {"url": "https://barberboss-a.jp", "title": "Barber Boss A", "description": "Site A"},
                ]
            }
        }
        mock_response_data_b = {
            "web": {
                "results": [
                    {"url": "https://barberboss-b.jp", "title": "Barber Boss B", "description": "Site B"},
                ]
            }
        }
        mock_response_data_c = {
            "web": {
                "results": [
                    {"url": "https://barberboss-c.jp", "title": "Barber Boss C", "description": "Site C"},
                ]
            }
        }

        mock_response_a = Mock()
        mock_response_a.status_code = 200 
        mock_response_a.json.return_value = mock_response_data_a
        mock_response_a.raise_for_status = Mock()

        mock_response_b = Mock()
        mock_response_b.status_code = 200
        mock_response_b.json.return_value = mock_response_data_b
        mock_response_b.raise_for_status = Mock()

        mock_response_c = Mock()
        mock_response_c.status_code = 200
        mock_response_c.json.return_value = mock_response_data_c
        mock_response_c.raise_for_status = Mock()

        # session.getが呼ばれるたびに異なるレスポンスを返すように設定
        mock_get.side_effect = [mock_response_a, mock_response_b, mock_response_c]
        
        # テスト企業
        company = CompanyInfo(
            id="001",
            company_name="Barber Boss",
            prefecture="東京都",
            industry="美容業"
        )
        
        # 全パターン検索実行
        results = agent.search_company(company) # await を削除、search_company_all_patterns を search_company に変更
        
        # 結果確認
        assert len(results) == 3  # pattern_a, pattern_b, pattern_c
        assert results["pattern_a"][0].url == "https://barberboss-a.jp"
        assert results["pattern_a"][0].rank == 1
        assert results["pattern_b"][0].url == "https://barberboss-b.jp"
        assert results["pattern_b"][0].rank == 1
        assert results["pattern_c"][0].url == "https://barberboss-c.jp"
        assert results["pattern_c"][0].rank == 1
        
        # API呼び出し回数確認（3パターン × 1回ずつ）
        assert mock_get.call_count == 3
        mock_sleep.assert_has_calls([call(1.2)] * 3) # patch.call を call に修正


if __name__ == "__main__":
    # 単独実行時のテスト
    pytest.main([__file__, "-v"]) 