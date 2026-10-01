"""Pobiera wyniki wszystkich rund WLB z publicznego API Roster Athletics -> data/raw/<meetingId>.json"""
import json, os, re, sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from ra import req

ORG_ID = 315
RAW = os.path.join(os.path.dirname(__file__), "data", "raw")
os.makedirs(RAW, exist_ok=True)

def list_meetings():
    out, body = {}, {"tz": "Europe/Warsaw", "tzMinutes": 120, "orgId": ORG_ID, "first": True}
    while True:
        d = req("/meeting/search/v2", body)
        for m in d["meets"]:
            out[m["meetingId"]] = m
        if not d["after"] or not d["meets"]:
            break
        last = d["meets"][-1]
        body = {"tz": "Europe/Warsaw", "tzMinutes": 120, "orgId": ORG_ID,
                "after": last["startDateTime"], "afterId": last["meetingId"]}
    return sorted(out.values(), key=lambda m: (m["startDateTime"], m["meetingId"]))

def fetch_meeting(m, force=False):
    mid = m["meetingId"]
    path = os.path.join(RAW, f"{mid}.json")
    # zakończone rundy trzymamy w cache, ale przez 14 dni pobieramy je ponownie (protesty, korekty wyników)
    recent = datetime.strptime(m["startDateTime"][:10], "%Y-%m-%d") > datetime.now() - timedelta(days=14)
    if os.path.exists(path) and not force and m["meetingStatus"] == "Finished" and not recent:
        return path
    details = req(f"/meeting/{mid}/details")
    events = {e["eventIdPk"]: e["eventName"] for e in details.get("sportEvents", [])}
    sched = [x["entityDto"] for x in req(f"/meeting/{mid}/schedule")["data"]]
    top = [e for e in sched if not e.get("parentMeetingEventIdFk") and e.get("hasResults")]
    rows = []
    def one(ev):
        r = req(f"/meeting/{mid}/results-v2/{ev['meetingEventIdPk']}")
        ath = {a["athleteIdPk"]: a for a in r["athleteList"]}
        res = {}
        for x in r["resultList"]:
            d = x["entityDto"]
            if d.get("attempt", 0) == 0:
                res[d["meetingParticipantIdFk"]] = d
        out = []
        for x in r["mpList"]:
            p = x["entityDto"]
            a = ath.get(p["athleteIdFk"], {})
            rr = res.get(p["meetingParticipantIdPk"], {})
            out.append({
                "event": events.get(ev["eventIdFk"], str(ev["eventIdFk"])),
                "gender": ev["gender"],
                "label": ev.get("label", ""),
                "athleteId": p["athleteIdFk"],
                "name": a.get("athleteName"),
                "first": a.get("firstName"), "last": a.get("lastName"),
                "club": a.get("primaryClubName"),
                "yob": a.get("yearOfBirth"),
                "place": p.get("place"),
                "startStatus": p.get("startStatus"),
                "status": rr.get("resultStatus"),
                "result": rr.get("result"),
            })
        return out
    with ThreadPoolExecutor(6) as ex:
        for part in ex.map(one, top):
            rows += part
    meta = {k: m.get(k) for k in ("meetingId", "meetingName", "startDateTime", "meetingStatus", "venueName")}
    data = {"meeting": meta, "rows": rows}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path

if __name__ == "__main__":
    ms = list_meetings()
    with open(os.path.join(os.path.dirname(__file__), "data", "meetings.json"), "w", encoding="utf-8") as f:
        json.dump(ms, f, ensure_ascii=False, indent=1)
    for m in ms:
        if m["meetingStatus"] == "Cancelled":
            continue
        fetch_meeting(m)
        print(m["meetingId"], m["meetingName"], flush=True)
