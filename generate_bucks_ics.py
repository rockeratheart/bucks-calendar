#!/usr/bin/env python3
"""Build a subscribable .ics feed of the Milwaukee Bucks schedule.

Data source: ESPN's public JSON API. (NBA.com's own schedule feed refuses
requests from GitHub's servers, so it can't be used from GitHub Actions.)

Covers preseason, regular season, play-in and playoffs for the current
season, and rolls over to the next season automatically after June.

Event title:  "{Away Team} @ {Home Team}"
Time zone:    America/Chicago (Central Time)
Description:  Watch: the national TV/streaming channel(s) ESPN lists for the
              game. With no national channel: "Bucks+" for home games and
              "League Pass / Bucks+" for away games. Also arena and playoff
              round if any.

Usage:
    python3 generate_bucks_ics.py --output public/bucks.ics
"""
import argparse
import sys
import time
import json
import urllib.request
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
TEAM_SLUG = "mil"
BUCKS_ESPN_ID = "15"
SEASON_TYPES = (1, 2, 3, 5)  # preseason, regular season, postseason, play-in

# ESPN only lists NATIONAL broadcasts. A game with no national channel listed
# shows one of these on its "Watch:" line instead:
FALLBACK_CHANNEL = "Bucks+"                      # home games
AWAY_FALLBACK_CHANNEL = "League Pass / Bucks+"   # games played away from home

CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")
GAME_LENGTH = timedelta(hours=2, minutes=30)
CAL_NAME = "Milwaukee Bucks"

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/Chicago
X-LIC-LOCATION:America/Chicago
BEGIN:DAYLIGHT
TZOFFSETFROM:-0600
TZOFFSETTO:-0500
TZNAME:CDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0500
TZOFFSETTO:-0600
TZNAME:CST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""


def get_json(url, tries=4):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 bucks-calendar", "Accept": "application/json"}
    )
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(2 ** attempt)
    print(f"warning: could not fetch {url}: {last}", file=sys.stderr)
    return None


def season_year(today):
    """ESPN labels a season by the year it ends: 2026-27 is 2027."""
    return today.year + 1 if today.month >= 7 else today.year


