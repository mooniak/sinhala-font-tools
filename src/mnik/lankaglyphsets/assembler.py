"""Order the IR canonically and hand it to a backend to serialize."""

from __future__ import annotations

from .model import FeatureDoc
from .feacomposer_adapter import get_backend, TextBackend

# Canonical OpenType feature order (registration order matters for the shaper).
FEATURE_ORDER = [
    "ccmp", "locl", "akhn", "rphf", "blwf", "half", "pstf", "vatu", "cjct",
    "pres", "abvs", "blws", "psts", "haln", "calt", "dist",
    "aalt",
    *[f"ss{n:02d}" for n in range(1, 21)],
]


def order_features(doc: FeatureDoc) -> FeatureDoc:
    rank = {tag: i for i, tag in enumerate(FEATURE_ORDER)}
    doc.features.sort(key=lambda f: rank.get(f.tag, len(FEATURE_ORDER)))
    return doc


def assemble(doc: FeatureDoc, language_systems: dict[str, list[str]],
             prefer_feacomposer: bool = True) -> str:
    order_features(doc)
    backend = get_backend(prefer_feacomposer=prefer_feacomposer)
    try:
        return backend.serialize(doc, language_systems)
    except Exception:
        if backend.name == "text":
            raise
        # feacomposer API drift / unsupported construct -> reliable text backend.
        return TextBackend().serialize(doc, language_systems)
