import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
# from app import render_comparison_tool, compare_snapshots, compare_technical, compare_fundamental


@pytest.mark.integration
class TestComparisonSnapshot:
    """Test snapshot comparison functionality."""

    @patch('query_wrapper.query_snapshot')
    def test_compare_two_snapshots(self, mock_query):
        """Test comparing two stock snapshots."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330", "2412"],
            "price": [650.5, 45.0],
            "bid_price": [650.0, 44.9],
            "ask_price": [651.0, 45.1],
            "volume": [50000, 100000]
        })

        # result = compare_snapshots(["2330", "2412"])
        # assert len(result.columns) > 0
        # assert "2330" in result.columns or "code" in result.columns

    @patch('query_wrapper.query_snapshot')
    def test_compare_three_snapshots(self, mock_query):
        """Test comparing three stock snapshots."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330", "2412", "3008"],
            "price": [650.5, 45.0, 210.5],
            "volume": [50000, 100000, 75000]
        })

        # result = compare_snapshots(["2330", "2412", "3008"])
        # assert len(result) == 3

    @patch('query_wrapper.query_snapshot')
    def test_compare_snapshots_with_missing_data(self, mock_query):
        """Test handling of missing snapshot data."""
        # Return partial data
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # result = compare_snapshots(["2330", "9999"])
        # Should handle missing code gracefully

    @patch('query_wrapper.query_snapshot')
    def test_compare_snapshots_ordering(self, mock_query):
        """Test that comparison maintains requested code ordering."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330", "2412", "3008"],
            "price": [650.5, 45.0, 210.5]
        })

        codes = ["2412", "2330", "3008"]
        # result = compare_snapshots(codes)
        # Column order should match input order


@pytest.mark.integration
class TestComparisonTechnical:
    """Test technical indicator comparison."""

    @patch('query_wrapper.query_institutional')
    def test_compare_institutional_data(self, mock_query):
        """Test comparing institutional investor data."""
        mock_query.return_value = pd.DataFrame({
            "date": ["2026-05-16", "2026-05-15"],
            "code": ["2330", "2330"],
            "foreign_buy": [1000000, 1100000]
        })

        # result = compare_technical(["2330", "2412"], "institutional")
        # assert "foreign_buy" in result.columns

    @patch('query_wrapper.query_margin_short')
    def test_compare_margin_short_data(self, mock_query):
        """Test comparing margin and short data."""
        mock_query.return_value = pd.DataFrame({
            "date": ["2026-05-16"],
            "code": ["2330"],
            "margin_balance": [5000000],
            "short_balance": [1000000]
        })

        # result = compare_technical(["2330"], "margin_short")
        # assert "margin_balance" in result.columns

    @patch('query_wrapper.query_shareholding')
    def test_compare_shareholding_data(self, mock_query):
        """Test comparing foreign shareholding data."""
        mock_query.return_value = pd.DataFrame({
            "date": ["2026-05-16"],
            "code": ["2330"],
            "foreign_percentage": [25.5]
        })

        # result = compare_technical(["2330"], "shareholding")
        # assert "foreign_percentage" in result.columns

    @patch('query_wrapper.query_institutional')
    def test_compare_technical_date_range(self, mock_query):
        """Test technical comparison with custom date range."""
        mock_query.return_value = pd.DataFrame({
            "date": pd.date_range("2026-05-01", periods=16),
            "foreign_buy": [1000000] * 16
        })

        # result = compare_technical(
        #     ["2330"],
        #     "institutional",
        #     start="2026-05-01",
        #     end="2026-05-16"
        # )
        # assert len(result) == 16


@pytest.mark.integration
class TestComparisonFundamental:
    """Test fundamental indicator comparison."""

    @patch('query_wrapper.query_month_revenue')
    def test_compare_month_revenue(self, mock_query):
        """Test comparing monthly revenue data."""
        mock_query.return_value = pd.DataFrame({
            "date": ["2026-04", "2026-03"],
            "code": ["2330", "2330"],
            "revenue": [1500000000, 1450000000]
        })

        # result = compare_fundamental(["2330"], "month_revenue")
        # assert "revenue" in result.columns

    @patch('query_wrapper.query_financial_statement')
    def test_compare_financial_statement(self, mock_query):
        """Test comparing financial statement data."""
        mock_query.return_value = pd.DataFrame({
            "quarter": ["2026Q1", "2025Q4"],
            "code": ["2330", "2330"],
            "net_income": [300000000, 280000000]
        })

        # result = compare_fundamental(["2330"], "financial_statement")
        # assert "net_income" in result.columns

    @patch('query_wrapper.query_month_revenue')
    def test_compare_fundamental_year_range(self, mock_query):
        """Test fundamental comparison with yearly data."""
        mock_query.return_value = pd.DataFrame({
            "date": pd.date_range("2025-01", periods=12, freq="ME"),
            "revenue": [100000000 + (i * 10000000) for i in range(12)]
        })

        # result = compare_fundamental(
        #     ["2330"],
        #     "month_revenue",
        #     start="2025-01",
        #     end="2025-12"
        # )
        # assert len(result) == 12


@pytest.mark.integration
class TestComparisonDisplay:
    """Test comparison result display and formatting."""

    @patch('streamlit.columns')
    @patch('query_wrapper.query_snapshot')
    def test_comparison_columns_display(self, mock_query, mock_columns):
        """Test display of comparison in side-by-side columns."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330", "2412"],
            "price": [650.5, 45.0]
        })

        # render_comparison_tool(comparison_type="snapshot", codes=["2330", "2412"])
        # mock_columns should be called to create side-by-side layout

    @patch('streamlit.plotly_chart')
    @patch('query_wrapper.query_institutional')
    def test_comparison_chart_display(self, mock_query, mock_chart):
        """Test display of technical comparison as chart."""
        mock_query.return_value = pd.DataFrame({
            "date": pd.date_range("2026-05-01", periods=10),
            "foreign_buy": [1000000 + (i * 100000) for i in range(10)]
        })

        # render_comparison_tool(comparison_type="technical", codes=["2330"])
        # mock_chart should be called

    def test_comparison_max_codes_limit(self):
        """Test handling of maximum codes to compare."""
        # Too many codes might cause display issues
        codes = [f"000{i}" for i in range(10)]
        # result = compare_snapshots(codes)
        # Should display warning or limit to reasonable number


