PREF="$HOME/.config/fontforge"
cd "`dirname "$0"`"
cp -a files/. $PREF
osascript -e 'tell application "Terminal" to quit' &
exit