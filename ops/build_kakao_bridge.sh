#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p sushi-fast/.runtime
swiftc -module-cache-path /private/tmp/ondo-swift-module-cache -O ops/kakao_bridge.swift -o sushi-fast/.runtime/kakao-bridge.next
mv sushi-fast/.runtime/kakao-bridge.next sushi-fast/.runtime/kakao-bridge
