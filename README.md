# Milwaukee Bucks schedule calendar

A calendar you subscribe to once. Every Bucks game shows up in your calendar app and stays up to date on its own, including the play-in and playoffs if the team makes them, and future seasons.

**Subscribe page: https://rockeratheart.github.io/bucks-calendar/**

Calendar link (for apps that ask for a URL): `https://rockeratheart.github.io/bucks-calendar/bucks.ics`

## How to subscribe

The easiest way is to open the subscribe page above and tap the button for your calendar app. If you'd rather do it by hand:

**iPhone or iPad**
1. Open **Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar**.
2. Paste the calendar link and tap **Next**, then **Save**.

**Mac (Calendar app)**
1. Choose **File → New Calendar Subscription**.
2. Paste the calendar link and click **Subscribe**.

**Google Calendar** (do this on a computer; it then appears on your phone too)
1. On the left, next to **Other calendars**, click **+ → From URL**.
2. Paste the calendar link and click **Add calendar**.

**Outlook.com**
1. Choose **Add calendar → Subscribe from web**.
2. Paste the calendar link, name it, and click **Import**.

**Outlook desktop**
1. Choose **Add Calendar → From Internet**, paste the link, and confirm.

**Any other app:** look for "Subscribe to calendar", "Add calendar from URL" or "Internet calendar", and paste the calendar link.

## What you'll see

- Events named like **Celtics @ Bucks**: away team first, home team second.
- Times shown in Central Time. Your calendar converts them to your own time zone.
- **Watch:** in each event's description lists where to watch. National TV or streaming channels are shown when they're announced. Games without a national channel show **MY24 / Bucks+** for home games and **League Pass / Bucks+** for away games.
- Playoff round and series details in the description when they apply.
- Games with no start time yet appear as all-day events and move to the right time once it's set. An opponent not yet decided shows as **TBD**.

## Common questions

**How often does it update?** The calendar file refreshes every 6 hours, but your calendar app decides how often it checks for changes. Google Calendar can take up to a day. Apple and Outlook are usually faster.

**A game time changed. Why doesn't my calendar show it?** Give it time. If it's urgent, check the Bucks' website or the NBA app.

**Will I need to subscribe again next season?** No. The same subscription picks up each new season's games automatically.

**How do I remove it?** Delete the subscribed calendar in your calendar app's settings.

*Unofficial, fan-made calendar. Not affiliated with or endorsed by the Milwaukee Bucks or the NBA. Schedule data comes from ESPN's public data and may change or contain mistakes.*

---

## For the maintainer

### How it works
`generate_bucks_ics.py` pulls the Bucks schedule and national broadcast info from ESPN's public API and writes `bucks.ics`. A GitHub Actions workflow runs it every 6 hours and publishes the result, along with `index.html`, to GitHub Pages. NBA.com's own schedule feed rejects requests from GitHub's servers (HTTP 403), which is why ESPN is used.

### Setup
1. Keep these files in the repo: `generate_bucks_ics.py`, `index.html`, `README.md`, and `.github/workflows/update-calendar.yml`.
2. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
3. The workflow's generate step must copy the page into the published folder:
   ```yaml
   - name: Generate bucks.ics
     run: |
       mkdir -p public
       python3 generate_bucks_ics.py --output public/bucks.ics
       cp index.html public/index.html
   ```
4. Run the workflow once from the **Actions** tab (**Run workflow**). After that it runs on its own.

### Settings in `generate_bucks_ics.py`
- `FALLBACK_CHANNEL` (default `"MY24 / Bucks+"`): shown on home games with no national channel listed.
- `AWAY_FALLBACK_CHANNEL` (default `"League Pass / Bucks+"`): shown on away games with no national channel listed.
- `GAME_LENGTH`: each event lasts 2.5 hours, since the data has no end time.
- `CAL_NAME`: the calendar's display name.

### If a run fails
Open the failed run in the **Actions** tab and check the red step. If the script can't reach ESPN or finds no games, it stops without replacing the published calendar, so subscribers keep the last good version.
