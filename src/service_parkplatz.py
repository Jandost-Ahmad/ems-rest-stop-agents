from uagents import Agent, Context, Model
import uuid
from datetime import datetime, timedelta
import re

# ---------- Input-Modell ----------
class ParkplatzMessage(Model):
    type: str = "parkplatz"
    fahrzeugart: str        # PKW, PKW_Behindert, LKW, BUS, …
    ladestation: bool       # True / False
    zeit: str               # HH:MM oder Minuten
    reservation_id: str
    client_sender: str

# ---------- Output-Modell ----------
class Message(Model):
    type: str               # z.B. "parkplatz_reservierung"
    message: str
    zeit: str = None

# ---------- Parkplatz-Konfiguration ----------
pkw_total = 100
pkw_lade_total = 50
lkw_total = 300
bus_total = 3

def two_percent(x):
    return max(1, round(x * 0.02))

behindert_pkw_ohne_lade = two_percent(pkw_total)
behindert_pkw_mit_lade = two_percent(pkw_total)
behindert_lkw_mit_lade = two_percent(lkw_total)

pkw_rest = pkw_total - behindert_pkw_ohne_lade - behindert_pkw_mit_lade
pkw_lade = min(pkw_lade_total, pkw_rest)
pkw_frei = pkw_rest - pkw_lade

lkw_lade = lkw_total - behindert_lkw_mit_lade
bus_lade = bus_total

parkplatz_status = {
    "PKW": {"frei": pkw_frei, "lade": pkw_lade},
    "PKW_Behindert": {"frei": behindert_pkw_ohne_lade, "lade": behindert_pkw_mit_lade},
    "LKW": {"lade": lkw_lade},
    "LKW_Behindert": {"lade": behindert_lkw_mit_lade},
    "BUS": {"lade": bus_lade}
}

# ---------- Agent ----------
parkplatzAgent = Agent(
    name="ParkplatzAgent",
    port=8001,
    seed="parkplatzAgent",
    endpoint=["http://localhost:8001/submit"],
)

print("\nParkplatz-Agent gestartet:")
for k, v in parkplatz_status.items():
    print(f"{k}: {v}")

# ---------- Reservierungen ----------
reservations = {}

# ---------- Helper ----------
def parse_time_field(zeit_str: str):
    if not zeit_str:
        return None
    zeit_str = zeit_str.strip()
    hhmm = re.match(r"^(\d{1,2}):(\d{2})$", zeit_str)
    if hhmm:
        h, m = int(hhmm.group(1)), int(hhmm.group(2))
        now = datetime.now()
        end = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if end <= now:
            end += timedelta(days=1)
        return end
    if zeit_str.isdigit():
        return datetime.now() + timedelta(minutes=int(zeit_str))
    return None

def total_pkw_available():
    return parkplatz_status["PKW"]["frei"] + parkplatz_status["PKW"]["lade"]

def consume_pkw_slots(n: int):
    consumed = 0
    take = min(n, parkplatz_status["PKW"]["frei"])
    parkplatz_status["PKW"]["frei"] -= take
    consumed += take
    rest = n - consumed
    if rest > 0:
        take2 = min(rest, parkplatz_status["PKW"]["lade"])
        parkplatz_status["PKW"]["lade"] -= take2
        consumed += take2
    return consumed

def try_allocate_lkw():
    if parkplatz_status["LKW"]["lade"] > 0:
        parkplatz_status["LKW"]["lade"] -= 1
        return True, "🚚🔌 LKW-Ladeparkplatz reserviert."
    if parkplatz_status.get("BUS", {}).get("lade", 0) > 0:
        parkplatz_status["BUS"]["lade"] -= 1
        return True, "🚚 (Fallback) Bus-Parkplatz für LKW reserviert."
    if total_pkw_available() >= 3 and consume_pkw_slots(3) == 3:
        return True, "🚚 (Fallback) 3× PKW → LKW-Platz reserviert."
    return False, None

