from uagents import Agent, Context, Model
import datetime

# ---------- Nachrichtenmodell ----------
class HaustierMessage(Model):
    message: str
    zeit: str = None          # Uhrzeit der Anfrage / Check-In
    betreuung_von: str = None # Startzeit der Betreuung
    betreuung_bis: str = None # Endzeit der Betreuung

class Message(Model):
    message: str
    zeit: str = None

# ---------- Kapazitäten ----------
MAX_HUNDE = 10
MAX_KATZEN = 20

tiere_status = {
    "hunde": MAX_HUNDE,
    "katzen": MAX_KATZEN
}

# ---------- Öffnungszeiten ----------
BUCHUNG_BIS = datetime.time(18, 0)   # Buchung nur bis 18:00 Uhr
CHECKIN_BIS = datetime.time(22, 0)   # Check-In bis 22:00 Uhr

# ---------- Haustier-Agent ----------
petHotelAgent = Agent(
    name="Haustierbetreuung",
    port=8020,
    seed="petHotelAgent",
    endpoint=["http://localhost:8020/submit"],
)

print("\n🐾 Haustierbetreuung-Service gestartet!")
print(f"Adresse: {petHotelAgent.address}")
print(f"Kapazitäten: 🐶 Hunde: {MAX_HUNDE}, 🐱 Katzen: {MAX_KATZEN}\n")

# ---------- Handler ----------
@petHotelAgent.on_message(model=HaustierMessage)  # Eingehend spezialisierte Nachricht
async def handler(ctx: Context, sender: str, msg: HaustierMessage):

    text = msg.message.lower()

    # Uhrzeit prüfen
    try:
        jetzt = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        await ctx.send(sender, Message(
            message="❌ Ungültige Zeit. Bitte HH:MM angeben.",
            zeit=msg.zeit
        ))
        return

    # Betreuungszeiten prüfen
    try:
        start = datetime.datetime.strptime(msg.betreuung_von, "%H:%M").time()
        ende = datetime.datetime.strptime(msg.betreuung_bis, "%H:%M").time()
    except:
        await ctx.send(sender, Message(
            message="❌ Bitte Zeitraum als HH:MM senden (betreuung_von / betreuung_bis).",
            zeit=msg.zeit
        ))
        return

    # Buchungsschluss prüfen
    if jetzt > BUCHUNG_BIS:
        antwort = (
            f"❌ Buchungen sind nur bis 18:00 möglich.\n"
            f"Aktuelle Zeit: {msg.zeit}\n"
            f"Check-In möglich bis 22:00 Uhr."
        )
        await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
        return

    # Übernacht-Betreuung erkennen
    ueber_nacht = ende < start

    # Hundebuchung
    if "hund" in text:
        if tiere_status["hunde"] > 0:
            tiere_status["hunde"] -= 1
            antwort = (
                f"🐶 Hundebetreuung reserviert!\n"
                f"⏱️ Zeitraum: {msg.betreuung_von} – {msg.betreuung_bis}"
                + (" (über Nacht)" if ueber_nacht else "") +
                f"\nCheck-In bis {CHECKIN_BIS.strftime('%H:%M')} möglich."
            )
        else:
            antwort = "❌ Keine Hundeplätze mehr verfügbar."

    # Katzenbuchung
    elif "katze" in text:
        if tiere_status["katzen"] > 0:
            tiere_status["katzen"] -= 1
            antwort = (
                f"🐱 Katzenbetreuung reserviert!\n"
                f"⏱️ Zeitraum: {msg.betreuung_von} – {msg.betreuung_bis}"
                + (" (über Nacht)" if ueber_nacht else "") +
                f"\nCheck-In bis {CHECKIN_BIS.strftime('%H:%M')} möglich."
            )
        else:
            antwort = "❌ Keine Katzenplätze mehr verfügbar."

    else:
        antwort = "❌ Bitte angeben, ob Hund oder Katze."

    # Antwort an Sender als Standard-Message
    await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))

    # Logging
    ctx.logger.info(
        f"Hunde frei={tiere_status['hunde']} | Katzen frei={tiere_status['katzen']}"
    )

# ---------- Agent starten ----------
if __name__ == "__main__":
    petHotelAgent.run()
