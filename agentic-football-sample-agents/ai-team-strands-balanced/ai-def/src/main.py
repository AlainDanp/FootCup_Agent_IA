"""
AI Soccer Defender Agent — Controls ONLY player 1.
Strands SDK + Amazon Nova. Fast rules first, LLM only for ambiguous cases.
"""

import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib")); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib"))
from _bootstrap import setup_lib_path; setup_lib_path(__file__)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_base import create_agent, create_invoke_handler
from fallback import build_fallback, DEF_CONFIG
from fast_rules import build_fast_rules
from prompt_common import build_prompt

app = BedrockAgentCoreApp()

# --- Position Config ---
MY_PLAYER_ID = 1
POSITION_LABEL = "DEF"

# --- System Prompt ---
ROLE = """## Role: Last defender
- Stay between the ball and your goal; never go past the halfway line (x=0).
- Opponent has the ball in your half: MARK TIGHT the opponent closest to your goal; if the carrier is within 8 units of you, PRESS_BALL 0.8.
- SLIDE_TACKLE only if the carrier is within 3 units AND within 20 units of your goal.
- Loose ball in your half and you are the closest: INTERCEPT aggressive=true.
- With the ball: PASS (GROUND) quickly to MID or a forward with high open=. Never dribble forward, never pass to the GK unless all others are marked.
- Team has the ball: MOVE_TO about 15 units in front of your goal, y near the ball's y * 0.5."""

SYSTEM_PROMPT = build_prompt(MY_PLAYER_ID, POSITION_LABEL, ROLE)

# --- Fallback + fast rules ---
fallback_commands = build_fallback(DEF_CONFIG)
fast_rules = build_fast_rules(POSITION_LABEL)

# --- Wire it up ---
agent = create_agent(SYSTEM_PROMPT, model_id="us.amazon.nova-lite-v1:0")
create_invoke_handler(
    app, agent, MY_PLAYER_ID, POSITION_LABEL, fallback_commands,
    fallback_cfg=DEF_CONFIG, fast_rules=fast_rules,
)

if __name__ == "__main__":
    app.run()
