import json, os, urllib.request

def first_season():
    """Pierwszy sezon publikowany imiennie.

    Do 90 dni po ogłoszeniu klasyfikacji końcowej 2026 publikujemy wyłącznie
    sezon 2026. Rekordy ze wszystkich sezonów pozostają w
    data/records-archiwum.json. Zmienna WLB_FIRST_SEASON służy wyłącznie do
    jednorazowych prac archiwizacyjnych.
    """
    return int(os.environ.get("WLB_FIRST_SEASON") or 2026)
API = "https://api.meets.rosterathletics.com/api/public"
def req(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)
