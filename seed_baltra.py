#!/usr/bin/env python3
"""
Seed script — creates the Baltra_auto project from the ADM schedule JSON.

Usage (server must be running on localhost:5000):
    python3 seed_baltra.py
    python3 seed_baltra.py --json data/adm-schedule-2026-04-21.json
"""
import json, sys, requests
from datetime import date

BASE  = "http://localhost:5000"
TODAY = date.today()

JSON_PATH = sys.argv[sys.argv.index('--json') + 1] \
    if '--json' in sys.argv else 'data/adm-schedule-2026-04-21.json'

TEAM_COLORS = {
    'SIML LITE':        '#0a84ff',
    'MetalLM Sharding': '#ff9f0a',
    'ANEC Compiler':    '#af52de',
    'Polymer Runtime':  '#34c759',
    'MetalLM Runtime':  '#00c7be',
    'TIE':              '#ff375f',
    'Integration':      '#8e8e93',
}
ACH_COLOR = '#636366'


def d(ds):
    """'M/D/YY' → 'YYYY-MM-DD'"""
    if not ds:
        return ''
    p = ds.strip().split('/')
    return f"20{int(p[2]):02d}-{int(p[0]):02d}-{int(p[1]):02d}"


def status(s, e):
    if not s or not e:
        return 'Not Started'
    try:
        sd, ed = date.fromisoformat(s), date.fromisoformat(e)
        if ed < TODAY:  return 'Complete'
        if sd <= TODAY: return 'In Progress'
    except Exception:
        pass
    return 'Not Started'


def post(url, payload):
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def put(tid, payload):
    r = requests.put(f"{BASE}/api/tasks/{tid}", json=payload)
    r.raise_for_status()


def make_task(pid, name, owner, s, e, priority, notes='',
              parent=None, color=None, milestone=False):
    sd, ed = d(s), d(e)
    payload = dict(name=name, owner=owner, start_date=sd, end_date=ed,
                   status=status(sd, ed), priority=priority, notes=notes)
    if parent:
        payload['parent_id'] = parent
    r = post(f"{BASE}/api/projects/{pid}/tasks", payload)
    tid = r['id']
    patch = {}
    if color:     patch['color'] = color
    if milestone: patch['is_milestone'] = 1
    if patch:
        put(tid, patch)
    return tid


# ── Load JSON ──────────────────────────────────────────────────────────────────
print(f"Loading {JSON_PATH} ...")
with open(JSON_PATH) as f:
    data = json.load(f)

achievements = data['data']
milestones   = data['ms']
model_drops  = data.get('modelDrops', [])

# ── Create project ─────────────────────────────────────────────────────────────
r = post(f"{BASE}/api/projects", {"name": "Baltra_auto"})
pid = r['id']
print(f"✓ Created Baltra_auto  pid={pid}")

# ── Program milestones ─────────────────────────────────────────────────────────
ms_func = make_task(pid, "ADM Functional ◆", "Program",
    "9/1/26", "9/1/26", "Critical",
    notes="ADM Functional milestone — Device to Server SW ready for carry",
    color="#ff9f0a", milestone=True)
print(f"  ◆ ADM Functional: {ms_func}")

ms_perf = make_task(pid, "ADM Performant ◆", "Program",
    "10/1/26", "10/1/26", "Critical",
    notes="ADM Performant milestone — Meet performance targets",
    color="#5856d6", milestone=True)
print(f"  ◆ ADM Performant: {ms_perf}")

# ── Model drops ────────────────────────────────────────────────────────────────
for md in model_drops:
    tid = make_task(pid, f"Model Drop: {md['l']}", md.get('team', 'SIML LITE'),
        md['d'], md['d'], "High",
        notes=f"Model drop — {md['l']}",
        color=TEAM_COLORS.get(md.get('team', 'SIML LITE'), '#0a84ff'),
        milestone=True)
    print(f"  ◆ Model Drop: {md['l']}  tid={tid}")

# ── Achievements ───────────────────────────────────────────────────────────────
ach_tid = {}

for ach in achievements:
    all_starts = [t['s'] for t in ach.get('teams', []) if t.get('s')]
    all_ends   = [t['e'] for t in ach.get('teams', []) if t.get('e')]
    ps = min(all_starts, key=lambda x: d(x)) if all_starts else ''
    pe = max(all_ends,   key=lambda x: d(x)) if all_ends   else ''

    priority = 'Critical' if ach.get('cat') == 'func' else 'High'
    ach_name = f"Ach {ach['id']} — {ach['name']}"

    parent_tid = make_task(pid, ach_name, "Multi-team",
        ps, pe, priority, notes=ach.get('notes', ''), color=ACH_COLOR)
    ach_tid[ach['id']] = parent_tid
    print(f"  Ach {ach['id']}: {parent_tid}")

    for team in ach.get('teams', []):
        team_name  = team['t']
        team_color = TEAM_COLORS.get(team_name, '#8e8e93')
        team_note  = team.get('note', '')
        if team.get('hc'):
            team_note += f" | HC: {team['hc']}"

        team_tid = make_task(pid,
            name=f"{team_name} — {team_note[:60]}" if team_note else team_name,
            owner=team_name, s=team['s'], e=team['e'],
            priority="Normal", notes=team_note,
            parent=parent_tid, color=team_color)

        for sub in team.get('subtasks', []):
            make_task(pid, name=sub['n'], owner=team_name,
                s=sub['s'], e=sub['e'], priority="Normal",
                parent=team_tid, color=team_color)

# ── Wire dependencies ──────────────────────────────────────────────────────────
print("\n  Wiring dependencies...")
for ach in achievements:
    deps = ach.get('deps', [])
    if deps:
        dep_str = ','.join(f"{ach_tid[dep_id]}FS"
                           for dep_id in deps if dep_id in ach_tid)
        if dep_str:
            put(ach_tid[ach['id']], {'depends_on': dep_str})
            print(f"    Ach {ach['id']} ← {', '.join(f'Ach {x}' for x in deps)}")

print(f"\n✅  Done — {pid=}")
print(f"    Open: http://localhost:5000/#{pid}")
print(f"    Recommended view: Gantt → Quarter zoom → Sprint Cadence ON")
