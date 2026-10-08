#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p sushi-fast/.runtime
xcrun clang -fobjc-arc -framework Foundation -framework Vision ops/grading_ocr.m -o sushi-fast/.runtime/grading-ocr.next
mv sushi-fast/.runtime/grading-ocr.next sushi-fast/.runtime/grading-ocr
