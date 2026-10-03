#!/usr/bin/env python3
"""
Generate assets/activity.svg: an editorial contribution grid.

- Standard library only. No dependencies.
- Reads your real GitHub contribution calendar (GraphQL API).
- Never invents numbers. With --empty it writes a placeholder grid with "--" values.

Usage
  GITHUB_TOKEN=... LOGIN=your-username python scripts/generate_activity.py
  python scripts/generate_activity.py --empty
"""
import argparse
import datetime as dt
import json
import os
import urllib.request

CREAM, CHOC, BLACK, BURG, RED = "#F3ECDD", "#3B2418", "#110E0D", "#5C0F1E", "#D7161F"
TAN, COCOA = "#C9B79A", "#7A4A3A"
LEVELS = [(CHOC, 0.08), (TAN, 1), (COCOA, 1), (BURG, 1), (BLACK, 1)]

W, H = 800, 560
CELL, STEP, X0, Y0 = 10, 13.2, 44, 232

CSS = (
    ".serif{font-family:'Bodoni 72','Bodoni MT',Didot,'Playfair Display','Cormorant Garamond',Georgia,'Times New Roman',serif}"
    ".mono{font-family:ui-monospace,'SF Mono','JetBrains Mono',Menlo,Consolas,'Liberation Mono','Courier New',monospace;letter-spacing:.08em}"
)

QUERY = (
    "query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){"
    "contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions "
    "weeks{contributionDays{date contributionCount}}}}}}"
)


