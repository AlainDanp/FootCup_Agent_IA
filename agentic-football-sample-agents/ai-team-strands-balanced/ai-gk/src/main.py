"""
AI Soccer Goalkeeper Agent — Controls ONLY player 0.
Strands SDK + Amazon Nova. Fast rules first, LLM only for ambiguous cases.
"""

import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib")); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib"))
from _bootstrap import setup_lib_path; setup_lib_path(__file__)

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from agent_base import create_agent, create_invoke_handler
from fallback import build_fallback, GK_CONFIG
from fast_rules import build_fast_rules
from prompt_common import build_prompt

app = BedrockAgentCoreApp()

# --- Position Config ---
MY_PLAYER_ID = 0
POSITION_LABEL = "GK"

# --- System Prompt ---
ROLE = """## Role: Goalkeeper
(Most GK decisions are handled by fast rules; you are only asked in unusual cases.)
- Stay on your goal line, between the ball and the centre of your goal.
- With the ball: GK_DISTRIBUTE (THROW) to the teammate with the highest open=.
- Never leave your box to chase the ball."""

SYSTEM_PROMPT = build_prompt(MY_PLAYER_ID, POSITION_LABEL, ROLE)

# --- Fallback + fast rules ---
fallback_commands = build_fallback(GK_CONFIG)
fast_rules = build_fast_rules(POSITION_LABEL)

# --- Wire it up ---
agent = create_agent(SYSTEM_PROMPT, model_id="us.amazon.nova-micro-v1:0")
create_invoke_handler(
    app, agent, MY_PLAYER_ID, POSITION_LABEL, fallback_commands,
    fallback_cfg=GK_CONFIG, fast_rules=fast_rules,
)

if __name__ == "__main__":
    app.run()
