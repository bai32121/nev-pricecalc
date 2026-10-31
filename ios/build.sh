#!/usr/bin/env bash
# 构建 iOS 未签名 IPA（供自签工具使用）
# 用法：./build.sh            —— macOS 上直接跑
#       CI 里也是跑这一个脚本，保证本地与云端产物一致
# 依赖：xcodegen（CI 里由 brew 安装；本机先 brew install xcodegen）
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="NEVPriceCalc"
OUT="build/${APP_NAME}-unsigned.ipa"

# ---- 1. 同步最新网页（唯一的内容来源是根目录的 车价计算器.html）----
if [ -f "../车价计算器.html" ]; then
  cp "../车价计算器.html" "Resources/index.html"
  echo "· 页面已同步：$(du -h Resources/index.html | cut -f1)"
else
  echo "!! 找不到 ../车价计算器.html，沿用现有的 Resources/index.html"
fi

# ---- 2. 生成 xcodeproj ----
if ! command -v xcodegen >/dev/null 2>&1; then
  echo "缺少 xcodegen，先执行：brew install xcodegen" >&2
  exit 1
fi
echo "· 生成 Xcode 工程"
xcodegen generate --quiet

# ---- 2.5 兜底层：确保工程格式老到任何 Xcode 都愿意打开 ----
# project.yml 里已指定 projectFormat: xcode14_0，但 XcodeGen 的默认值会随
# 版本漂移（2.44 的默认已经是 xcode16_0 = objectVersion 77）。这里再拦一道：
# 只要发现 objectVersion 是 7x，就压回 56，免得又撞上
# "The project could not be opened because it is in a future Xcode project file format"
PBX="${APP_NAME}.xcodeproj/project.pbxproj"
if [ -f "$PBX" ] && grep -q 'objectVersion = 7' "$PBX"; then
  echo "· 工程格式偏新，降级到 Xcode 14 (objectVersion 56)"
  /usr/bin/sed -i '' -E 's/objectVersion = [0-9]+;/objectVersion = 56;/' "$PBX"
  /usr/bin/sed -i '' -E 's/compatibilityVersion = "[^"]*";/compatibilityVersion = "Xcode 14.0";/' "$PBX"
fi

# ---- 3. 无签名构建 ----
echo "· 编译（CODE_SIGNING_ALLOWED=NO）"
xcodebuild \
  -project "${APP_NAME}.xcodeproj" \
  -scheme "${APP_NAME}" \
  -configuration Release \
  -sdk iphoneos \
  -destination "generic/platform=iOS" \
  -derivedDataPath build \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY="" \
  -quiet \
  build

APP_PATH="build/Build/Products/Release-iphoneos/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
  echo "!! 没找到构建产物：$APP_PATH" >&2
  exit 1
fi

# ---- 4. 打成 Payload 结构 —— 这就是 .ipa 的全部要求 ----
echo "· 打包 IPA"
rm -rf build/Payload "$OUT"
mkdir -p build/Payload
cp -R "$APP_PATH" build/Payload/
# ditto 保留符号链接与权限（codesign 重签时依赖这些，zip 会丢）
(cd build && ditto -c -k --sequesterRsrc --keepParent Payload "${APP_NAME}-unsigned.ipa")
rm -rf build/Payload

echo
echo "完成：$(pwd)/${OUT}  ($(du -h "$OUT" | cut -f1))"
echo "下一步：把 IPA 传到手机，用轻松签 / Sideloadly / AltStore 等自签工具重签安装。"
