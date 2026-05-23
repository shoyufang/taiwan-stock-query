import pytest
from unittest.mock import patch, MagicMock
from deepseek_engine import generate_us_stock_report

@patch("deepseek_engine.get_deepseek_engine")
@patch("us_stock_query.get_us_stock_info")
@patch("us_stock_query.get_us_analyst_info")
@patch("us_stock_query.get_us_holders")
@patch("us_stock_query.get_us_financials")
@patch("us_stock_query.get_us_stock_news")
def test_generate_us_stock_report(
    mock_news, mock_financials, mock_holders, mock_analyst, mock_info, mock_get_engine
):
    """
    驗證一鍵 AI 報告生成流程。
    驗證其能完整搜集數據、構建 Prompt，並順利獲取 AI 分析結果。
    """
    # 1. 設置 Mock 資料
    mock_info.return_value = {
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 3000000000000,
        "pe_ratio": 30.0,
        "forward_pe": 28.0,
        "eps": 6.5,
        "dividend_yield": 0.005,
        "52_week_high": 199.0,
        "52_week_low": 165.0,
        "summary": "Apple summary info."
    }
    
    mock_analyst.return_value = {
        "current_price": 180.0,
        "target_mean": 210.0,
        "target_high": 250.0,
        "target_low": 180.0,
        "analyst_count": 42,
        "recommendation": "buy",
        "recommendation_mean": 1.8
    }
    
    import pandas as pd
    mock_holders.return_value = {
        "institutional": pd.DataFrame([{
            "Holder": "Vanguard Group",
            "Shares": 1000000,
            "Value": 180000000,
            "% Out": "8.5%"
        }]),
        "mutualfund": pd.DataFrame()
    }
    
    mock_financials.return_value = {
        "income_annual": pd.DataFrame(
            [[100, 110, 120]], 
            index=["Total Revenue"], 
            columns=["2022", "2023", "2024"]
        ),
        "balance_annual": pd.DataFrame(),
        "cashflow_annual": pd.DataFrame()
    }
    
    mock_news.return_value = [
        {"title": "Apple News 1", "publisher": "Reuters"}
    ]
    
    # 2. 模擬 AI 引擎
    mock_engine_instance = MagicMock()
    mock_client = MagicMock()
    mock_engine_instance.client = mock_client
    mock_engine_instance.model_name = "deepseek-v4-flash"
    mock_get_engine.return_value = mock_engine_instance
    
    # 模擬 AI 回傳內容
    mock_choice = MagicMock()
    mock_choice.message.content = "# Apple Investment Report\nThis is a mocked investment report."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    
    # 3. 執行生成
    report = generate_us_stock_report("AAPL")
    
    # 4. 驗證斷言
    assert "# Apple Investment Report" in report
    assert "This is a mocked investment report." in report
    
    # 驗證 AI completions.create 被正確調用且 Prompt 包含關鍵數據
    mock_client.chat.completions.create.assert_called_once()
    called_kwargs = mock_client.chat.completions.create.call_args[1]
    assert called_kwargs["model"] == "deepseek-v4-flash"
    
    prompt_sent = called_kwargs["messages"][0]["content"]
    assert "Apple Inc." in prompt_sent
    assert "Technology" in prompt_sent
    assert "3,000,000,000,000" in prompt_sent
    assert "Total Revenue" in prompt_sent
    assert "Vanguard Group" in prompt_sent
    assert "Apple News 1" in prompt_sent
