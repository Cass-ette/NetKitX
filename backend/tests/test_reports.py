"""Tests for report export service and API."""

from datetime import datetime

from app.services.report_service import render_html, _format_duration, _extract_columns


class FakeTask:
    """Minimal task-like object for testing without a database."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.plugin_name = kwargs.get("plugin_name", "nmap-scan")
        self.status = kwargs.get("status", "done")
        self.params = kwargs.get("params", {"target": "192.168.1.0/24"})
        self.result = kwargs.get("result", {"items": []})
        self.created_by = kwargs.get("created_by", 1)
        self.created_at = kwargs.get("created_at", datetime(2025, 1, 15, 10, 0, 0))
        self.started_at = kwargs.get("started_at", datetime(2025, 1, 15, 10, 0, 0))
        self.finished_at = kwargs.get("finished_at", datetime(2025, 1, 15, 10, 2, 30))


class TestFormatDuration:
    def test_normal_duration(self):
        task = FakeTask()
        assert _format_duration(task) == "2m 30s"

    def test_short_duration(self):
        task = FakeTask(
            started_at=datetime(2025, 1, 15, 10, 0, 0),
            finished_at=datetime(2025, 1, 15, 10, 0, 45),
        )
        assert _format_duration(task) == "45s"

    def test_no_timestamps(self):
        task = FakeTask(started_at=None, finished_at=None)
        assert _format_duration(task) == "N/A"


class TestExtractColumns:
    def test_empty_items(self):
        assert _extract_columns([]) == []

    def test_extracts_keys(self):
        items = [{"host": "10.0.0.1", "port": 80, "service": "http"}]
        assert _extract_columns(items) == ["host", "port", "service"]


class TestRenderHtml:
    def test_basic_render(self):
        task = FakeTask(
            result={"items": [{"host": "10.0.0.1", "port": 80}]},
        )
        html = render_html(task)
        assert "NetKitX Report" in html
        assert "nmap-scan" in html
        assert "10.0.0.1" in html
        assert "80" in html

    def test_empty_results(self):
        task = FakeTask(result={"items": []})
        html = render_html(task)
        assert "No result items" in html

    def test_params_displayed(self):
        task = FakeTask(params={"target": "example.com", "ports": "1-1000"})
        html = render_html(task)
        assert "example.com" in html
        assert "1-1000" in html

    def test_no_params(self):
        task = FakeTask(params=None)
        html = render_html(task)
        assert "NetKitX Report" in html

    def test_multiple_items(self):
        items = [
            {"host": "10.0.0.1", "port": 22, "service": "ssh"},
            {"host": "10.0.0.1", "port": 80, "service": "http"},
            {"host": "10.0.0.2", "port": 443, "service": "https"},
        ]
        task = FakeTask(result={"items": items})
        html = render_html(task)
        assert "ssh" in html
        assert "https" in html
        assert html.count("<tr>") >= 4  # header + 3 data rows