# ---------- Handler ----------
@parkplatzAgent.on_message(model=ParkplatzMessage)
async def message_handler(ctx: Context, sender: str, msg: ParkplatzMessage):
    fahrzeugart = msg.fahrzeugart.lower()
    lade = bool(msg.ladestation)
    client = msg.client_sender or sender
    antwort = "❌ Kein geeigneter Parkplatz verfügbar."
    rid = None

    # ---- Fahrzeuglogik ----
    if "pkw" in fahrzeugart and "behindert" in fahrzeugart:
        if lade and parkplatz_status["PKW_Behindert"]["lade"] > 0:
            parkplatz_status["PKW_Behindert"]["lade"] -= 1
            antwort = "♿🔌 Behinderten-PKW-Ladeparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]
        elif not lade and parkplatz_status["PKW_Behindert"]["frei"] > 0:
            parkplatz_status["PKW_Behindert"]["frei"] -= 1
            antwort = "♿ PKW-Behindertenparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]
        elif total_pkw_available() >= 2 and consume_pkw_slots(2) == 2:
            antwort = "♿ (Fallback) 2× PKW → Behindertenplatz reserviert."
            rid = str(uuid.uuid4())[:8]

    elif "pkw" in fahrzeugart:
        if lade and parkplatz_status["PKW"]["lade"] > 0:
            parkplatz_status["PKW"]["lade"] -= 1
            antwort = "🔌🚗 PKW-Ladeparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]
        elif not lade and parkplatz_status["PKW"]["frei"] > 0:
            parkplatz_status["PKW"]["frei"] -= 1
            antwort = "🚗 PKW-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

    elif "lkw" in fahrzeugart and "behindert" in fahrzeugart:
        if parkplatz_status["LKW_Behindert"]["lade"] > 0:
            parkplatz_status["LKW_Behindert"]["lade"] -= 1
            antwort = "♿🚚🔌 Behinderten-LKW-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]
        else:
            ok, msg2 = try_allocate_lkw()
            if ok:
                antwort = "♿🚚 (Fallback) " + msg2
                rid = str(uuid.uuid4())[:8]

    elif "lkw" in fahrzeugart:
        ok, msg2 = try_allocate_lkw()
        if ok:
            antwort = msg2
            rid = str(uuid.uuid4())[:8]

    elif "bus" in fahrzeugart:
        if parkplatz_status["BUS"]["lade"] > 0:
            parkplatz_status["BUS"]["lade"] -= 1
            antwort = "🚌🔌 Bus-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

    # ---- Antwort an Client senden ----
    await ctx.send(
        client,
        Message(
            type="parkplatz_reservierung",
            message=antwort + (f" (RID={rid})" if rid else ""),
            zeit=msg.zeit
        )
    )

    # ---- Reservierung speichern ----
    if rid:
        end_dt = parse_time_field(msg.zeit) or (datetime.now() + timedelta(minutes=60))
        reservations[rid] = {
            "sender": client,
            "end": end_dt,
            "reminder_sent": False
        }

# ---------- Reminder & Expire ----------
@parkplatzAgent.on_interval(period=30.0)
async def reservation_maintenance(ctx: Context):
    REMINDER_MINUTES = 5
    now = datetime.now()
    expired = []

    for rid, r in reservations.items():
        end = r["end"]

        if not r["reminder_sent"] and now + timedelta(minutes=REMINDER_MINUTES) >= end > now:
            await ctx.send(
                r["sender"],
                Message(type="parkplatz_reminder", message=f"⏰ Ihre Reservierung {rid} läuft um {end.strftime('%H:%M')} ab.")
            )
            r["reminder_sent"] = True

        if now >= end:
            expired.append(rid)

    for rid in expired:
        data = reservations.pop(rid)
        await ctx.send(
            data["sender"],
            Message(type="parkplatz_abgelaufen", message=f"❗ Ihre Reservierung {rid} ist abgelaufen und wurde freigegeben.")
        )

# ---------- Agent starten ----------
if __name__ == "__main__":
    parkplatzAgent.run()
