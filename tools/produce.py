"""Calendar and budget helper for the /produce skill (stdlib only).
  produce.py show <day|date|next>      the items of that day and their status
  produce.py next                      the next item that is not made
  produce.py item <id>                 one item as JSON (D05-S1, D07-L, B03, R03 ...)
  produce.py budget                    ElevenLabs characters used / left this month, and what still fits
  produce.py done <id> <path> <chars>  mark an item made (path under finished/), with the characters spent
  produce.py swap <id> <B##|R##>    replace an item whose research failed with a backlog (B##) or reserve (R##) topic
  produce.py status                    counts per day
"""
import json, sys, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
CAL, ST = ROOT / "calendar" / "calendar.json", ROOT / "calendar" / "status.json"
cal = json.loads(CAL.read_text(encoding="utf-8")); status = json.loads(ST.read_text(encoding="utf-8")) if ST.exists() else {}
items = {i["id"]: i for d in cal["days"] for i in d["items"]}; items.update({r["id"]: r for r in cal["reserve"] + cal.get("backlog", [])})
def st(i): return status.get(i["id"], {}).get("status", i["status"] if i["status"] != "made" else "made")
def save(): ST.write_text(json.dumps(status, indent=1, ensure_ascii=False), encoding="utf-8"); print("saved")
def day_of(a):
    if a == "next":
        for d in cal["days"]:
            if any(st(i) not in ("made", "skipped") for i in d["items"]): return d
        return None
    if "-" in a: return next((d for d in cal["days"] if d["date"] == a), None)
    return next((d for d in cal["days"] if d["day"] == int(a)), None)
def show(d):
    print(f"Day {d['day']:02d} {d['weekday']} {d['date']}: {d['theme']}")
    for i in d["items"]: print(f"  {i['id']:7} {st(i):7} {'LONG ' if i['kind'] == 'long' else 'short'} {'WhatIf' if i['format'] == 'whatif' else 'Odd   '}  {i['title']}\n          idea: {i['rule'] or '-'}" + (f"\n          RISK: {i['risk']}" if i['risk'] else ""))
def budget():
    cfg = json.loads((ROOT / "tools" / "eleven_config.json").read_text(encoding="utf-8")); month = datetime.date.today().strftime("%Y-%m")
    led = json.loads((ROOT / "eleven_usage.json").read_text()) if (ROOT / "eleven_usage.json").exists() else {"calls": []}
    used = sum(c["chars"] for c in led["calls"] if c["date"].startswith(month)); left = cfg["monthly_char_budget"] - used
    print(f"ElevenLabs {month}: {used} of {cfg['monthly_char_budget']} characters used, {left} left")
    print(f"A long video needs about 1,600 characters, a Short about 700, a Sunday (long + Short) about 2,250. Still fits: {left // 1600} long videos, or {left // 700} Shorts, or {left // 2250} Sundays.")
a = sys.argv[1:] or ["status"]
if a[0] == "show": d = day_of(a[1]); show(d) if d else print("no such day (or nothing left)")
elif a[0] == "next": d = day_of("next"); show(d) if d else print("everything is made")
elif a[0] == "item": print(json.dumps({**items[a[1]], "status": st(items[a[1]])}, indent=1, ensure_ascii=False))
elif a[0] == "budget": budget()
elif a[0] == "done": status[a[1]] = {"status": "made", "path": a[2], "chars": int(a[3]) if len(a) > 3 else 0, "date": datetime.date.today().isoformat()}; save()
elif a[0] == "swap":
    old, new = a[1], a[2]; cal_i = next(i for d in cal["days"] for i in d["items"] if i["id"] == old); r = items[new]
    for k in ("kind_keep",): pass
    cal_i.update({"format": r["format"], "title": r["title"], "rule": r["rule"], "risk": r["risk"], "family": r.get("family", ""), "slug": r["slug"]}); status[new] = {"status": "skipped", "note": f"used for {old}"}; CAL.write_text(json.dumps(cal, indent=1, ensure_ascii=False), encoding="utf-8"); save()
else:
    for d in cal["days"]: n = sum(st(i) == "made" for i in d["items"]); print(f"Day {d['day']:02d} {d['date']} {n}/{len(d['items'])} made  {d['theme']}")
