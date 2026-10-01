"""Liczy klasyfikację generalną WLB z data/raw/*.json i wstawia dane do szablonu strony."""
import json, glob, os, re, collections, hashlib
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_STARTS, BEST_N = 7, 7          # regulamin VIII.4
AGE_MIN, AGE_MAX = 7, 14
DIST = {"60m": 60, "300m": 300, "600m": 600}
# terminarz z regulaminu (plan.py) – rundy jeszcze nierozegrane pokazujemy jako puste kolumny
_plan_path = os.path.join(HERE, "data", "plan.json")
PLAN = {int(k): v for k, v in json.load(open(_plan_path, encoding="utf-8")).items()} if os.path.exists(_plan_path) else {}

meetings = []
for f in glob.glob(os.path.join(HERE, "data", "raw", "*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if d["rows"]:
        meetings.append(d)
meetings.sort(key=lambda d: d["meeting"]["startDateTime"])

seasons = collections.defaultdict(list)
for d in meetings:
    seasons[int(d["meeting"]["startDateTime"][:4])].append(d)

def fmt_round(m, n):
    return {"n": n, "date": m["startDateTime"][:10], "id": m["meetingId"],
            "venue": "Hala" if "HALA" in m["meetingName"].upper() or "Hala" in (m.get("venueName") or "") else "Stadion"}

out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
       "rules": {"minStarts": MIN_STARTS, "best": BEST_N}, "seasons": {}}

for year, ms in sorted(seasons.items()):
    rounds = [fmt_round(d["meeting"], i + 1) for i, d in enumerate(ms)]
    planned = len(PLAN.get(year, [])) or len(rounds)
    for i, date in enumerate(PLAN.get(year, [])[len(rounds):], start=len(rounds)):
        rounds.append({"n": i + 1, "date": date, "id": None, "venue": None})
    # najlepszy wynik zawodnika w rundzie / dystansie
    best = {}   # (dist, g, yob, athleteId) -> {ri: time}
    ath = {}
    for ri, d in enumerate(ms):
        for r in d["rows"]:
            if r["event"] not in DIST or not r["yob"] or not r["result"]:
                continue
            if r["startStatus"] != "Ok" or r["status"] != "Ok" or "specjal" in (r["label"] or "").lower():
                continue
            if not AGE_MIN <= year - r["yob"] <= AGE_MAX:
                continue
            g = "K" if r["gender"] == "Female" else "M"
            key = (DIST[r["event"]], g, r["yob"], r["athleteId"])
            t = round(r["result"] / 100)            # setne sekundy
            cur = best.setdefault(key, {})
            cur[ri] = min(t, cur.get(ri, t))
            ath[r["athleteId"]] = [r["name"], r["club"] or ""]
    cats = collections.defaultdict(dict)
    for (dist, g, yob, aid), res in best.items():
        cats[(dist, g, yob)][aid] = res
    out_cats = []
    for (dist, g, yob), people in sorted(cats.items()):
        # miejsce w rundzie = pozycja czasu w kategorii (rocznik + płeć + dystans)
        places = {}
        for ri in range(len(ms)):
            times = sorted(res[ri] for res in people.values() if ri in res)
            for aid, res in people.items():
                if ri in res:
                    places[(aid, ri)] = 1 + times.index(res[ri])
        rows = []
        for aid, res in people.items():
            pts = sorted(places[(aid, ri)] for ri in res)
            starts = len(res)
            # które starty liczą się do 7 najlepszych (najmniej punktów, przy remisie lepszy czas)
            order = sorted(res, key=lambda ri: (places[(aid, ri)], res[ri]))
            counted = set(order[:BEST_N])
            rows.append({"a": aid, "r": [[places[(aid, ri)], res[ri], 1 if ri in counted else 0] if ri in res else 0
                                          for ri in range(len(ms))],
                         "tot": sum(pts), "b7": sum(pts[:BEST_N]), "s": starts, "pb": min(res.values())})
        pbs = sorted(r["pb"] for r in rows)
        for r in rows:
            r["tr"] = 1 + pbs.index(r["pb"])
        cls = sorted([r for r in rows if r["s"] >= MIN_STARTS], key=lambda r: (r["b7"], r["pb"]))
        rest = sorted([r for r in rows if r["s"] < MIN_STARTS], key=lambda r: (-r["s"], r["tot"], r["pb"]))
        for i, r in enumerate(cls):
            r["rk"] = i + 1
        out_cats.append({"d": dist, "g": g, "y": yob, "rows": cls + rest})
    used = {r["a"] for c in out_cats for r in c["rows"]}
    out["seasons"][str(year)] = {"rounds": rounds, "done": len(ms), "planned": planned, "cats": out_cats,
                                 "ath": {str(k): v for k, v in ath.items() if k in used}}

data = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
page = tpl.replace("/*__DATA__*/null", data)
# fragment dla artifactu Claude (on sam dokłada <html>/<head>)
open(os.path.join(HERE, "wlb-klasyfikacja.html"), "w", encoding="utf-8").write(page.replace("<!--LOGO-->", ""))
# pełny dokument dla GitHub Pages (z logo WLB z site/logo-wlb.png)
os.makedirs(os.path.join(HERE, "site"), exist_ok=True)
page = page.replace("<!--LOGO-->", '<img class="logo" src="logo-wlb.png" width="104" height="80" alt="Warszawska Liga Biegowa">')
head, _, body = page.partition("</style>")
head = head.replace("<title>", '<link rel="icon" href="logo-wlb.png">\n<title>', 1)
full = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Nieoficjalna klasyfikacja generalna Warszawskiej Ligi Biegowej liczona z wyników Roster Athletics.">
{head}
body {{ margin: 0 }} [hidden] {{ display: none !important }}
</style>
</head>
<body>
{body}
</body>
</html>
"""
open(os.path.join(HERE, "site", "index.html"), "w", encoding="utf-8").write(full)
# skrót danych bez znacznika czasu – update.py porównuje go, żeby wiedzieć, czy coś się zmieniło
digest = hashlib.sha256(json.dumps({**out, "generated": None}, sort_keys=True).encode()).hexdigest()
open(os.path.join(HERE, "data", "data.sha256"), "w").write(digest)
print("seasons:", {y: (s["done"], len(s["cats"])) for y, s in out["seasons"].items()}, "bytes:", len(data))
