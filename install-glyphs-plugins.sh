#!/bin/sh
# Install this repo's Glyphs 3 plugins into the Glyphs 3 Plugins folder:
#
#   Sinhala Glyph Builder  tools/composite-map/glyphs-plugin/
#   Sinhala Spacing        tools/spacing-map/glyphs-plugin/
#   Lanka Features         tools/feature-generator/glyphs-plugin/ (built first)
#
# Plugins are symlinked, so a `git pull` (or a plugin rebuild) takes effect on
# the next Glyphs restart. Use --copy for standalone copies that keep working
# if this checkout moves or is deleted (re-run the script to update them).
#
#   ./install-glyphs-plugins.sh             link all three
#   ./install-glyphs-plugins.sh --copy      copy instead of link
#   ./install-glyphs-plugins.sh --uninstall remove them
#
# A plugin of the same name that is already installed as a real folder (not a
# link, e.g. from the Plugin Manager) is moved to the Trash, not deleted.
set -eu

repo=$(cd "$(dirname "$0")" && pwd)
plugins="$HOME/Library/Application Support/Glyphs 3/Plugins"
marker=.installed-by-sinhala-font-design
mode=link
case "${1:-}" in
  "") ;;
  --copy) mode=copy ;;
  --uninstall) mode=uninstall ;;
  -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

[ "$(uname)" = Darwin ] || { echo "Glyphs plugins install on macOS only" >&2; exit 1; }
mkdir -p "$plugins"

# Remove whatever is installed under this name: links and our own copies go,
# anything else goes to the Trash.
clear_slot() {
  dest="$plugins/$1"
  if [ -L "$dest" ]; then
    rm "$dest"
  elif [ -e "$dest/$marker" ]; then
    rm -rf "$dest"
  elif [ -e "$dest" ]; then
    trash="$HOME/.Trash/$1.$(date +%Y%m%d-%H%M%S)"
    mv "$dest" "$trash"
    echo "  moved existing $1 to the Trash"
  fi
}

install_bundle() {  # name, source bundle
  clear_slot "$1"
  if [ "$mode" = copy ]; then
    cp -R "$2" "$plugins/$1"
    find "$plugins/$1" -name __pycache__ -type d -prune -exec rm -rf {} +
    echo "copied from $repo" > "$plugins/$1/$marker"
  else
    ln -s "$2" "$plugins/$1"
  fi
  echo "installed $1"
}

if [ "$mode" = uninstall ]; then
  for name in SinhalaGlyphBuilder SinhalaSpacing LankaFeatures SinhalaComposites; do
    if [ -e "$plugins/$name.glyphsPlugin" ] || [ -L "$plugins/$name.glyphsPlugin" ]; then
      clear_slot "$name.glyphsPlugin"
      echo "removed $name.glyphsPlugin"
    fi
  done
  exit 0
fi

# Sinhala Glyph Builder was called Sinhala Composites; drop a stale link.
[ -L "$plugins/SinhalaComposites.glyphsPlugin" ] && rm "$plugins/SinhalaComposites.glyphsPlugin" \
  && echo "removed old SinhalaComposites.glyphsPlugin link"

# These two are committed ready to run (bundled data and plugin launcher).
install_bundle SinhalaGlyphBuilder.glyphsPlugin \
  "$repo/tools/composite-map/glyphs-plugin/SinhalaGlyphBuilder.glyphsPlugin"
install_bundle SinhalaSpacing.glyphsPlugin \
  "$repo/tools/spacing-map/glyphs-plugin/SinhalaSpacing.glyphsPlugin"

# Lanka Features is assembled by build.sh (bundles lankafea, and borrows the
# launcher from one of the plugins just installed).
"$repo/tools/feature-generator/glyphs-plugin/build.sh" >/dev/null
install_bundle LankaFeatures.glyphsPlugin \
  "$repo/tools/feature-generator/glyphs-plugin/build/LankaFeatures.glyphsPlugin"

echo
echo "Done. Restart Glyphs 3; the plugins are in the Glyph menu."
