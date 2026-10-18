#!/bin/sh
# Assemble a self-contained LankaFeatures.glyphsPlugin into ./build and (with
# --install) copy it to the Glyphs 3 Plugins folder. Bundles lankafea from
# ../feature-generator/src so the plugin needs no pip install.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
src="$here/LankaFeatures.glyphsPlugin"
out="$here/build/LankaFeatures.glyphsPlugin"
plugins="$HOME/Library/Application Support/Glyphs 3/Plugins"

rm -rf "$here/build"
mkdir -p "$here/build"
cp -R "$src" "$out"

# Glyphs' Python plugin launcher is identical for every plugin; reuse one.
mkdir -p "$out/Contents/MacOS"
launcher=$(ls "$plugins"/*/Contents/MacOS/plugin 2>/dev/null | head -n 1 || true)
[ -n "$launcher" ] || { echo "no installed Glyphs Python plugin to borrow the launcher from" >&2; exit 1; }
cp "$launcher" "$out/Contents/MacOS/plugin"

cp -R "$here/../feature-generator/src/lankafea" "$out/Contents/Resources/lankafea"
# Vendor pure-Python PyYAML (glyphset YAMLs) if the generator's venv has it;
# without it the plugin falls back to the built-in codepoint tables.
yaml_dir=$(ls -d "$here"/../feature-generator/.venv/lib/*/site-packages/yaml 2>/dev/null | head -n 1 || true)
if [ -n "$yaml_dir" ]; then
  cp -R "$yaml_dir" "$out/Contents/Resources/yaml"
  find "$out/Contents/Resources/yaml" -name '*.so' -delete
fi
find "$out" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "built $out"
if [ "${1:-}" = "--install" ]; then
  rm -rf "$plugins/LankaFeatures.glyphsPlugin"
  cp -R "$out" "$plugins/"
  echo "installed — restart Glyphs"
fi
