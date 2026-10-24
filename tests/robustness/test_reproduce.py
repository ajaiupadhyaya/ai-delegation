"""PAP §11 C-80: a regenerated robustness CSV that reproduces the committed one within the
summation-order tolerance keeps the committed bytes; a real difference, or any .md difference,
rewrites it."""

from aideleg.robustness import report
from aideleg.robustness.reproduce import csv_equivalent


def _record(**kw) -> dict:
    r = {c: None for c in report.ROBUSTNESS_COLUMNS}
    r.update(
        row_id="R5",
        part="market",
        variant="v",
        applies_to="H5",
        label="robustness",
        estimand="slope",
        unit=report.MARKET_UNIT,
        estimate=1.0,
        n=49,
        note="",
    )
    r.update(kw)
    return r


HEAD = "a,b,c\nx,1.9584125416694946,\ny,0.0,-3\n"


def test_csv_equivalent_last_digits():
    assert csv_equivalent(HEAD, HEAD)
    assert csv_equivalent(HEAD, "a,b,c\nx,1.958412541669495,\ny,0.0,-3\n")
    assert csv_equivalent(HEAD, "a,b,c\nx,1.9584125416694946,\ny,1e-13,-3\n")  # near zero


def test_csv_equivalent_real_differences():
    assert not csv_equivalent(HEAD, "a,b,c\nx,1.9584125,\ny,0.0,-3\n")
    assert not csv_equivalent(HEAD, "a,b,c\nz,1.9584125416694946,\ny,0.0,-3\n")
    assert not csv_equivalent(HEAD, "a,b,d\nx,1.9584125416694946,\ny,0.0,-3\n")
    assert not csv_equivalent(HEAD, "a,b,c\nx,1.9584125416694946,1\ny,0.0,-3\n")
    assert not csv_equivalent(HEAD, "a,b,c\nx,1.9584125416694946,\n")
    assert not csv_equivalent(HEAD, "a,b,c\nx,1.9584125416694946,\ny,1e-11,-3\n")


def _write(tmp_path, recs, notes=()):
    return report.write_row("R5", recs, list(notes), out_dir=tmp_path)


def test_write_row_keeps_bytes_on_last_digit_difference(tmp_path):
    csv_path, md_path = _write(tmp_path, [_record(estimate=1.9584125416694946)])
    before = csv_path.read_bytes()
    _write(tmp_path, [_record(estimate=1.958412541669495)])
    assert csv_path.read_bytes() == before


def test_write_row_rewrites_on_real_difference(tmp_path):
    csv_path, _ = _write(tmp_path, [_record(estimate=1.9584125416694946)])
    _write(tmp_path, [_record(estimate=1.9584)])
    assert "1.9584," in csv_path.read_text()
    assert "1.9584125416694946" not in csv_path.read_text()


def test_write_row_rewrites_on_md_difference(tmp_path):
    csv_path, md_path = _write(tmp_path, [_record(estimate=1.9584125416694946)])
    _write(tmp_path, [_record(estimate=1.958412541669495)], notes=["another note"])
    assert "another note" in md_path.read_text()
    assert "1.958412541669495," in csv_path.read_text()


def _rq1(**kw):
    return _record(
        row_id="R38",
        part="oneway_occ",
        applies_to="H1",
        estimand="log_wage",
        unit="pp of the outcome share per unit of the regressor",
        note="x",
        **kw,
    )


def test_rq1_writer_keeps_bytes_on_last_digit_difference(tmp_path):
    """`rows._write` rewrites the CSV from the unlabelled records (C-78); it keeps the
    committed bytes under the same C-80 rule (R28 is written this way)."""
    from aideleg.robustness import rows

    csv_path, _ = rows._write("R38", [_rq1(estimate=4.395154698336432)], [], tmp_path)
    before = csv_path.read_bytes()
    assert b"log_wage" in before
    rows._write("R38", [_rq1(estimate=4.395154698336436)], [], tmp_path)
    assert csv_path.read_bytes() == before
    rows._write("R38", [_rq1(estimate=4.3951)], [], tmp_path)
    assert b"4.3951," in csv_path.read_bytes()
    rows._write("R38", [_rq1(estimate=4.395154698336436)], ["new note"], tmp_path)
    assert b"4.395154698336436" in csv_path.read_bytes()