def fetch(login, token, year):
    body = json.dumps({
        "query": QUERY,
        "variables": {"login": login, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "editorial-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {payload.get('errors') or 'user not found'}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def sunday_index(d):
    return (d.weekday() + 1) % 7


def level_fn(counts):
    nz = sorted(v for v in counts.values() if v > 0)
    if not nz:
        return lambda v: 0
    q = [nz[int(len(nz) * p)] if int(len(nz) * p) < len(nz) else nz[-1] for p in (0.25, 0.5, 0.75)]
    def f(v):
        if v <= 0:
            return 0
        if v <= q[0]:
            return 1
        if v <= q[1]:
            return 2
        if v <= q[2]:
            return 3
        return 4
    return f


def longest_run(counts, year, today):
    best = run = 0
    d = dt.date(year, 1, 1)
    while d <= min(today, dt.date(year, 12, 31)):
        if counts.get(d.isoformat(), 0) > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
        d += dt.timedelta(days=1)
    return best


def render(counts, year, today, empty=False):
    jan1 = dt.date(year, 1, 1)
    first_sun = jan1 - dt.timedelta(days=sunday_index(jan1))
    lv = level_fn(counts)
    peak_day = max(counts, key=counts.get) if counts and max(counts.values()) > 0 else None

    cells, months = [], []
    d = jan1
    seen_month = 0
    while d.year == year:
        col = (d - first_sun).days // 7
        row = sunday_index(d)
        x, y = X0 + col * STEP, Y0 + row * STEP
        iso = d.isoformat()
        future = d > today
        if future or empty:
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" fill="{CHOC}" opacity="{0.05 if future else 0.08}"/>')
        else:
            colr, op = LEVELS[lv(counts.get(iso, 0))]
            cells.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" fill="{colr}" opacity="{op}"/>')
        if d.month != seen_month and d.day <= 7 and row <= 6:
            seen_month = d.month
            months.append(f'<text x="{x:.1f}" y="{Y0 - 14}" class="mono" font-size="11" fill="{CHOC}">{d.strftime("%b").upper()}</text>')
        if iso == peak_day and not empty:
            cells.append(f'<circle cx="{x + CELL / 2:.1f}" cy="{y + CELL / 2:.1f}" r="9" fill="none" stroke="{RED}" stroke-width="1"/>')
        d += dt.timedelta(days=1)

    if empty:
        total = active = best = peak = "--"
        peak_note = ""
        stamp = "AWAITING FIRST RUN"
        foot = "PLACEHOLDER. RUN scripts/generate_activity.py OR ENABLE THE WORKFLOW."
    else:
        yr_counts = {k: v for k, v in counts.items() if k.startswith(str(year))}
        total = f"{sum(yr_counts.values()):,}"
        active = str(sum(1 for v in yr_counts.values() if v > 0))
        best = str(longest_run(counts, year, today))
        peak = str(max(yr_counts.values()) if yr_counts else 0)
        peak_note = dt.date.fromisoformat(peak_day).strftime("%d %b").upper() if peak_day else ""
        stamp = "UPDATED " + today.strftime("%d %b %Y").upper()
        foot = "SOURCE: GITHUB CONTRIBUTION CALENDAR. NO STREAK COUNTER, ON PURPOSE."

    legend_y = Y0 + 7 * STEP + 22
    legend = [f'<text x="{764 - 5 * 15 - 78}" y="{legend_y + 9}" class="mono" font-size="11" fill="{CHOC}">LESS</text>']
    for i, (colr, op) in enumerate(LEVELS):
        legend.append(f'<rect x="{764 - 5 * 15 - 36 + i * 15}" y="{legend_y}" width="{CELL}" height="{CELL}" fill="{colr}" opacity="{op}"/>')
    legend.append(f'<text x="764" y="{legend_y + 9}" class="mono" font-size="11" fill="{CHOC}" text-anchor="end">MORE</text>')

    stats = [("TOTAL", total, False), ("ACTIVE DAYS", active, False), ("LONGEST RUN", best, False), ("BUSIEST DAY", peak, True)]
    sx = [36, 212, 388, 564]
    stat_svg = []
    for (label, val, hot), x in zip(stats, sx):
        stat_svg.append(f'<line x1="{x}" y1="408" x2="{x + 140}" y2="408" stroke="{CHOC}" stroke-width=".75"/>')
        if hot:
            stat_svg.append(f'<circle cx="{x + 3.5}" cy="428" r="3.5" fill="{RED}"/>')
            stat_svg.append(f'<text x="{x + 14}" y="432" class="mono" font-size="11" fill="{CHOC}">{label}</text>')
        else:
            stat_svg.append(f'<text x="{x}" y="432" class="mono" font-size="11" fill="{CHOC}">{label}</text>')
        stat_svg.append(f'<text x="{x}" y="486" class="serif" font-size="52" fill="{BLACK}">{val}</text>')
        if hot and peak_note:
            stat_svg.append(f'<text x="{x + 92}" y="486" class="mono" font-size="11" fill="{CHOC}">{peak_note}</text>')

    title = f"Activity {year}. Contribution grid, one square per day."
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">{title}</title>
<defs><style>{CSS}</style>
<filter id="g" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .23 0 0 0 0 .14 0 0 0 0 .09 .22 0 0 0 -.02"/></filter></defs>
<rect width="{W}" height="{H}" fill="{CREAM}"/>
<text x="36" y="40" class="mono" font-size="12" fill="{CHOC}">ACTIVITY / {year}</text>
<text x="764" y="40" class="mono" font-size="12" fill="{CHOC}" text-anchor="end">{stamp}</text>
<line x1="36" y1="56" x2="764" y2="56" stroke="{CHOC}" stroke-width=".75"/>
<text x="36" y="136" class="serif" font-size="58" font-style="italic" fill="{BLACK}">Contributions, quietly.</text>
<text x="36" y="168" class="mono" font-size="11" fill="{CHOC}">FIG. 04. ONE SQUARE, ONE DAY.</text>
{''.join(months)}
{''.join(cells)}
{''.join(legend)}
{''.join(stat_svg)}
<line x1="36" y1="520" x2="764" y2="520" stroke="{CHOC}" stroke-width=".75"/>
<text x="36" y="542" class="mono" font-size="11" fill="{CHOC}">{foot}</text>
<rect width="{W}" height="{H}" filter="url(#g)"/>
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--empty", action="store_true", help="write a placeholder with no data")
    ap.add_argument("--login", default=os.environ.get("LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "assets", "activity.svg"))
    a = ap.parse_args()
    today = dt.date.today()
    if a.empty:
        counts = {}
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not (token and a.login):
            raise SystemExit("Set GITHUB_TOKEN and LOGIN (or use --empty).")
        counts = fetch(a.login, token, today.year)
    svg = render(counts, today.year, today, empty=a.empty)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
