#!/usr/bin/env python3
"""
Weekly Survivor 51 rankings updater.
Reads survivor/ratings.json, queries Claude with web search, updates IN-player ratings.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

RATINGS_PATH = Path(__file__).parent.parent / "survivor" / "ratings.json"
MODEL = "claude-sonnet-4-6"


def load_ratings() -> dict:
    with open(RATINGS_PATH) as f:
        return json.load(f)


def save_ratings(data: dict) -> None:
    with open(RATINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nWrote updated ratings.json to {RATINGS_PATH}")


def next_episode_num(players: dict) -> int:
    """The episode to process this run: one past the last recorded elimination."""
    weeks = [
        info["eliminatedWeek"]
        for info in players.values()
        if info.get("eliminatedWeek") is not None
    ]
    return (max(weeks) + 1) if weeks else 1


def build_previous_rankings(players: dict) -> list[dict]:
    return sorted(
        [
            {"name": name, "rank": info["rating"], "status": info["status"]}
            for name, info in players.items()
        ],
        key=lambda x: x["rank"],
    )


def extract_json_from_response(text: str) -> str:
    """Strip markdown code fences or leading prose before the JSON object."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    # Find the first JSON object/array and discard any leading prose
    match = re.search(r"[{\[]", text)
    if match:
        return text[match.start():]
    return text


