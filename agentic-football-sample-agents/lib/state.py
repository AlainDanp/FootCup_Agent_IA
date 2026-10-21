"""Game state summarization utilities for AI soccer agents."""

import math


# ---------------------------------------------------------------------------
# Format-agnostic helpers — handle both new (agentId/teamCode/possessionAgentId)
# and old (playerId/teamId/possessionPlayerId) game server formats.
# ---------------------------------------------------------------------------

def _player_idx(p: dict) -> int:
    """Numeric index (0-4) from a player dict — new agentId or old playerId."""
    if "agentId" in p:
        try:
            return int(p["agentId"].rsplit("_", 1)[-1])
        except (ValueError, IndexError):
            return 0
    return p.get("playerId", 0)


def _is_my_team(p: dict, team_id: int) -> bool:
    """True if player belongs to team_id — new teamCode or old teamId.

    teamCode is compared case-insensitively: the game server documents the
    teams as HOME/AWAY while the payload has been observed as home/away, and
    a case mismatch here is catastrophic rather than cosmetic — every player
    reads as an opponent, the agent's own player drops out of the prompt
    entirely, and the fallback degrades to SET_STANCE for the whole match.
    """
    code = p.get("teamCode")
    if isinstance(code, str):
        return code.strip().lower() == ("home" if team_id == 0 else "away")
    return p.get("teamId") == team_id


def _ball_is_free(ball: dict):
    """True/False from the server's own isFree flag, or None when absent.

    The server supplies isFree alongside possessionAgentId. Inferring
    looseness from a failed possession lookup instead makes any id we cannot
    parse look like a loose ball, which tells a player carrying the ball to
    go and fetch it.
    """
    free = ball.get("isFree")
    return free if isinstance(free, bool) else None


def _resolve_holder(ball: dict, players: list):
    """Return the player dict holding the ball, or None.

    agentId is not unique across teams — the same agentId_N appears once per
    team — so an id match alone cannot always identify the player. When the
    id is ambiguous we keep the long-standing behaviour of taking the first
    match in players[], rather than guessing: a positional tie-break on
    distance to the ball looks appealing but picks the wrong team whenever
    possession has just changed and the ball has not yet caught up.

    Ambiguity is therefore no worse than before. What changes is that the
    team is now checked against the resolved holder (see holder_is_me), so a
    player can no longer act on a ball the opposing player of the same index
    is carrying.

    TODO: drop the ambiguity entirely once the server exposes a globally
    unique player id, or sends a team discriminator alongside possession.
    """
    holder_agent = ball.get("possessionAgentId")
    if isinstance(holder_agent, str):
        matches = [p for p in players if p.get("agentId") == holder_agent]
    else:
        pid = ball.get("possessionPlayerId")
        if pid is None:
            return None
        matches = [p for p in players if p.get("playerId") == pid]
        team = ball.get("possessionTeamId")
        if team is not None:
            matches = [p for p in matches if p.get("teamId") == team]

    return matches[0] if matches else None


def _possession_idx(ball: dict):
    """Numeric possession player index from ball dict — new possessionAgentId or old possessionPlayerId.
    Returns int or None."""
    agent_id = ball.get("possessionAgentId")
    if agent_id is not None:
        try:
            return int(agent_id.rsplit("_", 1)[-1])
        except (ValueError, IndexError):
            return None
    return ball.get("possessionPlayerId")


def get_goal_positions(team_id: int) -> tuple[float, float]:
    """Return (my_goal_x, opp_goal_x) based on team."""
    if team_id == 0:
        return -55.0, 55.0
    return 55.0, -55.0


def get_possession_info(ball: dict, players: list, team_id: int) -> tuple:
    """Return (possession_id, ball_status_str, we_have_ball).

    possession_id is the holder's per-team index, which is NOT on its own
    enough to identify a player — use holder_is_me() for that rather than
    comparing it to your own id.
    """
    if _ball_is_free(ball) is True:
        return None, "free", False

    claimed = (
        isinstance(ball.get("possessionAgentId"), str)
        or ball.get("possessionPlayerId") is not None
    )
    holder = _resolve_holder(ball, players)
    if holder is None:
        # A ball with no possession claim is genuinely loose. A claim we
        # cannot resolve is reported as unknown and never as loose, so a
        # carrier is not told to go and fetch a ball it already has.
        return None, ("unknown" if claimed else "free"), False

    is_mine = _is_my_team(holder, team_id)
    idx = _player_idx(holder)
    side = "MY" if is_mine else "OPP"
    return idx, f"{side} player {idx}", is_mine


