"""Fast rules — deterministic decisions taken BEFORE calling the LLM.

Why: an LLM call costs ~0.5-2 s and the server gives us 5 s max. For obvious
situations (I have the ball in front of goal, the ball is loose and I'm the
closest) a rule is instant and never wrong. The LLM is only used for the
ambiguous cases (pass or dribble? who to mark? where to run?).

build_fast_rules(position_label) returns rules(game_state, team_id, pid)
-> list[dict] | None. None means "no rule applies, ask the LLM".
"""

from __future__ import annotations

from state import (
    _player_idx, _is_my_team, dist, get_goal_positions, holder_is_me,
    closest_teammate_to_ball, coach_messages,
)
from fallback import _cmd

# Shooting distance to the opponent goal, per position (None = never auto-shoot)
SHOOT_RANGE = {"GK": None, "DEF": None, "MID": 20.0, "FWD1": 24.0, "FWD2": 24.0}

# Assumption: L/R in aim_location is from the shooter's point of view, facing
# the goal. If replays show shots going TOWARD the keeper, set this to True.
FLIP_AIM = False

SPRINT_MIN_STAMINA = 0.25  # stamina is a 0.0-1.0 fraction


def aim_away_from_gk(game_state: dict, team_id: int) -> str:
    """Pick a low corner on the side opposite to the opponent goalkeeper."""
    players = game_state.get("players", [])
    gk = next((p for p in players if _player_idx(p) == 0 and not _is_my_team(p, team_id)), None)
    gk_y = gk.get("position", {}).get("y", 0) if gk else 0
    # Facing +x (HOME), left is +y. Facing -x (AWAY), left is -y.
    gk_on_left = gk_y > 0 if team_id == 0 else gk_y < 0
    side = "R" if gk_on_left else "L"
    if FLIP_AIM:
        side = "L" if side == "R" else "R"
    return "B" + side


def _most_open_teammate(players, team_id, me_pid, my_pos, opp_goal_x, exclude=(0,)):
    """Teammate with the most space, slightly favouring those closer to goal."""
    mates = [p for p in players if _is_my_team(p, team_id)
             and _player_idx(p) != me_pid and _player_idx(p) not in exclude]
    opps = [p for p in players if not _is_my_team(p, team_id)]
    if not mates:
        return None

    def score(p):
        pos = p.get("position", {})
        open_d = min((dist(pos, o.get("position", {})) for o in opps), default=30.0)
        forward = -abs(pos.get("x", 0) - opp_goal_x) * 0.15
        too_far = -max(0.0, dist(pos, my_pos) - 35) * 0.5  # long passes get intercepted
        return open_d + forward + too_far

    return _player_idx(max(mates, key=score))


def build_fast_rules(position_label: str):
    shoot_range = SHOOT_RANGE.get(position_label)

    def rules(game_state: dict, team_id: int, pid: int):
        players = game_state.get("players", [])
        ball = game_state.get("ball", {})
        ball_pos = ball.get("position", {"x": 0, "y": 0})
        me = next((p for p in players if _player_idx(p) == pid and _is_my_team(p, team_id)), None)
        if not me:
            return None
        pos = me.get("position", {})
        stamina = me.get("stamina", 1.0)
        my_goal_x, opp_goal_x = get_goal_positions(team_id)
        my_team = [p for p in players if _is_my_team(p, team_id)]

        # 1. I have the ball
        if holder_is_me(ball, players, team_id, pid):
            if position_label == "GK":
                target = _most_open_teammate(players, team_id, pid, pos, opp_goal_x)
                if target is not None:
                    return [_cmd("GK_DISTRIBUTE", pid, team_id,
                                 {"target_player_id": target, "method": "THROW"})]
            if shoot_range and abs(pos.get("x", 0) - opp_goal_x) < shoot_range \
                    and abs(pos.get("y", 0)) < 18:
                return [_cmd("SHOOT", pid, team_id,
                             {"aim_location": aim_away_from_gk(game_state, team_id), "power": 0.9})]
            return None  # pass or dribble: let the LLM decide

        # 2. Goalkeeper: fully rule-based (no LLM latency, never leaves goal)
        if position_label == "GK":
            d_ball_goal = abs(ball_pos.get("x", 0) - my_goal_x)
            if d_ball_goal < 14 and abs(ball_pos.get("y", 0)) < 14 and ball.get("isFree") is True:
                return [_cmd("INTERCEPT", pid, team_id, {"aggressive": True}, duration=2)]
            step_out = 3.0 if d_ball_goal > 30 else 1.5
            tx = my_goal_x + (step_out if my_goal_x < 0 else -step_out)
            ty = max(-6.0, min(6.0, ball_pos.get("y", 0) * 0.4))
            return [_cmd("MOVE_TO", pid, team_id,
                         {"target_x": tx, "target_y": ty, "sprint": d_ball_goal < 20})]

        # 3. Loose ball and I'm the closest outfield player: go get it
        # (skipped while the coach has given orders, so the LLM can apply them)
        if not coach_messages(game_state, my_player_id=pid) and ball.get("isFree") is True and closest_teammate_to_ball(my_team, ball_pos) == pid:
            # DEF does not chase deep into the opponent half
            if position_label == "DEF" and abs(ball_pos.get("x", 0) - my_goal_x) > 60:
                return None
            sprint = stamina > SPRINT_MIN_STAMINA and dist(pos, ball_pos) < 25
            return [_cmd("MOVE_TO", pid, team_id,
                         {"target_x": ball_pos.get("x", 0), "target_y": ball_pos.get("y", 0),
                          "sprint": sprint})]

        return None

    return rules
