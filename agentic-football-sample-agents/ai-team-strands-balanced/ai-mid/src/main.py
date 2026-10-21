"""
AI Soccer Midfielder Agent — Controls ONLY player 2.
Strands SDK + Amazon Nova. Fast rules first, LLM only for ambiguous cases.
"""

import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib")); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib"))
from _bootstrap import setup_lib_path; setup_lib_path(__file__)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_base import create_agent, create_invoke_handler
from fallback import build_fallback, MID_CONFIG
from fast_rules import build_fast_rules
from prompt_common import build_prompt

app = BedrockAgentCoreApp()

# --- Position Config ---
MY_PLAYER_ID = 2
POSITION_LABEL = "MID"

# --- System Prompt ---
ROLE = """## Role: Central midfielder (link player)
- With the ball: if a forward has open= > 8 and is closer to goal than you, PASS to him (THROUGH if he is running toward goal, else GROUND). If nobody is open, MOVE_TO (dribble) toward the opponent goal in the centre. Under pressure (nearest opponent < 4), pass back to DEF.
- Teammate has the ball: MOVE_TO a free space 10-15 units behind the forwards, offering a pass.
- Opponent has the ball in the middle third and is within 12 units: PRESS_BALL 0.7. Otherwise INTERCEPT aggressive=false.
- Opponent attacks in your half: drop back between ball and goal to help DEF."""

SYSTEM_PROMPT = build_prompt(MY_PLAYER_ID, POSITION_LABEL, ROLE)

# --- Fallback + fast rules ---
fallback_commands = build_fallback(MID_CONFIG)
fast_rules = build_fast_rules(POSITION_LABEL)

# --- Wire it up ---
agent = create_agent(SYSTEM_PROMPT, model_id="us.amazon.nova-lite-v1:0")
create_invoke_handler(
    app, agent, MY_PLAYER_ID, POSITION_LABEL, fallback_commands,
    fallback_cfg=MID_CONFIG, fast_rules=fast_rules,
)

if __name__ == "__main__":
    app.run()
