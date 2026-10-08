#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p sushi-fast/.runtime
# An explicit SDK is useful when CLT Swift and the newest installed SDK differ.
if [ -n "${KAKAO_SWIFT_SDK:-}" ]; then
  swiftc -sdk "$KAKAO_SWIFT_SDK" -module-cache-path /private/tmp/ondo-swift-module-cache -O ops/kakao_bridge.swift -o sushi-fast/.runtime/kakao-bridge.next
else
  swiftc -module-cache-path /private/tmp/ondo-swift-module-cache -O ops/kakao_bridge.swift -o sushi-fast/.runtime/kakao-bridge.next
fi
mv sushi-fast/.runtime/kakao-bridge.next sushi-fast/.runtime/kakao-bridge
