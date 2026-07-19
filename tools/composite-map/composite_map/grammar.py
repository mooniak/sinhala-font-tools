"""Sinhala composite-glyph name grammar, grounded in the form-family model.

Sinhala mark attachment is not uniform (see families.py), so a name like
`kU-sinh` is NOT mechanically `ka + usign`: කු is a special right-joined form.
This grammar therefore classifies each compositional-looking glyph name using
the family data:

  composite      genuinely base + a shape-invariant, anchor-driven mark:
                   • rasign (rakaransaya)      — all hosts except rakaransaya exceptions
                   • repha                     — all hosts except repaya exceptions
                   • usign / uusign (papilla)  — DEFAULT below-join hosts only
                   • virama (halkirima)        — DEFAULT kodiya hosts only
                   • ispilla (ිී) non-fused    — base + isign-sinh[.altN] (tier 3),
                     the alternate chosen from the anchor reference's iVowelAltN
                     classes (see ispilla.py)
  drawn          compositional by name but atomically designed or fused, so it
                 must stay drawn — carries the family as the reason:
                   • fused ispilla forms           → reason 'ispilla-fused'
                   • u-special/du-form/llu-form/ra → reason '<family>'
                   • hal-rahena/hal-trap/hal-ja/ra → reason '<family>'
                   • rakaransaya / repaya exceptions
  review         a sign form on a CONJUNCT base (kVa, cCa …) the family model
                 doesn't cover for u/uu/virama — a best-effort guess for a human
  None           not compositional (a plain base letter, a mark, a ligature)

ispilla and repha are classified for ANY base (plain or conjunct); u/uu/virama
and rasign are deterministic only for plain consonant bases, so conjunct forms
of those go to review.
"""
import re

# (name-stem suffix, sign glyph). 2-char suffixes first so `Ii`>`I`, `Uu`>`U`.
SIGN_SUFFIXES = [
    ("Ii", "iisign-sinh"),
    ("Uu", "uusign-sinh"),
    ("Ra", "rasign-sinh"),
    ("I", "isign-sinh"),
    ("U", "usign-sinh"),
]
ISPILLA_SIGNS = {"isign-sinh", "iisign-sinh"}
U_SIGNS = {"usign-sinh", "uusign-sinh"}
VIRAMA = "virama-sinh"
REPHA = "repha-sinh"

_NAME_RE = re.compile(r"^(?P<stem>.*)-sinh(?P<variant>\..*)?$")


def split_name(name):
    m = _NAME_RE.match(name)
    if not m:
        return None
    return m.group("stem"), (m.group("variant") or "")


