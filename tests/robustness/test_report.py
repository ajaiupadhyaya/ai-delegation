"""Robustness row writer and number formatting (Global Constraints)."""

import csv

import pytest

from aideleg.robustness import report, upstream


def _record(**kw) -> dict:
    r = {
        "row_id": "R5",
        "part": "ew",
        "variant": "rs=ff49_ew",
        "applies_to": "H5",
        "label": "robustness",
        "estimand": "slope",
        "unit": report.MARKET_UNIT,
        "estimate": 1.23456,
        "scale": 2.5,
        "ci_lo": -3.9,
        "ci_hi": 6.4,
        "stat": 0.1234,
        "p": 0.9031,
        "null": "b = bbar",
        "crit_0025": 2.4138,
        "crit_005": 2.0796,
        "n": 49,
        "n_dropped": 0,
        "dropped": "",
        "note": "secondary b = 0: T = 0.494, p = 0.626",
    }
    r.update(kw)
    return r


def test_fmt_p():
    assert report.fmt_p(0.0004) == "< 0.001"
    assert report.fmt_p(0.01234) == "0.012"
    assert report.fmt_p(0.001) == "0.001"


def test_fmt_pp_and_rho():
    assert report.fmt_pp(1.234) == "1.23"
    assert report.fmt_pp(-0.004) == "-0.00"
    assert report.fmt_rho(0.76312) == "0.763"


def test_write_row_schema(tmp_path):
    bad = _record()
    del bad["note"]
    with pytest.raises(ValueError, match="note"):
        report.write_row("R5", [bad], [], out_dir=tmp_path)
    with pytest.raises(ValueError, match="extra"):
        report.write_row("R5", [_record(extra=1)], [], out_dir=tmp_path)
    csv_path, md_path = report.write_row(
        "R5",
        [_record(), _record(applies_to="H5b")],
        ["**[default]** something (§11 C-64)."],
        out_dir=tmp_path,
    )
    assert csv_path == tmp_path / "R05.csv" and md_path == tmp_path / "R05.md"
    with csv_path.open() as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == report.ROBUSTNESS_COLUMNS
    assert len(rows) == 3
    assert float(rows[1][report.ROBUSTNESS_COLUMNS.index("estimate")]) == 1.23456
    text = md_path.read_text()
    assert text.rstrip("\n").splitlines()[-1] == upstream.WORDING
    assert "R5" in text.splitlines()[0] and "PAP §8.2" in text
    assert "reported as robustness; not a confirmatory decision (PAP §8.1)" in text
    assert "**[default]** something (§11 C-64)." in text
    assert "| H5 |" in text and "1.23" in text and "0.903" in text


def test_write_row_refuses_unknown_row(tmp_path):
    with pytest.raises(ValueError, match="R00"):
        report.write_row("R00", [_record(row_id="R00")], [], out_dir=tmp_path)
