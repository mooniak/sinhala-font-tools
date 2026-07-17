"""Fix the Mooniak foundry fields on a font source's info.

``designerURL``/``manufacturer`` live in Glyphs' ``properties`` (localized,
default-language); ``vendorID`` is a standard Glyphs custom parameter (maps to
OpenType OS/2 ``achVendID`` on build) and is absent from every sampled source.
"""

from __future__ import annotations

DESIGNER_URL = "http://www.mooniak.com/"
MANUFACTURER = "mooniak"
VENDOR_ID = "MNIK"


def fix_font_metadata(font, designer_url: str = DESIGNER_URL,
                       manufacturer: str = MANUFACTURER,
                       vendor_id: str = VENDOR_ID) -> list[str]:
    """Set designerURL/manufacturer/vendorID on a loaded GSFont.

    Returns the list of field names actually changed.
    """
    changed: list[str] = []
    if font.designerURL != designer_url:
        font.designerURL = designer_url
        changed.append("designerURL")
    if font.manufacturer != manufacturer:
        font.manufacturer = manufacturer
        changed.append("manufacturers")
    if font.customParameters["vendorID"] != vendor_id:
        font.customParameters["vendorID"] = vendor_id
        changed.append("vendorID")
    return changed
