"""
Phase J 測試：valuation_chart 模組
"""
import pytest
import plotly.graph_objects as go

from valuation_chart import plot_pe_river, plot_peer_comparison, _empty_pe_figure, _empty_peer_figure


class TestPlotPeRiver:
    def test_returns_figure(self):
        fig = plot_pe_river("2330", 3)
        assert isinstance(fig, go.Figure)

    def test_has_traces(self):
        fig = plot_pe_river("2330", 3)
        assert len(fig.data) > 0

    def test_unknown_stock(self):
        """不存在的股票回傳空圖"""
        fig = plot_pe_river("99999999", 1)
        assert isinstance(fig, go.Figure)

    def test_different_years(self):
        fig1 = plot_pe_river("2330", 1)
        fig5 = plot_pe_river("2330", 5)
        assert isinstance(fig1, go.Figure)
        assert isinstance(fig5, go.Figure)


class TestPlotPeerComparison:
    def test_returns_figure(self):
        fig = plot_peer_comparison(["2330", "2454"])
        assert isinstance(fig, go.Figure)

    def test_single_stock(self):
        fig = plot_peer_comparison(["2330"])
        assert isinstance(fig, go.Figure)

    def test_unknown_codes(self):
        fig = plot_peer_comparison(["99999999"])
        assert isinstance(fig, go.Figure)


class TestEmptyFigures:
    def test_empty_pe_figure(self):
        fig = _empty_pe_figure("測試原因")
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0

    def test_empty_peer_figure(self):
        fig = _empty_peer_figure("測試原因")
        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0
