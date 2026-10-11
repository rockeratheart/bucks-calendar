# Milwaukee Bucks calendar feed

Auto-updating `.ics` feed built from NBA.com's official schedule data
(`cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`, the file behind
nba.com/bucks/schedule). Preseason, regular season, NBA Cup, play-in and
playoff games appear automatically once the NBA publishes them.

- Title: `Away Team @ Home Team`
- All times: Central Time (`America/Chicago`)
- Description: `Watch:` national TV/streaming plus the Bucks-side local broadcast
- Games with no announced time (e.g. future playoff games) show as all-day events
  and update to the real time once scheduled; unknown opponents show as `TBD`.

## One-time setup (about 3 minutes)

1. Create a new GitHub repository (public is simplest) and push these files to `main`:
   `generate_bucks_ics.py`, `.github/workflows/update-calendar.yml`, `README.md`.
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Repo **Actions** tab → "Update Bucks calendar" → **Run workflow** (it also runs every 6 hours).
4. Your feed is at `https://<your-username>.github.io/<repo-name>/bucks.ics`.

## Subscribe

- **Apple Calendar / iPhone**: open `webcal://<your-username>.github.io/<repo-name>/bucks.ics`
- **Google Calendar**: Other calendars **+ → From URL**, paste the `https://` link
  (Google refreshes subscribed calendars on its own schedule, often 12–24 hours)
- **Outlook**: Add calendar → Subscribe from web

## If a run fails

If NBA.com blocks the request or the schedule contains no Bucks games, the
workflow fails and the previously published feed stays live. Check the Actions log.
