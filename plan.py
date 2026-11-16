"""Czyta terminarz rund z regulaminu na warszawskaligabiegowa.pl -> data/plan.json ({rok: [[data, obiekt]]})."""
import html, json, os, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# nowa strona (od października 2026) i stary adres z Wixa
URLS = ["https://www.warszawskaligabiegowa.pl/regulamin.html", "https://www.warszawskaligabiegowa.pl/regulamin"]
MONTHS = {m: i + 1 for i, m in enumerate(["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
                                           "sierpnia", "września", "października", "listopada", "grudnia"])}
DATE = r"(\d{1,2})\s+(\w+)\s+(\d{4})"
PATTERNS = [
    # tabela: <tr><td>1</td><td>8 marca 2026</td><td>Stadion</td></tr>
    rf"<tr>\s*<td>\s*(\d+)\s*</td>\s*<td>\s*{DATE}\s*</td>\s*<td>\s*(\w*)",
    # tekst: Runda 1 8 marca 2026 (Stadion)
    rf"Runda\s+(\d+)\s+{DATE}\s*(?:\(\s*(\w+)\s*\))?",
]

def parse(page):
    found = {}
    for i, pat in enumerate(PATTERNS):
        text = page if i == 0 else html.unescape(re.sub(r"<[^>]+>", " ", page))
        for n, day, month, year, venue in re.findall(pat, text, re.I):
            if month.lower() in MONTHS:
                venue = {"hala": "Hala", "stadion": "Stadion"}.get(venue.lower())
                found.setdefault(year, {})[int(n)] = [f"{year}-{MONTHS[month.lower()]:02d}-{int(day):02d}", venue]
        if found:
            break
    return found

def update_plan():
    path = os.path.join(HERE, "data", "plan.json")
    plan = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    found = {}
    for url in URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            found = parse(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore"))
        except Exception as e:                  # brak strony nie blokuje odświeżenia wyników
            print("plan:", url, e)
        if found:
            break
    if not found:
        print("plan: nie znaleziono terminarza w regulaminie, zostaje poprzedni")
    for year, rounds in found.items():
        plan[year] = [rounds[k] for k in sorted(rounds)]
    json.dump(plan, open(path, "w", encoding="utf-8"), indent=1)
    print("plan:", {y: len(v) for y, v in plan.items()})
    return plan

if __name__ == "__main__":
    update_plan()