def holder_is_me(ball: dict, players: list, team_id: int, my_player_id: int) -> bool:
    """True only when this specific player holds the ball.

    Both the index and the team must match. Comparing the possession index
    alone is true for two players at once — one per team — which lets a
    player act on a ball an opponent is carrying.
    """
    holder = _resolve_holder(ball, players)
    if holder is None:
        return False
    return _player_idx(holder) == my_player_id and _is_my_team(holder, team_id)


def dist(pos1: dict, pos2: dict) -> float:
    """Euclidean distance between two position dicts with x,y keys."""
    return math.sqrt(
        (pos1.get("x", 0) - pos2.get("x", 0)) ** 2
        + (pos1.get("y", 0) - pos2.get("y", 0)) ** 2
    )


def summarize_state(
    game_state: dict,
    team_id: int,
    my_player_id: int,
    position_label: str,
) -> str:
    """Build a concise text summary of the game state for a single-player agent."""
    ball = game_state.get("ball", {})
    ball_pos = ball.get("position", {"x": 0, "y": 0})
    score = game_state.get("score", {})
    game_time = game_state.get("gameTime", 0)
    play_mode = game_state.get("playMode", 0)
    players = game_state.get("players", [])

    my_team = sorted(
        [p for p in players if _is_my_team(p, team_id)],
        key=lambda p: _player_idx(p),
    )
    opponents = sorted(
        [p for p in players if not _is_my_team(p, team_id)],
        key=lambda p: _player_idx(p),
    )

    me = next((p for p in my_team if _player_idx(p) == my_player_id), None)
    possession_id, ball_status, _ = get_possession_info(ball, players, team_id)

    my_goal_x, opp_goal_x = get_goal_positions(team_id)

    lines = [
        f"Time: {game_time:.0f}s | Score: {score.get('home',0)}-{score.get('away',0)} | "
        f"Team: {team_id} ({'HOME' if team_id == 0 else 'AWAY'}) | PlayMode: {play_mode}",
        f"Ball: ({ball_pos.get('x',0):.1f}, {ball_pos.get('y',0):.1f}) held by {ball_status}",
        f"Your goal at x={my_goal_x:.0f} | Opponent goal at x={opp_goal_x:.0f}",
        "",
    ]

    # My player info
    if me:
        pos = me.get("position", {})
        # Stamina is a 0.0-1.0 fraction (current/max), not a 0-100 integer.
        # The old default of 100 hid that: had the key ever been missing it
        # would have rendered as "100" and the mistake would have been
        # obvious immediately.
        stam = me.get("stamina", 1.0)
        dist_ball = dist(pos, ball_pos)
        has_ball = holder_is_me(ball, players, team_id, my_player_id)
        extra = f" distOppGoal={abs(pos.get('x', 0) - opp_goal_x):.1f}" if position_label in ("MID", "FWD1", "FWD2") else ""
        lines.append(
            f">>> YOUR PLAYER ({position_label}, id={my_player_id}): "
            f"pos=({pos.get('x',0):.1f},{pos.get('y',0):.1f}) "
            # :.0f rounded the 0.0-1.0 fraction to a single digit, so the
            # model only ever saw 0 or 1 — fully rested or exhausted, with
            # nothing in between.
            f"stam={stam:.2f} distBall={dist_ball:.1f}{extra} hasBall={has_ball}"
        )
    lines.append("")

    # Teammates
    lines.append("Teammates:")
    for p in my_team:
        if _player_idx(p) == my_player_id:
            continue
        pos = p.get("position", {})
        pid = _player_idx(p)
        role = "GK" if pid == 0 else f"P{pid}"
        extra = ""
        if position_label == "MID":
            extra = f" distOppGoal={abs(pos.get('x', 0) - opp_goal_x):.1f}"
        # open = distance to the nearest opponent: high value = safe pass target
        open_d = min((dist(pos, o.get("position", {})) for o in opponents), default=99.0)
        lines.append(f"  {role}(id={pid}): ({pos.get('x',0):.1f},{pos.get('y',0):.1f}){extra} open={open_d:.1f}")

    lines.append("")

    # Opponents
    opp_header = "Opponents (defenders to watch):" if position_label in ("FWD1", "FWD2") else "Opponents:"
    lines.append(opp_header)
    for p in opponents:
        pos = p.get("position", {})
        pid = _player_idx(p)
        d_goal = abs(pos.get("x", 0) - my_goal_x)
        d_me = dist(pos, me.get("position", {})) if me else 0
        tag = " [GK]" if pid == 0 else ""
        lines.append(f"  P{pid}{tag}: ({pos.get('x',0):.1f},{pos.get('y',0):.1f}) distToMyGoal={d_goal:.1f} distToMe={d_me:.1f}")

    lines.extend(_context_lines(game_state, team_id, my_player_id, my_team, opponents, ball_pos))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extra context: match situation, closest player to the ball, coach orders
