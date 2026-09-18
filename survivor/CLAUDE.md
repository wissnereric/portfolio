# Survivor Contest Tracker — Claude Reference

## What This Is

A single-page web app (`index.html`) that tracks a friend-group Survivor 51 fantasy contest. Participants each draft a set of castaways at the start of the season. The page displays each person's picks, shows which players have been eliminated, and calculates a win probability for each contestant.

A second, independent contest for another group runs on `index_Brittany.html` — same scoring engine and same shared `ratings.json`, different owners/picks. See "Running Multiple Contests" below.

Rankings are updated weekly via an automated GitHub Actions workflow (`scripts/update_rankings.py`) that calls the Claude API with web search to synthesize episode recaps and analysis.

---

## File Overview

| File | Purpose |
|------|---------|
| `index.html` | Main contest — HTML, CSS, and JS in one file |
| `index_Brittany.html` | Second, independent contest ("Brittany's League") — same engine, own `teams` |
| `assign.html` | Draft-assignment utility — click-to-draft UI that generates the `teams` array to paste into either page after a draft |
| `ratings.json` | Weekly-updated player rankings and elimination status, shared by both contest pages |
| `img/survivor51/` | Player headshot `.jpg` images, one per castaway, plus `roster.json` (name + photo manifest used by `assign.html`) |
| `img/survivor50/` | Prior season's images, kept for history |

---

## Running Multiple Contests

Each contest is its own HTML file (`index.html`, `index_Brittany.html`, ...) with its own hard-coded `DATA.teams`, but all of them point `rankingsUrl` at the same `./ratings.json` — castaway performance is the same regardless of which group drafted them, so rankings only need to be maintained in one place.

**To add another group's contest:** copy `index_Brittany.html` to a new `index_<Name>.html`, leave `rankingsUrl` pointing at `./ratings.json`, and use `assign.html` (below) to generate that group's `teams` array after their draft.

---

## Draft Assignment Utility (`assign.html`)

Solves "how do we record who drafted which castaway" after a live draft. Open it in a browser:

1. It loads the castaway pool from a roster file (default `./img/survivor51/roster.json` — name + photo pairs).
2. Type owner names (one per line), click "Set owners."
3. Click an owner to make them active, then click castaways in the pool to draft them — picks move out of the pool as they're taken. Click the ✕ on a pick to undo it.
4. Click "Generate" to produce a ready-to-paste `teams: [...]` block matching the exact structure `index.html` expects (`owner`, `picks[]` with `name`/`photo`/`eliminatedWeek`).
5. Paste that block over the existing `teams: [...]` in the target page (`index.html` or `index_<Name>.html`).

Progress autosaves to the browser's localStorage (per-browser, not shared), so a draft can be done incrementally without losing state. **This tool only edits its own in-memory state — it never writes to the repo.** You still paste its output into the target file by hand.

For a future season: create a new `img/survivor<N>/roster.json` (see the Survivor 51 one for the shape) and point the tool's "Roster file" field at it.

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

## Team Picks (hard-coded in `index.html` / `index_<Name>.html`)

Defined in each page's `DATA.teams` array. Each entry has:
- `owner` — display name
- `picks[]` — array of `{ name, photo, eliminatedWeek }` objects
  - `name` must exactly match the key in `ratings.json`
  - `photo` is a relative path to the player's headshot in `img/survivor51/`
  - `eliminatedWeek` can be set here as a fallback, but `ratings.json` takes precedence

Generate this array with `assign.html` after a draft rather than hand-editing it — see "Draft Assignment Utility" above.

**Current state:** Season 51 draft hasn't happened yet. `index.html` has the four usual owners (Gina, Erin, Eric, Mike) with empty `picks[]`. `index_Brittany.html` has an empty `teams[]` entirely — populate both with `assign.html` once each group drafts.

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
| 2026-04-23 | Added `scripts/update_rankings.py` — automated Claude API + web search rankings updater |
| 2026-04-23 | Added `.github/workflows/update_rankings.yml` — weekly cron job (Thu 23:00 UTC / 6–7 PM ET) to run the updater and commit ratings.json |
| 2026-04-23 | Added commentary feature: script saves `commentary` + `episode` fields to ratings.json; index.html renders a styled "Episode N Analysis" panel below the grid |
| 2026-04-30 | Updated header subtitle: reflects automated Claude API (not ChatGPT), Thursday 11 PM UTC schedule, and actual prompt text used by update_rankings.py |
| 2026-06-08 | Paused weekly rankings workflow (commented out cron schedule) until next season — workflow_dispatch still available for manual runs |
| 2026-09-18 | New season setup: reset `ratings.json` to the 21 Survivor 51 castaways (preseason placeholder ratings, all IN); downloaded official CBS press headshots into `img/survivor51/` with a `roster.json` manifest |
| 2026-09-18 | Cleared `DATA.teams` in `index.html` to empty picks for the same four owners (Gina, Erin, Eric, Mike), pending this season's draft |
| 2026-09-18 | Added `index_Brittany.html` — second, independent contest page for another group, sharing `ratings.json` but with its own (currently empty) `teams` |
| 2026-09-18 | Added `assign.html` — click-to-draft utility that generates a `teams` array from a roster file + owner list, to be pasted into `index.html`/`index_<Name>.html` after each draft |
| 2026-09-18 | Updated `scripts/update_rankings.py` prompt/docstring from "Survivor 50" to "Survivor 51"; re-enabled the weekly GitHub Actions cron schedule (Thu 23:00 UTC) now that the season is starting |
| 2026-09-18 | Fixed a pre-existing bug in `index.html`'s header: smart/curly quotes in `class="..."` attributes (from a prior paste) were breaking the `.sub`/`.toolbar`/`.pill` styling — replaced with straight quotes |
