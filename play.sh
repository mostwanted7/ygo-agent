#!/usr/bin/env bash
# Play against the agent: host a LAN duel in EDOPro, run this, press Enter when the room is open.
# Same as `ygo-agent play --join`. Extra options: --model sonnet (faster), --effort low|medium|high, --port N,
# --deck blackwing, --teach, --brain-only (see --help).
cd "$(dirname "$0")" && exec python3 -m ygo_agent play --join "$@"
