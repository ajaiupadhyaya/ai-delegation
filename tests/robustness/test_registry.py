"""The §8.2 row registry: every row R1–R38 covered once, with its owner and outputs."""

from aideleg.robustness.registry import ROWS, Row, output_stem


def test_rows_cover_r1_to_r38():
    assert sorted(ROWS) == sorted(f"R{i}" for i in range(1, 39))
    assert all(isinstance(r, Row) and r.id == k for k, r in ROWS.items())


def test_r12_r13_owned_by_confirmatory_script():
    for rid in ("R12", "R13"):
        row = ROWS[rid]
        assert row.owner == "confirmatory_script"
        assert row.outputs == ("docs/results/confirmatory_h5.md",)
        assert row.task == ()


def test_plan4_rows_have_tasks():
    plan4 = [r for r in ROWS.values() if r.owner == "plan4"]
    assert len(plan4) == 36
    for r in plan4:
        assert r.task, r.id
        stem = output_stem(r.id)
        assert r.outputs == (
            f"docs/results/robustness/{stem}.csv",
            f"docs/results/robustness/{stem}.md",
        )


def test_output_stem_is_zero_padded():
    assert output_stem("R5") == "R05"
    assert output_stem("R38") == "R38"


def test_every_row_applies_to_something():
    assert all(r.applies_to for r in ROWS.values())
    assert ROWS["R10"].task == (8, 11)
    assert ROWS["R23"].task == (11, 12)
    assert ROWS["R10"].applies_to == ("H1", "H3", "H5", "H5b")
