import json, os, urllib.request
from datetime import datetime

def first_season():
    """Pierwszy sezon publikowany imiennie: bieżący i dwa poprzednie (ustalenie z IOD, regulamin WLB).
    Rekordy ligi z wcześniejszych sezonów zostają w data/records-archiwum.json.
    Zmienna WLB_FIRST_SEASON pozwala jednorazowo zmienić granicę (np. przy tworzeniu archiwum)."""
    return int(os.environ.get("WLB_FIRST_SEASON") or datetime.now().year - 2)
API = "https://api.meets.rosterathletics.com/api/public"
def req(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)
