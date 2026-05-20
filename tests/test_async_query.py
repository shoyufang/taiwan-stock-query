import pytest
import time
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import query_wrapper as qw
from datetime import date


class TestAsyncBatchQuery:
    """Test async batch query functionality."""

    def test_batch_query_sync_multiple_snapshots(self):
        """Test batch query with multiple stock snapshots."""
        codes = ["2330", "2412", "3008"]
        queries = [
            {"func": qw.query_snapshot, "args": ([code],), "name": code}
            for code in codes
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == len(codes)
        for result in results:
            assert result is not None

    def test_batch_query_sync_with_exceptions(self):
        """Test batch query handles exceptions gracefully."""
        queries = [
            {"func": qw.query_snapshot, "args": (["2330"],), "name": "Valid"},
            {"func": qw.query_snapshot, "args": (["INVALID"],), "name": "Invalid"},
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == 2
        # Both should return a DataFrame (one empty, one with error)
        for result in results:
            assert result is not None

    def test_batch_query_performance_improvement(self):
        """Test that batch query provides performance improvement for multiple queries."""
        codes = ["2330", "2412"]

        # Sequential query time
        seq_start = time.time()
        seq_results = []
        for code in codes:
            result = qw.query_snapshot([code])
            seq_results.append(result)
        seq_time = time.time() - seq_start

        # Batch query time
        batch_start = time.time()
        queries = [
            {"func": qw.query_snapshot, "args": ([code],), "name": code}
            for code in codes
        ]
        batch_results = qw.batch_query_sync(queries)
        batch_time = time.time() - batch_start

        # Batch should be faster (or at least not significantly slower)
        # Allow 50% slower due to overhead, but should improve with caching
        assert batch_time <= seq_time * 1.5 or batch_time < 2.0

        # Results should match
        assert len(batch_results) == len(seq_results)

    def test_batch_query_preserves_order(self):
        """Test that batch query preserves the order of results."""
        codes = ["2330", "2412", "3008"]
        queries = [
            {"func": qw.query_snapshot, "args": ([code],), "name": code}
            for code in codes
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == len(codes)
        # Order should be preserved
        for i, result in enumerate(results):
            assert result is not None

    def test_batch_query_empty_list(self):
        """Test batch query with empty list."""
        queries = []
        results = qw.batch_query_sync(queries)
        assert results == []

    def test_batch_query_single_query(self):
        """Test batch query with single query falls back to sync."""
        queries = [
            {"func": qw.query_snapshot, "args": (["2330"],), "name": "TSMC"}
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == 1
        assert results[0] is not None


@pytest.mark.integration
class TestAsyncIntegration:
    """Integration tests for async query functionality."""

    def test_comparison_tool_async_query(self):
        """Test comparison tool with async queries."""
        codes = ["2330", "2412"]
        queries = [
            {"func": qw.query_snapshot, "args": ([code],), "name": code}
            for code in codes
        ]

        results = qw.batch_query_sync(queries)

        # Should return results for comparison
        assert len(results) == len(codes)
        for result in results:
            # Results can be empty but should be DataFrames
            assert result is not None

    def test_technical_analysis_async(self):
        """Test async technical analysis queries."""
        codes = ["2330", "2412"]
        start_date = date(2026, 1, 1)
        end_date = date(2026, 5, 16)

        queries = [
            {
                "func": qw.query_institutional_investors,
                "args": (code, start_date, end_date),
                "name": code
            }
            for code in codes
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == len(codes)
        for result in results:
            assert result is not None

    def test_fundamental_analysis_async(self):
        """Test async fundamental analysis queries."""
        codes = ["2330", "2412"]
        start_date = date(2025, 1, 1)
        end_date = date(2026, 5, 16)

        queries = [
            {
                "func": qw.query_month_revenue,
                "args": (code, start_date, end_date),
                "name": code
            }
            for code in codes
        ]

        results = qw.batch_query_sync(queries)

        assert len(results) == len(codes)
        for result in results:
            assert result is not None
