#!/bin/bash
set -e
URL="https://dldir1v6.qq.com/weixin/Universal/Mac/WeChatMac.dmg"
DMG="/tmp/WeChatMac.dmg"
MNT="/Volumes/微信 WeChat"
APP="/Applications/WeChat.app"
APP2="/Applications/微信_副本.app"
ICON_URL="https://strike20023.github.io/wechat_blue_icon.icns"

sudo echo "start"
pkill -9 WeChat || true
[ -f "$DMG" ] && sudo rm -f "$DMG"

curl -L -o "$DMG" "$URL"
hdiutil detach "$MNT" -force || true
sleep 1
hdiutil attach "$DMG" -nobrowse

[ -d "$APP" ] && sudo rm -rf "$APP"
[ -d "$APP2" ] && sudo rm -rf "$APP2"
cp -R "$MNT/WeChat.app" /Applications/
cp -R "$MNT/WeChat.app" "$APP2"

hdiutil detach "$MNT" -force || true
sudo rm -f "$DMG"

sudo curl -L -o $APP2/Contents/Resources/AppIcon.icns "$ICON_URL"
sudo plutil -replace CFBundleIdentifier -string "com.tencent.WeiXin" $APP2/Contents/Info.plist
sudo codesign --force --deep --sign - $APP2
sudo xattr -r -d com.apple.quarantine $APP2

open $APP
open $APP2
