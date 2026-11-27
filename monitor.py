"""Monitor finału WLB. Standardowa biblioteka; stan i sekrety poza repozytorium."""
import argparse
import collections
import fcntl
import json
import logging
import os
import re
from pathlib import Path
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from fetch import list_meetings
from ra import req

DIST = {'60m': 60, '300m': 300, '600m': 600}

def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
    tmp.chmod(0o600)
    tmp.replace(path)

def valid(row, year):
    return (row.get('event') in DIST and row.get('yob') and 7 <= year-row['yob'] <= 14
            and row.get('result') and row.get('startStatus') == 'Ok'
            and row.get('status') == 'Ok' and 'specjal' not in (row.get('label') or '').lower()
            and row.get('gender') in ('Male', 'Female'))

def category(row, year):
    return f"{DIST[row['event']]}-{'K' if row['gender']=='Female' else 'M'}-{year-row['yob']}-H"

def title(key, year):
    d, g, age, _ = key.split('-')
    return f"{d} m • {'dziewczęta' if g=='K' else 'chłopcy'} • {age} lat (rocznik {year-int(age)})"

def seconds(t):
    return f'{t/100:.2f}'.replace('.', ',') + ' s'

def snapshot(meeting):
    mid = meeting['meetingId']
    details = req(f'/meeting/{mid}/details')
    if details.get('season') != 'Indoor' or details.get('organisationId') != 315:
        raise ValueError('Zawody nie są halową rundą organizatora WLB')
    schedule = [x['entityDto'] for x in req(f'/meeting/{mid}/schedule')['data']]
    events = {e['eventIdPk']: e['eventName'] for e in details['sportEvents']}
    groups = {a['ageGroupIdPk']: a for a in details['ageGroups']}
    year = int(meeting['startDateTime'][:4])
    rows, cat_events, completed = [], collections.defaultdict(set), set()
    for e in schedule:
        if e.get('parentMeetingEventIdFk') or events.get(e['eventIdFk']) not in DIST or 'specjal' in e.get('label', '').lower():
            continue
        eid = e['meetingEventIdPk']
        members = [e] + [s for s in schedule if s.get('parentMeetingEventIdFk') == eid]
        if all(s.get('resultsComplete') is True for s in members):
            completed.add(eid)
        ag = groups.get(e.get('ageGroupIdFk'), {})
        # Include every scheduled category, even when its last heat has no result yet.
        suffix = 'Female' if e['gender'] == 'Female' else ''
        lo, hi = ag.get('rangeStart'+suffix, ag.get('rangeStart', 0)), ag.get('rangeEnd'+suffix, ag.get('rangeEnd', 999))
        ages = re.fullmatch(r'(\d+)[–-](\d+) lat', e.get('label', '').strip())
        if ages:
            lo, hi = map(int, ages.groups())
        if ag.get('rangeType') != 'Age':
            lo, hi = 7, 14  # unknown range: conservatively block all ages until complete
        for age in range(max(7, lo), min(14, hi)+1):
            k = f"{DIST[events[e['eventIdFk']]]}-{'K' if e['gender']=='Female' else 'M'}-{age}-H"
            cat_events[k].add(eid)
        if not e.get('hasResults'):
            continue
        data = req(f'/meeting/{mid}/results-v2/{eid}')
        athletes = {a['athleteIdPk']: a for a in data['athleteList']}
        results = {x['entityDto']['meetingParticipantIdFk']: x['entityDto'] for x in data['resultList'] if x['entityDto'].get('attempt', 0) == 0}
        for x in data['mpList']:
            p = x['entityDto']; a = athletes.get(p['athleteIdFk'], {}); r = results.get(p['meetingParticipantIdPk'], {})
            row = dict(event=events[e['eventIdFk']], gender=e['gender'], label=e.get('label', ''), athleteId=p['athleteIdFk'], name=a.get('athleteName', '?'), club=a.get('primaryClubName') or '', yob=a.get('yearOfBirth'), startStatus=p.get('startStatus'), status=r.get('resultStatus'), result=r.get('result'))
            rows.append(row)
            if row['yob'] and 7 <= year-row['yob'] <= 14:
                cat_events[category(row, year)].add(eid)
    # A second schedule read prevents sending podium against an earlier completion state.
    after = [x['entityDto'] for x in req(f'/meeting/{mid}/schedule')['data']]
    if after != schedule:
        raise ValueError('Harmonogram zmienił się podczas odczytu; ponawiam')
    ready = {k for k, ids in cat_events.items() if ids and ids <= completed}
    return {'meeting': {**meeting, 'season': 'Indoor'}, 'rows': rows}, ready

