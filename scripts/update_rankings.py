#!/usr/bin/env python3
"""
Weekly Survivor 50 rankings updater.
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


def extract_episode_num(players: dict) -> int:
    weeks = [
        info["eliminatedWeek"]
        for info in players.values()
        if info.get("eliminatedWeek") is not None
    ]
    return max(weeks) if weeks else 1


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

    episode_num = extract_episode_num(players)
    num_active = len(active)
    active_names = sorted(active.keys())
    previous_rankings = build_previous_rankings(players)

    print(f"Episode: {episode_num}")
    print(f"Active players ({num_active}): {', '.join(active_names)}")

    prompt = (
        f'It is after Episode {episode_num} of Survivor 50. '
        f'Search for recaps and analysis published in the past week. '
        f'Based on that research, rank all remaining active players from 1 (best positioned to win) '
        f'to {num_active} (worst positioned), considering advantages, jury relationships, '
        f'alliance standing, and recent challenge and strategic performance. '
        f'Return ONLY valid JSON with no explanation and no markdown, in exactly this format: '
        f'{{"rankings": [{{"name": "PlayerName", "rank": 1}}, ...], '
        f'"commentary": "2-3 paragraph plain-text analysis of the episode and current game state. '
        f'Cover the key strategic moves and why the top-ranked players are well-positioned. '
        f'No markdown, no bullet points — flowing prose only."}}. '
        f'Active players to rank: {active_names}. '
        f'Previous rankings for context — do not re-rank OUT or MED players: {previous_rankings}. '
        f'Do not include any text before or after the JSON object — your entire response must be valid JSON starting with {{.'
    )

    client = anthropic.Anthropic()

    print(f"\nQuerying {MODEL} with web search...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        # Cache the stable prefix for any same-episode re-runs.
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
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
    except json.JSONDecodeError as exc:
        print(f"ERROR: Failed to parse JSON from response: {exc}", file=sys.stderr)
        print(f"Raw text was:\n{text_content}", file=sys.stderr)
        sys.exit(1)

    # Accept either the new {rankings, commentary} shape or the legacy bare array.
    if isinstance(parsed, list):
        new_rankings = parsed
        commentary = ""
    elif isinstance(parsed, dict) and "rankings" in parsed:
        new_rankings = parsed["rankings"]
        commentary = str(parsed.get("commentary", "")).strip()
    else:
        print("ERROR: Unexpected JSON shape from Claude.", file=sys.stderr)
        sys.exit(1)

    rank_map: dict[str, int] = {item["name"]: item["rank"] for item in new_rankings}

    # Warn about any active player missing from the response
    for name in active_names:
        if name not in rank_map:
            print(f"WARNING: Active player '{name}' missing from rankings response.", file=sys.stderr)

    # Apply new ratings only to IN players
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

    print(f"\nEpisode {episode_num} update complete — {len(changes)} ranking change(s):")
    if changes:
        for line in changes:
            print(line)
    else:
        print("  No changes.")

    # Expose episode number for GitHub Actions commit message
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"episode_num={episode_num}\n")


if __name__ == "__main__":
    main()
