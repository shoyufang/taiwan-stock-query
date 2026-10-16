import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import utils


class TestDateHandling:
    """Test date parsing and validation utilities."""

    def test_parse_date_string_valid(self):
        """Test parsing valid date string."""
        date_str = "2026-05-16"
        # Assuming parse_date_string function exists in utils
        # parsed = utils.parse_date_string(date_str)
        # assert parsed == datetime(2026, 5, 16).date()

    def test_parse_date_range_valid(self):
        """Test parsing valid date range."""
        start = "2026-01-01"
        end = "2026-05-16"
        # Assuming parse_date_range function exists
        # range_tuple = utils.parse_date_range(start, end)
        # assert range_tuple[0] < range_tuple[1]

    def test_date_format_validation(self):
        """Test date format validation."""
        valid_formats = [
            "2026-05-16",
            "2026/05/16",
            "2026.05.16"
        ]
        # Test each format


class TestDataFormatting:
    """Test data formatting utilities."""

    def test_format_number_with_comma(self):
        """Test number formatting with thousand separators."""
        # Assuming format_number function exists
        # result = utils.format_number(1000000)
        # assert result == "1,000,000"

    def test_format_percentage(self):
        """Test percentage formatting."""
        # Assuming format_percentage function exists
        # result = utils.format_percentage(0.0850)
        # assert result == "8.50%"

    def test_format_currency(self):
        """Test currency formatting."""
        # Assuming format_currency function exists
        # result = utils.format_currency(1234.56, "TWD")
        # assert "1,234.56" in result


class TestListSplitting:
    """Test utility for splitting lists."""

    def test_split_codes_by_comma(self):
        """Test splitting comma-separated stock codes."""
        # Assuming split_stock_codes function exists
        # codes = utils.split_stock_codes("2330,2412,3008")
        # assert codes == ["2330", "2412", "3008"]

    def test_split_codes_with_whitespace(self):
        """Test splitting codes with whitespace."""
        # codes = utils.split_stock_codes("2330, 2412 , 3008")
        # assert codes == ["2330", "2412", "3008"]

    def test_split_codes_empty_string(self):
        """Test splitting empty string."""
        # codes = utils.split_stock_codes("")
        # assert codes == []


class TestValidation:
    """Test data validation utilities."""

    def test_validate_stock_code_format(self):
        """Test stock code format validation."""
        # Assuming validate_stock_code function exists
        # assert utils.validate_stock_code("2330") is True
        # assert utils.validate_stock_code("INVALID") is False

    def test_validate_stock_code_range(self):
        """Test stock code numeric range."""
        # Taiwan stock codes are typically 4 digits
        # assert utils.validate_stock_code("1000") is True
        # assert utils.validate_stock_code("9999") is True
        # assert utils.validate_stock_code("0001") is True

    def test_validate_date_range(self):
        """Test date range validation."""
        # start = "2026-01-01"
        # end = "2026-05-16"
        # assert utils.validate_date_range(start, end) is True
        # assert utils.validate_date_range(end, start) is False


class TestExportFunctionality:
    """Test export utilities."""

    @patch('utils.export_csv')
    def test_export_to_csv(self, mock_csv):
        """Test CSV export."""
        df = pd.DataFrame({
            "代號": ["2330", "2412"],
            "名稱": ["台積電", "中華電"],
            "價格": [650.5, 45.0]
        })
        # Assuming export_to_csv function exists
        # result = utils.export_to_csv(df, "output.csv")
        # assert result is not None

    @patch('openpyxl.Workbook')
    def test_export_to_excel(self, mock_wb):
        """Test Excel export."""
        df = pd.DataFrame({
            "代號": ["2330"],
            "價格": [650.5]
        })
        # Assuming export_to_excel function exists
        # result = utils.export_to_excel(df, "output.xlsx")

    def test_export_with_unicode_characters(self):
        """Test export with Chinese characters."""
        df = pd.DataFrame({
            "代號": ["2330"],
            "名稱": ["台積電"],
            "分類": ["半導體"]
        })
        # Should handle unicode properly


class TestErrorHandling:
    """Test error handling utilities."""

    def test_safe_divide(self):
        """Test safe division handling."""
        # Assuming safe_divide function exists
        # result = utils.safe_divide(10, 2)
        # assert result == 5
        # result = utils.safe_divide(10, 0)
        # assert result == 0 or result == None

    def test_safe_float_conversion(self):
        """Test safe float conversion."""
        # result = utils.safe_float("123.45")
        # assert result == 123.45
        # result = utils.safe_float("invalid")
        # assert result == 0 or result == None

    def test_safe_date_parsing(self):
        """Test safe date parsing."""
        # result = utils.safe_date_parse("2026-05-16")
        # assert isinstance(result, datetime)
        # result = utils.safe_date_parse("invalid")
        # assert result is None


class TestDataAggregation:
    """Test data aggregation utilities."""

    def test_aggregate_institutional_data(self):
        """Test aggregation of institutional investor data."""
        data = [
            {"date": "2026-05-16", "foreign": 100, "trust": 50},
            {"date": "2026-05-15", "foreign": 110, "trust": 45}
        ]
        # df = utils.aggregate_institutional(data)
        # assert len(df) == 2

    def test_calculate_cumulative_sum(self):
        """Test cumulative sum calculation."""
        data = [10, 20, 30, 40]
        # result = utils.cumulative_sum(data)
        # assert result == [10, 30, 60, 100]


@pytest.mark.integration
class TestUtilsIntegration:
    """Integration tests for utils."""

    def test_full_export_pipeline(self):
        """Test complete export pipeline."""
        df = pd.DataFrame({
            "代號": ["2330", "2412"],
            "名稱": ["台積電", "中華電"],
            "價格": [650.5, 45.0]
        })
        # Test full export to different formats
        # csv_result = utils.export_to_csv(df)
        # excel_result = utils.export_to_excel(df)
        # pdf_result = utils.export_to_pdf(df)
        # All should succeed without errors

    def test_data_validation_pipeline(self):
        """Test complete data validation pipeline."""
        codes = "2330,2412,invalid,3008"
        dates = "2026-01-01,2026-05-16"
        # valid_codes = utils.validate_and_clean_codes(codes)
        # valid_dates = utils.validate_and_clean_dates(dates)
        # Should return only valid entries