# ---------------------------------------------------------------------------

MATCH_DURATION_S = 300.0  # 5-minute matches


def match_situation(game_state: dict, team_id: int) -> tuple[int, float]:
    """Return (goal_diff from MY point of view, seconds left)."""
    score = game_state.get("score", {}) or {}
    mine = score.get("home", 0) if team_id == 0 else score.get("away", 0)
    theirs = score.get("away", 0) if team_id == 0 else score.get("home", 0)
    left = max(0.0, MATCH_DURATION_S - float(game_state.get("gameTime", 0) or 0))
    return mine - theirs, left


def closest_teammate_to_ball(my_team: list, ball_pos: dict, include_gk: bool = False):
    """Index of my teammate (incl. me) closest to the ball; GK excluded by default."""
    cands = [p for p in my_team if include_gk or _player_idx(p) != 0]
    if not cands:
        return None
    return _player_idx(min(cands, key=lambda p: dist(p.get("position", {}), ball_pos)))


def _msg_text(m) -> str:
    if isinstance(m, str):
        return m.strip()
    if isinstance(m, dict):
        return str(m.get("message") or m.get("text") or m.get("content") or "").strip()
    return ""


def coach_messages(game_state: dict, limit: int = 3, my_player_id=None) -> list[str]:
    """Latest coach instructions from OUR coach only.

    teamChat also carries the OPPONENT coach's messages, so a message is kept
    only if it contains our secret CODEWORD (see team_config.py). When
    my_player_id is given, messages that name another of our players (and not
    this one) are dropped: they are not for this agent.
    """
    try:
        from team_config import CODEWORD, PLAYER_NAMES
    except ImportError:
        CODEWORD, PLAYER_NAMES = "", {}
    code = CODEWORD.lower()
    out = []
    for m in (game_state.get("teamChat") or []):
        txt = _msg_text(m)
        low = txt.lower()
        if not txt or (code and code not in low):
            continue
        if my_player_id is not None and PLAYER_NAMES:
            mine = PLAYER_NAMES.get(my_player_id, "").lower()
            named = [n.lower() for n in PLAYER_NAMES.values() if n and n.lower() in low]
            if named and mine not in named:
                continue
        if code:
            txt = txt[low.index(code) + len(code):].strip(" :-,") or txt
        out.append(txt[:200])
    return out[-limit:]


def player_name(my_player_id: int) -> str:
    try:
        from team_config import PLAYER_NAMES
        return PLAYER_NAMES.get(my_player_id, "")
    except ImportError:
        return ""


def _context_lines(game_state, team_id, my_player_id, my_team, opponents, ball_pos) -> list[str]:
    diff, left = match_situation(game_state, team_id)
    if diff > 0:
        sit = f"LEADING by {diff}"
    elif diff < 0:
        sit = f"TRAILING by {-diff}"
    else:
        sit = "DRAW"
    if left < 90 and diff > 0:
        plan = "protect the lead: stay compact, safe passes, no risky tackles"
    elif left < 90 and diff < 0:
        plan = "all-out attack: push up, shoot early, press high"
    else:
        plan = "normal balanced play"

    lines = ["", f"Match: {sit} | {left:.0f}s left | Plan: {plan}"]

    closest = closest_teammate_to_ball(my_team, ball_pos)
    if closest is not None:
        who = "YOU" if closest == my_player_id else f"P{closest}"
        lines.append(f"Closest outfield teammate to ball: {who}")

    opp_gk = next((p for p in opponents if _player_idx(p) == 0), None)
    if opp_gk:
        lines.append(f"Opponent GK y={opp_gk.get('position', {}).get('y', 0):.1f} (shoot to the far side)")

    coach = coach_messages(game_state, my_player_id=my_player_id)
    if coach:
        lines.append("")
        name = player_name(my_player_id)
        lines.append(f"COACH INSTRUCTIONS for you{' (' + name + ')' if name else ''} - highest priority, obey them (latest first wins):")
        lines.extend(f"  - {c}" for c in coach)
    return lines
