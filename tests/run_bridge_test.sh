#!/usr/bin/env bash
# Builds and runs the C# bridge test against a fresh brain (uses real model calls; takes ~1 minute).
# Extra arguments go to the brain, e.g. --model sonnet. Logs go to a temporary folder, not games/.
set -u
cd "$(dirname "$0")/.."
PORT=${BRIDGE_TEST_PORT:-7939}
OUT=tests/build
mkdir -p "$OUT"
mcs -nologo -out:"$OUT/BridgeTest.exe" -r:windbot-src/bin/Release/ExecutorBase.dll \
    -r:windbot-src/bin/Release/Mono.Data.Sqlite.dll tests/BridgeTest.cs || exit 1
GAMES=$(mktemp -d "${TMPDIR:-/tmp}/ygo-bridge-test.XXXXXX")
LOG="$GAMES/brain.log"
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
$PY -m ygo_agent play --join --brain-only --brain-port "$PORT" --games-dir "$GAMES" "$@" > "$LOG" 2>&1 &
BRAIN=$!
trap 'kill $BRAIN 2>/dev/null' EXIT
sleep 4
if ! kill -0 $BRAIN 2>/dev/null; then cat "$LOG"; echo "FAIL brain did not start"; exit 1; fi
MONO_PATH=windbot-src/bin/Release timeout 600 mono "$OUT/BridgeTest.exe" "$HOME/Games/ProjectIgnis/expansions/cards.cdb" "$PORT"
STATUS=$?
# The brain side: one log folder per game of the match (plus one for the early go_first-only connection),
# with the replies recorded in game.jsonl.
JSONL=$(find "$GAMES" -mindepth 2 -maxdepth 2 -name game.jsonl)  # find skips the latest symlink
GAMES_LOGGED=$(grep -l '"e": "start"' $JSONL | wc -l)
REPLIES=$(cat $JSONL | grep -c '"kind": "reply"')
if [ "$GAMES_LOGGED" -eq 2 ]; then echo "PASS two games logged separately"; else echo "FAIL expected 2 game logs, got $GAMES_LOGGED"; STATUS=1; fi
if [ "$REPLIES" -gt 0 ]; then echo "PASS replies logged ($REPLIES)"; else echo "FAIL no replies in game.jsonl"; STATUS=1; fi
echo "brain output and game logs: $GAMES"
exit $STATUS