def parse_utc(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def fetch_events(year):
    events = {}
    for st in SEASON_TYPES:
        data = get_json(f"{API}/teams/{TEAM_SLUG}/schedule?season={year}&seasontype={st}")
        for ev in (data or {}).get("events", []):
            events[str(ev["id"])] = ev
    return events


def fetch_broadcasts(events, today):
    """Map event id -> list of broadcast names, from ESPN's per-day scoreboard."""
    days = set()
    for ev in events.values():
        start = parse_utc(ev.get("date"))
        if start:
            d = start.astimezone(EASTERN).date()
            if d >= today - timedelta(days=1):
                days.add(d)
    found = {}
    for d in sorted(days):
        data = get_json(f"{API}/scoreboard?dates={d:%Y%m%d}&limit=50")
        for ev in (data or {}).get("events", []):
            eid = str(ev.get("id"))
            if eid not in events:
                continue
            names = []
            for comp in ev.get("competitions", []):
                for b in comp.get("broadcasts", []) or []:
                    market = (b.get("market") or "")
                    if isinstance(market, dict):
                        market = market.get("type", "")
                    for n in b.get("names", []) or []:
                        if n and n not in names and str(market).lower() in ("national", ""):
                            names.append(n)
                for g in comp.get("geoBroadcasts", []) or []:
                    mtype = str((g.get("market") or {}).get("type", "")).lower()
                    n = (g.get("media") or {}).get("shortName")
                    if n and n not in names and mtype == "national":
                        names.append(n)
            if names:
                found[eid] = names
    return found


def esc(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """RFC 5545 line folding at 75 octets."""
    if len(line.encode("utf-8")) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(cur) + len(enc) > limit:
            parts.append(cur)
            cur = b""
        cur += enc
    parts.append(cur)
    return "\r\n ".join(p.decode("utf-8") for p in parts)


def team_name(competitor):
    """Team nickname only, e.g. "Bucks" (no city)."""
    team = (competitor or {}).get("team") or {}
    name = team.get("shortDisplayName")
    if not name:
        full = team.get("displayName") or ""
        loc = team.get("location") or ""
        name = full[len(loc):].strip() if loc and full.startswith(loc) else full
    return name if name and name.upper() != "TBD" else "TBD"


def build_event(ev, broadcasts, stamp):
    comp = (ev.get("competitions") or [{}])[0]
    by_side = {c.get("homeAway"): c for c in comp.get("competitors", [])}
    home, away = by_side.get("home"), by_side.get("away")
    if not home or not away:
        return None
    title = f"{team_name(away)} @ {team_name(home)}"

    bucks_away = (home.get("id") != BUCKS_ESPN_ID
                  and (home.get("team") or {}).get("id") != BUCKS_ESPN_ID)
    fallback = AWAY_FALLBACK_CHANNEL if bucks_away else FALLBACK_CHANNEL
    watch = list(broadcasts) or [fallback]
    lines = ["Watch: " + ", ".join(watch)]

    for note in comp.get("notes", []) or []:
        if note.get("headline"):
            lines.append(note["headline"])
    st = (ev.get("seasonType") or {}).get("name")
    if st and st != "Regular Season":
        lines.append(st)

    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    arena = ", ".join(x for x in (venue.get("fullName"), addr.get("city")) if x)
    if arena:
        lines.append(f"Arena: {arena}")

    start = parse_utc(ev.get("date"))
    tbd = start is None or ev.get("timeValid") is False

    out = ["BEGIN:VEVENT",
           f"UID:espn-{ev['id']}@bucks-calendar",
           f"DTSTAMP:{stamp}",
           f"SUMMARY:{esc(title)}"]
    if arena:
        out.append(f"LOCATION:{esc(arena)}")
    if tbd:
        if start is None:
            return None
        day = start.astimezone(CENTRAL).date()
        lines.insert(0, "Start time TBD")
        out.append(f"DTSTART;VALUE=DATE:{day:%Y%m%d}")
        out.append(f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}")
    else:
        local = start.astimezone(CENTRAL)
        end = (start + GAME_LENGTH).astimezone(CENTRAL)
        out.append(f"DTSTART;TZID=America/Chicago:{local:%Y%m%dT%H%M%S}")
        out.append(f"DTEND;TZID=America/Chicago:{end:%Y%m%dT%H%M%S}")
    out.insert(4, f"DESCRIPTION:{esc(chr(10).join(lines))}")
    out.append("END:VEVENT")
    return out


def build_calendar(events, broadcasts):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0",
           "PRODID:-//bucks-calendar//ESPN schedule feed//EN",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           f"X-WR-CALNAME:{CAL_NAME}",
           "X-WR-TIMEZONE:America/Chicago",
           "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
           "X-PUBLISHED-TTL:PT6H", VTIMEZONE.replace("\n", "\r\n")]
    count = 0
    for eid in sorted(events, key=lambda i: events[i].get("date", "")):
        ev = build_event(events[eid], broadcasts.get(eid, []), stamp)
        if ev:
            out.extend(ev)
            count += 1
    out.append("END:VCALENDAR")
    body = "\r\n".join(fold(l) if "\n" not in l else l for l in out) + "\r\n"
    return body, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="bucks.ics")
    args = ap.parse_args()

    today = date.today()
    events = fetch_events(season_year(today))
    if not events:
        raise SystemExit("No Bucks games returned by ESPN; refusing to overwrite the feed.")
    broadcasts = fetch_broadcasts(events, today)
    body, count = build_calendar(events, broadcasts)
    if count == 0:
        raise SystemExit("No usable games; refusing to overwrite the feed.")
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    print(f"Wrote {count} events ({len(broadcasts)} with broadcast info) to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