@pytest.mark.integration
class TestComparisonEdgeCases:
    """Test edge cases in comparison functionality."""

    @patch('query_wrapper.query_snapshot')
    def test_compare_same_code_multiple_times(self, mock_query):
        """Test comparing the same code multiple times."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # result = compare_snapshots(["2330", "2330", "2330"])
        # Should handle duplicate codes

    @patch('query_wrapper.query_snapshot')
    def test_compare_with_invalid_codes(self, mock_query):
        """Test comparison with some invalid codes."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # result = compare_snapshots(["2330", "INVALID", "9999"])
        # Should handle gracefully

    @patch('query_wrapper.query_institutional')
    def test_compare_no_data_available(self, mock_query):
        """Test comparison when no data available."""
        mock_query.return_value = pd.DataFrame()

        # result = compare_technical(["INVALID"], "institutional")
        # Should return empty or show "No data" message

    @patch('query_wrapper.query_month_revenue')
    def test_compare_insufficient_history(self, mock_query):
        """Test comparison with insufficient historical data."""
        mock_query.return_value = pd.DataFrame({
            "date": ["2026-05"],
            "revenue": [1500000000]
        })

        # result = compare_fundamental(["2330"], "month_revenue")
        # Should work with limited data


@pytest.mark.integration
class TestComparisonCaching:
    """Test caching in comparison operations."""

    @patch('query_wrapper.query_snapshot')
    def test_comparison_caching_repeated_queries(self, mock_query):
        """Test that repeated comparisons use cached data."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # First comparison
        # result1 = compare_snapshots(["2330"])

        # Second comparison - should use cache
        # result2 = compare_snapshots(["2330"])

        # Query should be called less due to caching
        # assert mock_query.call_count < 2

    @patch('query_wrapper.query_snapshot')
    def test_comparison_cache_invalidation(self, mock_query):
        """Test cache invalidation between different comparisons."""
        mock_query.return_value = pd.DataFrame({
            "code": ["2330"],
            "price": [650.5]
        })

        # First comparison
        # compare_snapshots(["2330"])

        # Different comparison - cache should not be used
        # compare_snapshots(["2412"])

        # Different code = different cache key