def baseline(archive, history, year, target_date):
    records = {}
    # Current season rebuilt WITHOUT final. Its archive entry could already include final.
    for k, seasons in archive.items():
        if not k.endswith('-H'): continue
        values = [v['t'] for y, v in seasons.items() if int(y) < year]
        if values: records[k] = min(values)
    for m in history:
        if m['meeting'].get('season') != 'Indoor': continue
        y = int(m['meeting']['startDateTime'][:4])
        if y != year or m['meeting']['startDateTime'][:10] >= target_date: continue
        for r in m['rows']:
            if valid(r, y):
                k, t = category(r, y), round(r['result']/100)
                records[k] = min(records.get(k, t), t)
    return records

def podiums(history, live, ready):
    year = int(live['meeting']['startDateTime'][:4]); mid = live['meeting']['meetingId']
    all_rounds = [m for m in history if int(m['meeting']['startDateTime'][:4]) == year and m['meeting']['startDateTime'] < live['meeting']['startDateTime'] and m['meeting']['meetingId'] != mid] + [live]
    results, people = collections.defaultdict(dict), {}
    for i, m in enumerate(all_rounds):
        best = {}
        for r in m['rows']:
            if valid(r, year):
                k = category(r, year); aid = r['athleteId']; t = round(r['result']/100)
                best[k, aid] = min(best.get((k, aid), t), t); people[k, aid] = r
        for (k, aid), t in best.items():
            times = [v for (kk, _), v in best.items() if kk == k]
            results[k].setdefault(aid, []).append((1+sum(v<t for v in times), t))
    out = {}
    for k in ready:
        ranked = []
        for aid, starts in results[k].items():
            if len(starts) >= 7:
                r = people[k, aid]
                ranked.append((sum(p for p, _ in sorted(starts)[:7]), min(t for _, t in starts), str(aid), r['name'], r['club']))
        ranked.sort()
        lines = []
        for i, r in enumerate(ranked[:3], 1):
            lines.append(f'{i}. {r[3]} — {r[4] or "bez klubu"} — {r[0]} pkt')
        ties = any(a[:2] == b[:2] for a, b in zip(ranked[:3], ranked[1:4]))
        out[k] = '🏅 KLASYFIKACJA CYKLU\n' + title(k, year) + '\n' + ('\n'.join(lines) or 'Brak zawodników z wymaganymi 7 startami.') + ('\n⚠️ Nierozstrzygnięty remis — kolejność wymaga decyzji organizatora.' if ties else '') + '\nPo zakończeniu konkurencji w Roster; 7 najlepszych rund.'
    return out

def notifications(state, live, ready, history, base):
    year = int(live['meeting']['startDateTime'][:4]); changes = []
    current = {}
    for r in live['rows']:
        if valid(r, year):
            k = category(r, year); t = round(r['result']/100)
            ident = f"{k}:{r['athleteId']}"
            if ident not in current or t < current[ident][0]: current[ident] = (t, r, k)
    # Keep per-athlete alerts so a later faster athlete does not retract an earlier record.
    thresholds = dict(base)
    for ident, old in state.get('records', {}).items():
        if ident in current:
            t, r, k = current[ident]
            if old['threshold'] is None or t <= old['threshold']:
                thresholds[k] = min(thresholds.get(k, t), t)
    for ident, (t, r, k) in sorted(current.items(), key=lambda x: -x[1][0]):
        old = state.get('records', {}).get(ident)
        threshold = old['threshold'] if old else thresholds.get(k)
        if threshold is not None and t > threshold: continue
        body = ('🏆 REKORD WLB — HALA' if threshold is None or t < threshold else '🏆 WYRÓWNANY REKORD WLB — HALA') + '\n' + title(k, year) + f"\n{r['name']} — {r['club']}\nWynik: {seconds(t)}" + (f'\nPoprzedni rekord: {seconds(threshold)}' if threshold is not None else '\nPierwszy wynik w bazie rekordów.') + '\nWynik z Roster — do zatwierdzenia przez obsługę.'
        payload = {'t': t, 'threshold': threshold, 'body': body}
        if old != payload: changes.append(('records', ident, payload, ('KOREKTA\n' if old else '')+body))
        thresholds[k] = min(thresholds.get(k, t), t)
    active = {ident for _, ident, _, _ in changes} | {i for i,(t,r,k) in current.items() if i in state.get('records',{}) and (state['records'][i]['threshold'] is None or t <= state['records'][i]['threshold'])}
    for ident, old in state.get('records', {}).items():
        if ident not in active:
            changes.append(('records', ident, None, '⚠️ KOREKTA: wcześniejszy alert rekordowy jest nieaktualny (zmiana/usunięcie wyniku).\n'+old['body']))
    pods = podiums(history, live, ready)
    for k, body in pods.items():
        old = state.get('podiums', {}).get(k)
        if old != body: changes.append(('podiums', k, body, ('KOREKTA PODIUM\n' if old else '')+body))
    for k in state.get('podiums', {}):
        if k not in ready: changes.append(('podiums', k, None, '⚠️ Konkurencja ponownie otwarta — podium wymaga ponownego zatwierdzenia.\n'+title(k,year)))
    return changes, thresholds

