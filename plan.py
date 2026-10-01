"""Czyta terminarz rund z regulaminu na warszawskaligabiegowa.pl -> data/plan.json ({rok: [daty]})."""
import html, json, os, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.warszawskaligabiegowa.pl/regulamin"
MONTHS = {m: i + 1 for i, m in enumerate(["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
                                           "sierpnia", "września", "października", "listopada", "grudnia"])}

def update_plan():
    path = os.path.join(HERE, "data", "plan.json")
    plan = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        t = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    except Exception as e:                      # brak strony nie blokuje odświeżenia wyników
        print("plan: nie udało się pobrać regulaminu:", e)
        return plan
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    found = {}
    for n, day, month, year in re.findall(r"Runda\s+(\d+)\s+(\d{1,2})\s+(\w+)\s+(\d{4})", t):
        if month.lower() in MONTHS:
            found.setdefault(year, {})[int(n)] = f"{year}-{MONTHS[month.lower()]:02d}-{int(day):02d}"
    for year, rounds in found.items():
        plan[year] = [rounds[k] for k in sorted(rounds)]
    json.dump(plan, open(path, "w", encoding="utf-8"), indent=1)
    print("plan:", {y: len(v) for y, v in plan.items()})
    return plan

if __name__ == "__main__":
    update_plan()
