#!/usr/bin/env bash
# Rebuilds the WindBot fork in windbot-src (needed only after changing its C# code).
cd "$(dirname "$0")/windbot-src" || exit 1
if ! out=$(xbuild /p:Configuration=Release /v:minimal WindBot.csproj 2>&1); then
    echo "$out" | grep -E "error" || echo "$out" | tail -20
    exit 1
fi
echo "$out" | grep -E " error " && exit 1
echo "Built windbot-src/bin/Release/WindBot.exe"