def send(config, body):
    url = 'https://api.telegram.org/bot'+config['telegram_token']+'/sendMessage'
    request = urllib.request.Request(url, data=json.dumps({'chat_id': config['chat_id'], 'text': body}).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if not json.load(response).get('ok'): raise RuntimeError('Telegram odrzucił wiadomość')

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--config', required=True); parser.add_argument('--once', action='store_true'); parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(); config = json.loads(Path(args.config).read_text())
    root = Path(config['data_dir']); root.mkdir(parents=True, exist_ok=True)
    lock = (root/'monitor.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    state_path = root/('dry-state.json' if args.dry_run else 'state.json')
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    date = config['date']; year = int(date[:4])
    if state and state.get('date') != date: raise ValueError('Stan pochodzi z innych zawodów')
    state['date'] = date
    history = [m for p in (root/'raw').glob('*.json') if (m := json.loads(p.read_text()))['rows'] and m['meeting'].get('meetingStatus') != 'Cancelled']
    archive = json.loads((root/'records-archiwum.json').read_text())
    earlier = [m for m in history if m['meeting']['startDateTime'][:4] == str(year) and m['meeting']['startDateTime'][:10] < date]
    if len(earlier) != config.get('expected_prior_rounds', 9):
        raise ValueError('Niepełne dane wcześniejszych rund; nie można liczyć podium')
    base = baseline(archive, history, year, date)
    meeting = None
    while True:
        delay = config.get('interval', 30)
        try:
            now = datetime.now(ZoneInfo('Europe/Warsaw'))
            if not args.dry_run and now.strftime('%Y-%m-%d') < date:
                logging.info('Czekam na finał %s', date); delay = 3600
            elif not args.dry_run and now.strftime('%Y-%m-%d') > config.get('end_date', date):
                logging.info('Okno monitorowania zakończone'); return
            else:
                if meeting is None:
                    candidates = [m for m in list_meetings() if m['startDateTime'][:10] == date and m.get('meetingStatus') != 'Cancelled']
                    if len(candidates) != 1: raise ValueError('Brak jednoznacznej rundy finałowej w Roster')
                    meeting = candidates[0]
                live, ready = snapshot(meeting)
                changes, thresholds = notifications(state, live, ready, history, base)
                for group, key, value, body in changes:
                    if args.dry_run: print(body+'\n', flush=True)
                    else: send(config, body)
                    bucket = state.setdefault(group, {})
                    if value is None: bucket.pop(key, None)
                    else: bucket[key] = value
                    atomic(state_path, state)
                    if not args.dry_run: time.sleep(1.1)
                state['thresholds'] = thresholds; state['last_ok'] = now.isoformat(); atomic(state_path,state)
                logging.info('Odczyt OK; gotowe kategorie: %d; alerty: %d',len(ready),len(changes))
        except Exception as exc:
            # Never print exception text: urllib errors may expose token URLs.
            logging.error('Odczyt/wysyłka nieudane (%s); ponowię', type(exc).__name__)
            delay = max(60, delay)
            if args.once: raise SystemExit(1)
        if args.once: return
        time.sleep(delay)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s'); main()