def main() -> None:
    data = load_ratings()
    players = data["players"]

    active = {name: info for name, info in players.items() if info["status"] == "IN"}
    if not active:
        print("No active (IN) players found — nothing to update.")
        sys.exit(0)

    episode_num = next_episode_num(players)
    active_names = sorted(active.keys())
    previous_rankings = build_previous_rankings(players)

    print(f"Episode to process: {episode_num}")
    print(f"Active players going in ({len(active_names)}): {', '.join(active_names)}")

    total_players = len(players)
    # Players already out hold places total_players down to (num_remaining + 1).
    # Anyone leaving this episode takes the next places down from num_remaining.
    num_remaining = len(active_names)

    prompt = (
        f'It is the week after Episode {episode_num} of Survivor 51 aired. '
        f'Search for recaps and analysis published in the past week. '
        f'Do this in two steps, in this order. '
        f'STEP 1 — FINAL PLACEMENTS FOR ELIMINATED PLAYERS: Determine which currently-active players '
        f'(if any) were voted out, medically evacuated, or quit during Episode {episode_num}. '
        f'Once a player leaves the game, their final placement in the overall game is locked in and '
        f'never changes. There are {total_players} castaways in total and {num_remaining} were still '
        f'in the game going into this episode, so the first player to leave during this episode '
        f'finishes in place {num_remaining}, the next in place {num_remaining - 1}, and so on. '
        f'List eliminations in the order they left the game and give each its "place". '
        f'STEP 2 — RANK THE REMAINING PLAYERS: Only after placements are assigned, rank every player '
        f'who is STILL ACTIVE after that episode from 1 (best positioned to win) down to the number '
        f'of players remaining, using each number exactly once with no ties, considering advantages, '
        f'jury relationships, alliance standing, and recent challenge and strategic performance. '
        f'An eliminated player must never appear in the rankings or hold a top rank. '
        f'Return ONLY valid JSON with no explanation and no markdown, in exactly this format: '
        f'{{"eliminations": [{{"name": "PlayerName", "status": "OUT", "place": {num_remaining}}}, ...], '
        f'"rankings": [{{"name": "PlayerName", "rank": 1}}, ...], '
        f'"commentary": "2-3 paragraph plain-text analysis of the episode and current game state. '
        f'Cover the key strategic moves and why the top-ranked players are well-positioned. '
        f'No markdown, no bullet points — flowing prose only."}}. '
        f'Each "eliminations" entry\'s "status" must be exactly "OUT", "MED", or "QUIT". '
        f'Do NOT include newly-eliminated players in "rankings" — only still-active players belong '
        f'there. If Episode {episode_num} has not aired yet or no reliable recap exists yet, return '
        f'an empty "eliminations" array and repeat the previous rankings unchanged. '
        f'The "rankings" and "eliminations" arrays must contain ONLY the specified objects — close '
        f'each with "]" before adding sibling keys, never as an array element. '
        f'Active players going into this episode: {active_names}. '
        f'Previous rankings and status for context — players already OUT/MED/QUIT keep their '
        f'existing final placement and must not be re-ranked: {previous_rankings}. '
        f'Do not include any text before or after the JSON object — your entire response must be valid JSON starting with {{.'
    )

    client = anthropic.Anthropic()

    print(f"\nQuerying {MODEL} with web search...")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                    # Cache the stable prefix for any same-episode re-runs.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    max_attempts = 3
    parsed = None
    for attempt in range(1, max_attempts + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=messages,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )

        # The response may contain server_tool_use + tool_result blocks before the
        # final text answer. Take the LAST text block.
        text_content = next(
            (block.text for block in reversed(response.content) if block.type == "text"),
            None,
        )

        if not text_content:
            print("ERROR: No text block in Claude response.", file=sys.stderr)
            print("Response content types:", [b.type for b in response.content], file=sys.stderr)
            sys.exit(1)

        cleaned = extract_json_from_response(text_content)

        try:
            parsed = json.loads(cleaned)
            break
        except json.JSONDecodeError as exc:
            print(f"WARNING (attempt {attempt}/{max_attempts}): Failed to parse JSON: {exc}", file=sys.stderr)
            print(f"Raw text was:\n{text_content}", file=sys.stderr)
            if attempt == max_attempts:
                print("ERROR: Giving up after repeated invalid JSON responses.", file=sys.stderr)
                sys.exit(1)
            # Ask Claude to fix its own malformed JSON, reusing the same
            # conversation (and web search results already gathered).
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"That response was not valid JSON: {exc}. "
                            f"Return ONLY the corrected, complete, valid JSON object in the exact "
                            f"same format as before — no explanation, no markdown."
                        ),
                    }
                ],
            })

    # Accept either the new {eliminations, rankings, commentary} shape or the legacy bare array.
    if isinstance(parsed, list):
        eliminations = []
        new_rankings = parsed
        commentary = ""
    elif isinstance(parsed, dict) and "rankings" in parsed:
        eliminations = parsed.get("eliminations", [])
        new_rankings = parsed["rankings"]
        commentary = str(parsed.get("commentary", "")).strip()
    else:
        print("ERROR: Unexpected JSON shape from Claude.", file=sys.stderr)
        sys.exit(1)

    VALID_STATUSES = {"OUT", "MED", "QUIT"}

    # Apply eliminations first, so the rating pass below only touches players
    # still IN after this episode.
    eliminated_names: list[str] = []
    for item in eliminations:
        name = item.get("name")
        status = str(item.get("status", "OUT")).upper()
        if status not in VALID_STATUSES:
            print(f"WARNING: Unrecognized elimination status '{status}' for '{name}', defaulting to OUT.", file=sys.stderr)
            status = "OUT"
        if name not in players:
            print(f"WARNING: Eliminated player '{name}' not found in ratings.json — skipping.", file=sys.stderr)
            continue
        # Final placement is fixed by elimination order, regardless of what the
        # model reports, so an eliminated player can never keep a top rank.
        place = num_remaining - len(eliminated_names)
        if item.get("place") not in (None, place):
            print(f"WARNING: Model gave '{name}' place {item.get('place')}, using {place} from elimination order.", file=sys.stderr)
        players[name]["status"] = status
        players[name]["eliminatedWeek"] = episode_num
        players[name]["rating"] = place
        eliminated_names.append(name)

    rank_map: dict[str, int] = {item["name"]: item["rank"] for item in new_rankings}

    # Warn about any still-active player missing from the response
    still_active_names = [n for n in active_names if n not in eliminated_names]
    for name in still_active_names:
        if name not in rank_map:
            print(f"WARNING: Active player '{name}' missing from rankings response.", file=sys.stderr)
    active_ranks = [rank_map[n] for n in still_active_names if n in rank_map]
    if sorted(active_ranks) != list(range(1, len(still_active_names) + 1)):
        print(f"WARNING: Active rankings are not a clean 1..{len(still_active_names)} sequence: {sorted(active_ranks)}", file=sys.stderr)

    # Apply new ratings only to players still IN
    changes: list[str] = []
    for name, info in players.items():
        if info["status"] == "IN" and name in rank_map:
            old = info["rating"]
            new = rank_map[name]
            if old != new:
                changes.append(f"  {name}: {old} → {new}")
            info["rating"] = new

    data["updated"] = date.today().isoformat()
    data["source"] = "Claude API - web search synthesis"
    data["episode"] = episode_num
    if commentary:
        data["commentary"] = commentary

    save_ratings(data)

    print(f"\nEpisode {episode_num} update complete — {len(eliminated_names)} elimination(s), {len(changes)} ranking change(s):")
    if eliminated_names:
        for name in eliminated_names:
            print(f"  OUT: {name} ({players[name]['status']}, week {episode_num}, final place {players[name]['rating']})")
    if changes:
        for line in changes:
            print(line)
    if not eliminated_names and not changes:
        print("  No changes.")

    # Expose episode number for GitHub Actions commit message
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"episode_num={episode_num}\n")


if __name__ == "__main__":
    main()
