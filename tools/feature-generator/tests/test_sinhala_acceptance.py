"""Acceptance: the generated Sinhala features shape like each font's hand-written ones,
except where a difference is known and tracked.

Runs against the real fonts in the sibling font-repos checkout and is skipped without
it (CI has none). See acceptance_sinhala.py for the corpus, how both feature sets are
compiled into the same synthetic font, and the difference categories; run
`python tests/acceptance_sinhala.py` for the full report.
"""

from __future__ import annotations

import pytest

import acceptance_sinhala as A


@pytest.mark.parametrize("key", list(A.CASES))
def test_every_difference_is_known(key, tmp_path):
    case = A.CASES[key]
    if not A.available(case):
        pytest.skip(f"{key}: source not found")
    r = A.run(key, tmp_path)
    bad = r.unexplained()
    assert not bad, "unexplained differences:\n" + "\n".join(
        f"  [{d.feature}] {d.label!r}: hand {d.hand} vs generated {d.generated}"
        for d in bad[:8])
    # The corpus covered the grid, the clusters and the texts.
    assert r.total["default"] > 10_000


def test_hidden_zwj_is_not_a_difference(tmp_path):
    """HarfBuzz shows a ZWJ no rule consumed as a zero-advance space; it is invisible."""
    from lankafea.inventory import FontInventory
    inv = FontInventory({"space", "ka-sinh", "zerowidthjoiner"}, {0x20, 0x0D9A, 0x200D},
                        {0x20: "space", 0x0D9A: "ka-sinh", 0x200D: "zerowidthjoiner"})
    font = A.synthetic_font(inv, "languagesystem sinh dflt;\n", tmp_path / "z.ttf")
    names, _ = A.Shaper(font).shape("ක‍ක")
    assert names == ["ka-sinh", "ka-sinh"]
    names, _ = A.Shaper(font).shape("ක ක")
    assert names == ["ka-sinh", "space", "ka-sinh"]      # a real space stays


def test_known_items_are_recognised():
    mk = lambda hand, gen, text="", feature="default", section="grid": A.Difference(
        feature, section, "x", text, hand, gen)
    r = A.Result(A.CASES["abhaya"])
    assert A.categorise(mk(["cU-sinh"], ["cCU-sinh"]), r, [], []) == "A1"
    # G6 is fixed: a ._c form in default shaping is a regression, not a known item.
    assert A.categorise(mk(["da-sinh", "aasign-sinh"], ["daa._c-sinh"]), r, [], []) == "unexplained"
    assert A.categorise(mk(["ka-sinh"], ["kha-sinh"]), r, [], []) == "unexplained"
    r.hand_unreachable = {"ndRa-sinh"}
    assert A.categorise(mk(["nda-sinh", "rasign-sinh"], ["ndRa-sinh"]), r, [], []) == "reach"
    # Under a stylistic feature, a difference that grows out of a default-run reach is
    # that reach (ss01 turns the generated ndRa into ndRaa._c; the hand never forms ndRa).
    hand = ["nda-sinh", "rasign-sinh", "aasign-sinh"]
    assert A.categorise(mk(hand, ["ndRaa._c-sinh"], feature="ss01"), r,
                        hand, ["ndRa-sinh", "aasign-sinh"]) == "reach"
