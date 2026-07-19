"""Form-family / mark-system data — the reason some base+mark forms are NOT
simple composites.

Loaded from the design-stages source of truth
(`sinhala-design-stages/sinhala-design-dependencies.yaml`) so this tool stays in
sync with the taxonomy instead of hardcoding it. Sinhala mark attachment is not
uniform:

  ිී (ispilla)   — "every base+ි combination should be atomically designed for
                    quality"; each host belongs to a form-family (fam-i-ki,
                    fam-i-term fused, …). NOT a generic base+isign composite.
  ුූ (papilla)   — a regular below-join (සු) that IS a base+usign composite, but
                    special right-joined forms on ක ග ත භ ශ ඟ (u-special), plus
                    දු (du-form), ළු (llu-form) and රු (ra-forms) that are fused.
  ්  (halkirima) — four forms: default kodiya flag (a base+virama composite) but
                    fused rahena/trap/ja alternates on specific hosts.

Only rasign (rakaransaya, rakar anchor), repha (repaya anchor) and the
DEFAULT-class u/uu/virama attach as shape-invariant, anchor-driven composites.
The special/fused/atomic classes named above are recorded as keep-drawn with the
family as the reason.

Rakaransaya and repaya additionally have per-base exceptions
(`tools/_generated/shaping-exceptions.js`) whose forms are drawn specially.
"""
import json
import re
from pathlib import Path

from .lanka_data import REPO_ROOT, load_letters

DESIGN_DEPS_YAML = REPO_ROOT / "sinhala-design-stages" / "sinhala-design-dependencies.yaml"
SHAPING_EXCEPTIONS_JS = REPO_ROOT / "tools" / "_generated" / "shaping-exceptions.js"

# Sinhala letters present in the design taxonomy but not in the lanka letters
# table (rare sanyaka forms). Maps the character to its base-glyph latin stem.
CHAR_ALIASES = {"ඦ": "nyja"}


def _char_to_base_glyph(letters):
    """Sinhala character -> base glyph name (e.g. 'ක' -> 'ka-sinh')."""
    mapping = {char: f"{latin}-sinh" for latin, char in letters.items()}
    for char, latin in CHAR_ALIASES.items():
        mapping.setdefault(char, f"{latin}-sinh")
    return mapping


def _load_shaping_exception_chars():
    """Return {'rakaransaya': [...chars], 'repaya': [...], 'yansaya': [...]}
    parsed from the vendored JS. Multi-codepoint entries (e.g. 'ක්‍ෂ') are kept
    as-is; only single-letter entries resolve to a base glyph later."""
    text = SHAPING_EXCEPTIONS_JS.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (\{.*?\});\n  var EXPORTS", text, re.S)
    if not m:
        return {"rakaransaya": [], "repaya": [], "yansaya": []}
    return json.loads(m.group(1))


class Families:
    def __init__(self):
        self.letters = load_letters()
        self.char2base = _char_to_base_glyph(self.letters)
        deps = _read_yaml(DESIGN_DEPS_YAML)
        self.form_families = {
            k: v for k, v in deps.get("glyphs", {}).items()
            if v.get("type") == "form-family"
        }
        self._build_sets()

    def _bases(self, family_key):
        fam = self.form_families.get(family_key, {})
        return {self.char2base[c] for c in fam.get("hosts", []) if c in self.char2base}

    def _build_sets(self):
        # u/uu forms that are special or fused (not a base+usign composite)
        self.special_u_bases = (
            self._bases("u-special")
            | self._bases("du-form")
            | self._bases("llu-form")
            | self._bases("ra-forms")
        )
        # virama (al) forms that are fused alternates (not base+kodiya composite)
        self.special_hal_bases = (
            self._bases("hal-rahena")
            | self._bases("hal-trap")
            | self._bases("hal-ja")
            | self._bases("ra-forms")
        )
        # every ispilla (i/ii) host — atomically designed, never a generic composite
        self.ispilla_bases = set()
        self.ispilla_family_of = {}
        for key, fam in self.form_families.items():
            if fam.get("mark") == "ි":
                for base in (self.char2base[c] for c in fam.get("hosts", []) if c in self.char2base):
                    self.ispilla_bases.add(base)
                    self.ispilla_family_of[base] = key

        # per-base rakaransaya / repaya exceptions (single-letter entries only)
        exc = _load_shaping_exception_chars()
        self.rakaransaya_exception_bases = {
            self.char2base[c] for c in exc.get("rakaransaya", []) if c in self.char2base
        }
        self.repaya_exception_bases = {
            self.char2base[c] for c in exc.get("repaya", []) if c in self.char2base
        }

        # reason table for documenting keep-drawn forms
        self.u_family_of = {}
        for key in ("u-special", "du-form", "llu-form", "ra-forms"):
            for base in self._bases(key):
                self.u_family_of.setdefault(base, key)
        self.hal_family_of = {}
        for key in ("hal-rahena", "hal-trap", "hal-ja", "ra-forms"):
            for base in self._bases(key):
                self.hal_family_of.setdefault(base, key)


def _read_yaml(path):
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
