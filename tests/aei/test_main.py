import polars as pl

from aideleg.aei import __main__ as cli
from aideleg.aei.panel import QualityReport


def _run(monkeypatch, tmp_path, ok: bool):
    panel = tmp_path / "aei_panel.parquet"
    panel.write_bytes(b"stale")
    monkeypatch.setattr(cli, "PANEL", panel)
    monkeypatch.setattr(cli, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr(cli, "build_panel", lambda write=False: pl.DataFrame({"a": [1]}))
    monkeypatch.setattr(cli, "check_panel",
                        lambda df: QualityReport({"x": (ok, "detail")}))
    written = []
    monkeypatch.setattr(cli, "write_panel", lambda df: written.append(df) or panel)
    return cli.main(), panel, written


def test_failed_check_removes_stale_panel(monkeypatch, tmp_path):
    code, panel, written = _run(monkeypatch, tmp_path, ok=False)
    assert code == 1
    assert not panel.exists()
    assert written == []
    assert "FAIL" in (tmp_path / "report.md").read_text()


def test_passing_check_writes_panel(monkeypatch, tmp_path):
    code, panel, written = _run(monkeypatch, tmp_path, ok=True)
    assert code == 0 and len(written) == 1
