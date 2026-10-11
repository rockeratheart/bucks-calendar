#!/usr/bin/env python3
"""Build a subscribable .ics feed of the Milwaukee Bucks schedule.

Source: NBA.com's official schedule data (the same file that powers
nba.com/bucks/schedule). It covers preseason, regular season, NBA Cup,
play-in and playoffs, so every phase appears automatically once the NBA
publishes it.

Event title:  "{Away Team} @ {Home Team}"
Time zone:    America/Chicago (Central Time)
Description:  where to watch (national TV/streaming + the Bucks-side local
              broadcast), plus game label / series status and arena.

Usage:
    python3 generate_bucks_ics.py --output public/bucks.ics
    python3 generate_bucks_ics.py --input schedule.json --output bucks.ics   # offline test
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SOURCE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
BUCKS_ID = 1610612749
CENTRAL = ZoneInfo("America/Chicago")
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


def fetch_schedule():
    req = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
            "Accept": "application/json",
        },
    )
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # network / HTTP errors
            last = e
            time.sleep(2 ** attempt)
    raise SystemExit(f"Could not fetch schedule: {last}")


def team_name(team):
    team = team or {}
    if not team.get("teamId"):
        return "TBD"
    name = f"{team.get('teamCity', '')} {team.get('teamName', '')}".strip()
    return name or team.get("teamTricode") or "TBD"


def broadcaster_names(entries):
    out = []
    for b in entries or []:
        n = b.get("broadcasterDisplay") or b.get("broadcasterAbbreviation")
        if n and n not in out:
            out.append(n)
    return out


def watch_list(game, bucks_home):
    b = game.get("broadcasters") or {}
    side = "home" if bucks_home else "away"
    names = []
    for key in ("nationalTvBroadcasters", "nationalOttBroadcasters",
                f"{side}TvBroadcasters", f"{side}OttBroadcasters"):
        for n in broadcaster_names(b.get(key)):
            if n not in names:
                names.append(n)
    return names


def esc(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """RFC 5545 line folding at 75 octets."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
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


def parse_utc(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def build_event(game, stamp):
    home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
    bucks_home = home.get("teamId") == BUCKS_ID
    title = f"{team_name(away)} @ {team_name(home)}"

    watch = watch_list(game, bucks_home)
    lines = ["Watch: " + (", ".join(watch) if watch else "TBD (not yet announced)")]
    label = " – ".join(x for x in (game.get("gameLabel"), game.get("gameSubLabel")) if x)
    if label:
        lines.append(label)
    if game.get("seriesText"):
        lines.append(game["seriesText"])
    arena = ", ".join(x for x in (game.get("arenaName"), game.get("arenaCity")) if x)
    if arena:
        lines.append(f"Arena: {arena}")

    start = parse_utc(game.get("gameDateTimeUTC"))
    status_text = (game.get("gameStatusText") or "").strip().upper()
    tbd = start is None or status_text == "TBD"

    ev = ["BEGIN:VEVENT",
          f"UID:nba-{game['gameId']}@bucks-calendar",
          f"DTSTAMP:{stamp}",
          f"SUMMARY:{esc(title)}",
          f"DESCRIPTION:{esc(chr(10).join(lines))}"]
    if arena:
        ev.append(f"LOCATION:{esc(arena)}")

    if tbd:
        day_src = game.get("gameDateEst") or game.get("gameDateUTC") or ""
        try:
            day = datetime.fromisoformat(day_src.replace("Z", "+00:00")).date()
        except ValueError:
            return None
        ev.append(f"DTSTART;VALUE=DATE:{day:%Y%m%d}")
        ev.append(f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}")
        ev[4] = "DESCRIPTION:" + esc("Start time TBD\n" + "\n".join(lines))
    else:
        local = start.astimezone(CENTRAL)
        end = (start + GAME_LENGTH).astimezone(CENTRAL)
        ev.append(f"DTSTART;TZID=America/Chicago:{local:%Y%m%dT%H%M%S}")
        ev.append(f"DTEND;TZID=America/Chicago:{end:%Y%m%dT%H%M%S}")
    ev.append("END:VEVENT")
    return ev


def build_calendar(data):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    games = []
    for gd in data["leagueSchedule"]["gameDates"]:
        for g in gd.get("games", []):
            ids = {(g.get("homeTeam") or {}).get("teamId"),
                   (g.get("awayTeam") or {}).get("teamId")}
            if BUCKS_ID in ids:
                games.append(g)

    out = ["BEGIN:VCALENDAR", "VERSION:2.0",
           "PRODID:-//bucks-calendar//NBA schedule feed//EN",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           f"X-WR-CALNAME:{CAL_NAME}",
           "X-WR-TIMEZONE:America/Chicago",
           "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
           "X-PUBLISHED-TTL:PT6H", VTIMEZONE.replace("\n", "\r\n")]
    count = 0
    for g in games:
        ev = build_event(g, stamp)
        if ev:
            out.extend(ev)
            count += 1
    out.append("END:VCALENDAR")
    body = "\r\n".join(fold(l) if "\n" not in l else l for l in out) + "\r\n"
    return body, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="read schedule JSON from a local file instead of fetching")
    ap.add_argument("--output", default="bucks.ics")
    args = ap.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch_schedule()

    body, count = build_calendar(data)
    if count == 0:
        raise SystemExit("No Bucks games found in the schedule data; refusing to overwrite the feed.")
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    print(f"Wrote {count} events to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
