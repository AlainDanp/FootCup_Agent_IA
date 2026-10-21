"""
AI Soccer Forward 2 - right channel Agent — Controls ONLY player 4.
Strands SDK + Amazon Nova. Fast rules first, LLM only for ambiguous cases.
"""

import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib")); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib"))
from _bootstrap import setup_lib_path; setup_lib_path(__file__)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_base import create_agent, create_invoke_handler
from fallback import build_fallback, FWD2_CONFIG
from fast_rules import build_fast_rules
from prompt_common import build_prompt

app = BedrockAgentCoreApp()

# --- Position Config ---
MY_PLAYER_ID = 4
POSITION_LABEL = "FWD2"

# --- System Prompt ---
ROLE = """## Role: Striker, RIGHT channel (y on the positive side, around y=+8)
- With the ball far from goal: MOVE_TO (dribble) toward the opponent goal around y=+6, sprint if stam > 0.3. If an opponent blocks you (distToMe < 4) and FWD1 (id=3) has open= > 6, PASS to id=3.
- Teammate has the ball: MOVE_TO into space ahead of the ball, 15-22 units from the opponent goal, y about +8, to receive a THROUGH pass. Stay 8+ units from the goal line.
- Opponent has the ball in THEIR half and is within 10 units: PRESS_BALL 0.8 (high press). If it is in YOUR half, do not track back past x=0: hold the right channel near the halfway line for a counter-attack."""

SYSTEM_PROMPT = build_prompt(MY_PLAYER_ID, POSITION_LABEL, ROLE)

# --- Fallback + fast rules ---
fallback_commands = build_fallback(FWD2_CONFIG)
fast_rules = build_fast_rules(POSITION_LABEL)

# --- Wire it up ---
agent = create_agent(SYSTEM_PROMPT, model_id="us.amazon.nova-lite-v1:0")
create_invoke_handler(
    app, agent, MY_PLAYER_ID, POSITION_LABEL, fallback_commands,
    fallback_cfg=FWD2_CONFIG, fast_rules=fast_rules,
)

if __name__ == "__main__":
    app.run()
