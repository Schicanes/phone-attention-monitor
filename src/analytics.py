from datetime import datetime, timedelta, timezone


def summary(db, days=1):
    local_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    since = (local_start - timedelta(days=days-1)).astimezone(timezone.utc).isoformat()
    events = db.rows("SELECT state,SUM(duration) AS seconds FROM attention_events WHERE timestamp>=? GROUP BY state", (since,))
    durations = {row["state"]: row["seconds"] for row in events}
    sessions = db.rows("SELECT * FROM sessions WHERE started>=?", (since,))
    pickups = sum(row["pickups"] for row in sessions)
    elapsed = sum(durations.values())
    phone = durations.get("PHONE_USE", 0) + durations.get("PHONE_GLANCE", 0)
    return dict(focus=durations.get("FOCUSED", 0), phone=phone, pickups=pickups,
                warnings=len(db.rows("SELECT id FROM interventions WHERE timestamp>=?", (since,))),
                longest=max((row["longest_focus"] for row in sessions), default=0),
                per_hour=pickups*3600/elapsed if elapsed else 0,
                average_phone=phone/pickups if pickups else 0)


def personalization(db):
    responses = db.rows("SELECT type,AVG(response_time) AS average FROM interventions WHERE response_time IS NOT NULL GROUP BY type")
    totals = db.rows("SELECT AVG(phone / NULLIF(pickups,0)) AS phone, AVG(focus / (pickups+1)) AS focus, SUM(pickups)*3600.0/NULLIF(SUM(elapsed),0) AS rate FROM sessions")[0]
    hour = db.rows("SELECT strftime('%H',timestamp,'localtime') AS hour,SUM(duration) AS total FROM attention_events WHERE state IN ('PHONE_USE','PHONE_GLANCE') GROUP BY hour ORDER BY total DESC LIMIT 1")
    return {"average_focus_block_estimate": totals["focus"], "average_phone_session": totals["phone"],
            "phone_pickups_per_hour": totals["rate"], "most_distracted_hour": hour[0]["hour"] if hour else None,
            "response_seconds": {row["type"]: row["average"] for row in responses}}
