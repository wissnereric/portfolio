# Survivor Contest Tracker — Claude Reference

## What This Is

A single-page web app (`index.html`) that tracks a friend-group Survivor 50 fantasy contest. Four participants (Gina, Erin, Eric, Mike) each picked six returning players at the start of the season. The page displays each person's picks, shows which players have been eliminated, and calculates a win probability for each contestant.

Rankings are updated each weekend by Eric using ChatGPT research — synthesizing online episode recaps and analysis of each player's performance and position to win the game.

---

## File Overview

| File | Purpose |
|------|---------|
| `index.html` | Entire app — HTML, CSS, and JS in one file |
| `ratings.json` | Weekly-updated player rankings and elimination status |
| `img/survivor50/` | Player headshot `.webp` images, one per player |

---

## How `ratings.json` Works

Fetched at runtime by the app (`fetch('./ratings.json', { cache: "no-store" })`). Structure:

```json
{
  "updated": "YYYY-MM-DD",
  "source": "description of ranking source",
  "players": {
    "Player Name": {
      "rating": 3,           // ordinal rank — lower = better (1 = top contender)
      "status": "IN",        // "IN", "OUT", "MED", or "QUIT"
      "eliminatedWeek": null // null if still in, integer week number if out
    }
  }
}
```

**Status values:**
- `"IN"` — still playing
- `"OUT"` — voted out
- `"MED"` — medically evacuated
- `"QUIT"` — quit the game

A player is considered eliminated ("snuffed") if `status` is OUT/MED/QUIT **or** `eliminatedWeek` is non-null. Both conditions are checked independently so either field alone is sufficient to mark a player out.

**Updating weekly:** Edit `ratings.json` — update `rating` values for active players to reflect new rankings, set `status` and `eliminatedWeek` for newly eliminated players. Player names must match exactly (case-sensitive) between `ratings.json` and the `teams` array in `index.html`.

---

## How Win Probability Is Calculated

Only active (non-snuffed) players contribute to scores.

**Formula per player:** `1 / sqrt(rank)`

| Rank | Score |
|------|-------|
| 1    | 1.000 |
| 2    | 0.707 |
| 5    | 0.447 |
| 10   | 0.316 |

**Team score:** sum of `1/sqrt(rank)` across all active picks on that team.

**Win probability for a team:** `(team score / sum of all teams' scores) * 100`

This replaced the original `1/rank` method, which was too heavily biased toward the #1 ranked player. The `1/sqrt(rank)` method still rewards top rankings but compresses the advantage — rank 2 is 71% of rank 1 instead of 50%.

---

## Team Picks (hard-coded in `index.html`)

Defined in `DATA.teams` array (~line 285). Each entry has:
- `owner` — display name
- `picks[]` — array of `{ name, photo, eliminatedWeek }` objects
  - `name` must exactly match the key in `ratings.json`
  - `photo` is a relative path to the player's headshot in `img/survivor50/`
  - `eliminatedWeek` can be set here as a fallback, but `ratings.json` takes precedence

**Current teams:**
- **Gina:** Ozzy Lusth, Mike White, Savannah Louie, Rizo Velovic, Jenna Lewis-Dougherty, Angelina Keeley
- **Erin:** Colby Donaldson, Kamilla Karthigesu, Dee Valladares, Jonathan Young, Chrissy Hofbeck, Tiffany Ervin
- **Eric:** Aubry Bracco, Charlie Davis, Genevieve Mushaluk, Rick Devens, Emily Flippen, Christian Hubicki
- **Mike:** Benjamin "Coach" Wade, Joe Hunter, Stephenie LaGrossa Kendrick, Cirie Fields, Kyle Fraser, Q Burdette

---

## Key JS Functions

| Function | What it does |
|----------|-------------|
| `getRatingsAndStatus()` | Fetches `ratings.json`, returns `{ ratings, status }` maps |
| `isSnuffed(p, statusMap)` | Returns true if player is eliminated (checks both JSON status and hard-coded `eliminatedWeek`) |
| `reciprocal(rank)` | Returns `1/sqrt(rank)` — the scoring weight for a given rank |
| `computeTeamRawScore()` | Sums `reciprocal(rank)` for all active players on a team |
| `computeWinProbabilities()` | Returns array of win % for each team |
| `playerWinContrib()` | Individual player's share of the global win pool |
| `findTopContender()` | Finds the lowest-rank-number (best) active player across all teams — shown with ★ badge |
| `render()` | Async; fetches data and builds the DOM grid |

---

## Styling Notes

- Dark theme with CSS custom properties defined in `:root`
- Color coding: green (`--good`) ≥ 30% win prob, yellow (`--warn`) ≥ 18%, red (`--bad`) below
- Eliminated players show dimmed/grayscale card with "FIRE OUT" badge
- Responsive grid: 4 columns → 2 → 1 at narrow widths

---

## Working Instructions for Claude

- **Always update the Change Log below** when making any change to `index.html`, `ratings.json`, or `CLAUDE.md` itself. Add a row with today's date and a brief description of what changed.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-04-13 | Replaced `1/rank` scoring with `1/sqrt(rank)` to reduce bias toward top-ranked player |
| 2026-04-13 | Updated intro text: rankings now sourced from ChatGPT weekend research (not True Dork Times) |
| 2026-04-13 | Created this CLAUDE.md |
| 2026-04-13 | Simplified header subtitle — removed redundant scoring formula description (now only shown in pill) |
| 2026-04-13 | Added transparency note to header showing the ChatGPT prompt used to generate rankings |
