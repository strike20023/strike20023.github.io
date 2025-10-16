
#!/bin/bash
set -e
URL="https://dldir1v6.qq.com/weixin/Universal/Mac/WeChatMac.dmg"
DMG="/tmp/WeChatMac.dmg"
MNT="/Volumes/微信 WeChat"
APP="/Applications/WeChat.app"
APP2="/Applications/微信_副本.app"
ICON_URL="https://strike20023.github.io/wechat_blue_icon.icns"
sudo ls
pkill -9 WeChat || true
[ -f "$DMG" ] && rm -f "$DMG"
curl -L -o "$DMG" "$URL"
hdiutil detach "$MNT" -force || true
sleep 1
hdiutil attach "$DMG" -nobrowse
[ -d "$APP" ] && rm -rf "$APP"
cp -R "$MNT/WeChat.app" /Applications/
hdiutil detach "$MNT" -force || true
rm -f "$DMG"

cp -r $APP $APP2

sudo curl -L -o $APP2/Contents/Resources/AppIcon.icns "$ICON_URL"
sudo plutil -replace CFBundleIdentifier -string "com.tencent.WeiXin" $APP2/Contents/Info.plist
sudo codesign --force --deep --sign - $APP2
sudo xattr -r -d com.apple.quarantine $APP2

