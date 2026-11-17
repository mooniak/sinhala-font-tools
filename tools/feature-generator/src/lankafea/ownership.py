"""Who owns a block of layout code in a Glyphs source — per script.

lankafea only ever rewrites code it generated itself, recognised by an ownership
marker. That was enough while a source held one script. Abhaya Libre carries Sinhala
AND Tamil, with the same feature tags twice (``akhn`` for ``sinh``, ``akhn`` for
``taml``/``tml2``), so ownership, class bookkeeping and hand-written collisions all
have to be per script, or generating Tamil would delete the Sinhala features (and the
classes they use) and ``--replace-tags akhn`` would delete both hand-written ones.

Pure functions over strings, shared by the library (``glyphsource``) and by the Glyphs
plugin, which writes to the live font through the Glyphs API instead of glyphsLib.
"""

from __future__ import annotations

import re

# Ownership marker: the first line of every generated feature / prefix.
MARKER = "# lankafea:generated v1 — do not edit; regenerate with lankafea"
GENERATED_PREFIX = "# lankafea:generated"
# In a multi-script source a second line says which script the block is for.
SCRIPT_LINE = "# lankafea:script "

MANIFEST_PREFIX = "lankafea-manifest"
INJECTED_PREFIX = "lankafea-injected"
LANGUAGESYSTEMS_PREFIX = "Languagesystems"

# script key -> its OpenType script tags / its glyph-name namespace
SCRIPT_TAGS = {"sinhala": {"sinh"}, "tamil": {"taml", "tml2"}}
NAMESPACES = {"sinhala": "sinh", "tamil": "taml"}

_NS_RE = re.compile(r"-(sinh|taml)(?![A-Za-z])")
_SCRIPT_STMT = re.compile(r"^\s*script\s+(\w{4})\s*;", re.M)


def header(script: str | None = None, scoped: bool = False) -> str:
    """The marker, plus the script line when the source holds more than one script."""
    return MARKER + (f"\n{SCRIPT_LINE}{script}" if scoped and script else "")


def is_generated(code: str | None) -> bool:
    return (code or "").lstrip().startswith(GENERATED_PREFIX)


def namespaces_in(code: str | None) -> set[str]:
    """The script namespaces (sinh / taml) whose glyph names the code uses."""
    return set(_NS_RE.findall(code or ""))


def _script_of_namespace(ns: str) -> str | None:
    return next((k for k, v in NAMESPACES.items() if v == ns), None)


def owner_script(code: str | None) -> str | None:
    """Which script generated this block, or ``None`` if it cannot be told.

    Read from the ``# lankafea:script`` line when there is one; otherwise inferred
    from the glyph names the block uses (a marked block written before scripts were
    tracked still has an owner if it only mentions one script's glyphs)."""
    text = (code or "").lstrip()
    for line in text.splitlines()[:3]:
        if line.startswith(SCRIPT_LINE):
            return line[len(SCRIPT_LINE):].strip() or None
    found = namespaces_in(text)
    if len(found) == 1:
        return _script_of_namespace(next(iter(found)))
    return None


def owned_by(code: str | None, script: str | None) -> bool:
    """Is this generated block ours to rewrite when generating ``script``?

    ``script=None`` is the single-script behaviour: every generated block is ours.
    A generated block of unknown owner is also ours (as before); one that belongs to
    another script is not."""
    if not is_generated(code):
        return False
    if script is None:
        return True
    owner = owner_script(code)
    return owner is None or owner == script


def scoped_tags(code: str | None) -> set[str]:
    """OpenType script tags a hand-written feature restricts itself to (``script
    taml;``). Empty means it is not scoped, so it applies to every script."""
    return set(_SCRIPT_STMT.findall(code or ""))


def collides(user_code: str | None, script: str | None) -> bool:
    """Does a hand-written feature clash with the one we would generate?

    Only if it can affect the same script: unscoped, or scoped to one of ours."""
    if is_generated(user_code):
        return False
    if script is None:
        return True
    tags = scoped_tags(user_code)
    return not tags or bool(tags & SCRIPT_TAGS.get(script, set()))


def is_multi_script(glyph_names) -> bool:
    """True when the source has glyphs in more than one script namespace."""
    seen: set[str] = set()
    for name in glyph_names:
        seen.update(namespaces_in(name))
        if len(seen) > 1:
            return True
    return False


# ---- the class manifest: which classes are ours to strip, per script ------------ #

def parse_manifest(code: str | None) -> dict[str | None, list[str]]:
    """``# classes: a b`` (script unknown) and ``# classes tamil: c d`` lines."""
    out: dict[str | None, list[str]] = {}
    for line in (code or "").splitlines():
        m = re.match(r"# classes(?: (\w+))?:(.*)$", line)
        if m:
            out.setdefault(m.group(1), []).extend(m.group(2).split())
    return out


def owned_class_names(manifest_code: str | None, script: str | None,
                      class_code: dict[str, str] | None = None) -> set[str]:
    """Class names this run may replace.

    With ``script=None`` that is every listed class. Otherwise the classes listed for
    the script, plus classes listed without one whose members are only that script's
    glyphs (or whose owner cannot be told)."""
    listed = parse_manifest(manifest_code)
    if script is None:
        return {n for names in listed.values() for n in names}
    out = set(listed.get(script, ()))
    for name in listed.get(None, ()):
        owner = owner_script((class_code or {}).get(name, ""))
        if owner is None or owner == script:
            out.add(name)
    return out


def manifest_code(existing: str | None, script: str | None, scoped: bool,
                  written: list[str], class_code: dict[str, str] | None = None) -> str:
    """The manifest to write: this script's classes, with other scripts' kept."""
    lines = [header(script, scoped)]
    if script is None:
        lines.append("# classes: " + " ".join(written))
        return "\n".join(lines)
    listed = parse_manifest(existing)
    for other, names in sorted(listed.items(), key=lambda kv: kv[0] or ""):
        if other == script:
            continue
        if other is None:
            # unscoped names: ours get rewritten, another script's are kept
            names = [n for n in names
                     if owner_script((class_code or {}).get(n, "")) not in (None, script)]
            if not names:
                continue
            lines.append("# classes: " + " ".join(names))
        else:
            lines.append(f"# classes {other}: " + " ".join(names))
    lines.append(f"# classes {script}: " + " ".join(written))
    return "\n".join(lines)


# ---- language systems ------------------------------------------------------------- #

def merge_languagesystems(existing: str | None, wanted: dict[str, list[str]]) -> str:
    """A generated ``Languagesystems`` prefix that keeps other scripts' lines and adds
    this script's missing ones, so scripts can be generated one after the other."""
    have = [ln.strip() for ln in (existing or "").splitlines()
            if ln.strip().startswith("languagesystem")]
    for tag, langs in wanted.items():
        for lang in langs:
            line = f"languagesystem {tag} {lang};"
            if line not in have:
                have.append(line)
    return MARKER + "\n" + "\n".join(have)