class Grammar:
    def __init__(self, classification, glyph_names, families, ispilla):
        self.names = set(glyph_names)
        self.fam = families
        self.ispilla = ispilla
        self.consonants = list(classification["consonants"])          # 'ka', 'kha'
        self.plain_bases = {f"{c}-sinh" for c in self.consonants}      # 'ka-sinh'
        self.independent = set(classification["independent_vowels"])
        self.dep_signs = set(classification["dependent_signs"])
        self.marks = set(classification["other_marks"])

    # -- deterministic generation over PLAIN consonant bases ----------------
    def generate(self):
        """Return (composites, drawn) dicts for plain-consonant sign forms.
        `drawn` values are {'reason', 'components'} for documentation."""
        composites, drawn = {}, {}
        for cons in self.consonants:
            base = f"{cons}-sinh"
            stem = cons[:-1]
            self._emit(f"{stem}-sinh", base, VIRAMA, stem, composites, drawn)          # al-form
            for suffix, sign in SIGN_SUFFIXES:
                self._emit(f"{stem}{suffix}-sinh", base, sign, stem, composites, drawn)
        # repha (anchor-driven) over plain consonant bases
        for cons in self.consonants:
            base = f"{cons}-sinh"
            target = f"{cons}_repha-sinh"
            if target in self.names and REPHA in self.names:
                if base in self.fam.repaya_exception_bases:
                    drawn[target] = {"reason": "repaya-exception", "components": [base, REPHA]}
                else:
                    composites[target] = {"components": [base, REPHA], "tier": 2, "source": "grammar"}
        return composites, drawn

    def _emit(self, target, base, sign, stem, composites, drawn):
        if target == base or target not in self.names:
            return
        if sign in ISPILLA_SIGNS:
            spec = self._ispilla_spec(base, stem, long=(sign == "iisign-sinh"))
            if spec[0] == "composite":
                composites[target] = {"components": spec[1], "tier": 3, "source": "noto-ispilla"}
            else:
                drawn[target] = {"reason": spec[1], "components": [base, sign]}
            return
        if sign not in self.names:
            return
        verdict = self._verdict(base, sign)
        if verdict[0] == "composite":
            composites[target] = {"components": [base, sign], "tier": 1, "source": "grammar"}
        else:
            drawn[target] = {"reason": verdict[1], "components": [base, sign]}

    def _ispilla_spec(self, base, stem, long):
        """('composite', [base, isign-variant]) or ('drawn', 'ispilla-fused')."""
        if self.ispilla.is_fused(stem, long=long):
            return ("drawn", "ispilla-fused")
        return ("composite", [base, self.ispilla.component(base, long=long)])

    def _verdict(self, base, sign):
        """('composite', None) or ('drawn', reason) for a plain-consonant base
        + a u/uu/rasign/virama sign, per the family model. (ispilla is handled
        separately by _ispilla_spec.)"""
        if sign in U_SIGNS:
            if base in self.fam.special_u_bases:
                return ("drawn", self.fam.u_family_of.get(base, "u-special"))
            return ("composite", None)
        if sign == "rasign-sinh":
            if base in self.fam.rakaransaya_exception_bases:
                return ("drawn", "rakaransaya-exception")
            return ("composite", None)
        if sign == VIRAMA:
            if base in self.fam.special_hal_bases:
                return ("drawn", self.fam.hal_family_of.get(base, "hal-special"))
            return ("composite", None)
        return ("composite", None)

    # -- classify an arbitrary -sinh name (used for the remaining names) ----
    def classify(self, name):
        """Return one of:
          ('composite', [base, sign])
          ('drawn', reason, [base, sign])
          ('review', [base, sign])
          None
        """
        parts = split_name(name)
        if not parts:
            return None
        stem, _variant = parts

        # a plain base letter or a mark/sign glyph itself is not a target
        if stem in {c for c in self.consonants} or stem in self.independent \
                or stem in self.dep_signs or stem in self.marks:
            return None

        # repha (anchor-driven on ANY base, incl. conjuncts)
        if "_repha" in stem:
            core = stem.split("_repha")[0]
            base = self._base_glyph(core)
            if base is None:
                return None
            if base in self.fam.repaya_exception_bases:
                return ("drawn", "repaya-exception", [base, REPHA])
            return ("composite", [base, REPHA])
        if "_" in stem:
            return None  # multi-part combos (yasign_isign, dae._c …) — leave alone

        for suffix, sign in SIGN_SUFFIXES:
            if stem.endswith(suffix) and len(stem) > len(suffix):
                prefix = stem[: -len(suffix)]
                base = self._base_glyph(prefix)
                if base is None:
                    return None
                return self._classify_with_base(base, sign)

        # al-form (bare stem + virama)
        base = self._base_glyph(stem)
        if base is not None and base != name:
            return self._classify_with_base(base, VIRAMA)
        return None

    def _classify_with_base(self, base, sign):
        # ispilla applies to ANY base (plain or conjunct) via the mined model
        if sign in ISPILLA_SIGNS:
            spec = self._ispilla_spec(base, self._stem_of(base), long=(sign == "iisign-sinh"))
            if spec[0] == "composite":
                return ("composite", spec[1])
            return ("drawn", spec[1], [base, sign])
        if base in self.plain_bases:
            verdict = self._verdict(base, sign)
            if verdict[0] == "composite":
                return ("composite", [base, sign])
            return ("drawn", verdict[1], [base, sign])
        # u/uu/virama/rasign on a conjunct base: family model doesn't cover it
        return ("review", [base, sign])

    @staticmethod
    def _stem_of(base):
        core = base[:-len("-sinh")] if base.endswith("-sinh") else base
        return core[:-1] if core.endswith("a") else core

    def _base_glyph(self, core):
        """core like 'k' or 'nD' -> base glyph 'ka-sinh' / 'nDa-sinh' if present."""
        cand = f"{core}a-sinh"
        if cand in self.names:
            return cand
        cand2 = f"{core}-sinh"
        if cand2 in self.names:
            return cand2
        return None
