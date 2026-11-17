"""Acceptance: the generated Tamil features shape like each font's hand-written ones.

Runs against the real fonts in the sibling font-repos checkout and is skipped without
it (CI has none). See acceptance_tamil.py for what is compared and how a difference is
explained; run `python tests/acceptance_tamil.py` for the full report.
"""

from __future__ import annotations

import pytest

import acceptance_tamil as A


@pytest.mark.parametrize("key", list(A.CASES))
def test_generated_features_shape_like_the_hand_written(key, tmp_path):
    case = A.CASES[key]
    if not A.available(case):
        pytest.skip(f"{key}: source, build or alias table not found")
    r = A.run(key, tmp_path)

    # Every difference must be explained: only glyphs the hand-written features never
    # reach, which the generated ones now do.
    bad = r.unexplained()
    assert not bad, "unexplained differences:\n" + "\n".join(
        f"  {d.label!r}: hand {d.hand} vs generated {d.generated}" for d in bad[:8])
    bad_t = r.unexplained(traditional=True)
    assert not bad_t, "unexplained traditional differences:\n" + "\n".join(
        f"  {d.label!r}: hand {d.hand} vs generated {d.generated}" for d in bad_t[:8])
    # ...and they are the exception: nearly everything is identical.
    assert r.same / r.total > 0.95, f"{key}: only {r.same}/{r.total} identical"
    # The full grid (24 x 13) and both spellings of ஸ்ரீ were part of the corpus.
    assert r.total >= 24 * 13 + 2


def test_abhaya_the_descriptive_pole_matches_exactly(tmp_path):
    """Abhaya Libre draws a glyph for every outcome. The generated features must
    reproduce its shaping exactly, in the default features and in ss09."""
    case = A.CASES["abhaya"]
    if not A.available(case):
        pytest.skip("abhaya: source, build or alias table not found")
    r = A.run("abhaya", tmp_path)
    assert r.differences == [] and r.traditional_differences == []
    assert r.traditional_comparable


def test_a_difference_is_explained_only_by_glyphs_the_hand_written_cannot_output():
    r = A.Result(A.CASES["ralex"], hand_unreachable={"lI-taml"})
    mk = lambda hand, gen: A.Difference("grid", "x", "x", hand, gen)
    # the generated side uses a glyph the hand-written features never output
    assert r.explained(mk(["la-taml", "isign-taml.alt3"], ["lI-taml"]))
    # a glyph the hand-written features CAN output, used differently: not explained
    assert not r.explained(mk(["la-taml", "isign-taml.alt3"], ["la-taml", "isign-taml"]))
    # nothing new on the generated side (a glyph dropped): not explained
    assert not r.explained(mk(["la-taml", "isign-taml"], ["la-taml"]))
