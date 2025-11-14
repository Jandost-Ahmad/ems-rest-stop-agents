from uagents import Agent, Context, Model
import datetime

# ---------- Nachrichtenmodell ----------
class HotelMessage(Model):
    message: str
    zeit: str = None
    naechte: int = 1  # Anzahl der Nächte

# ---------- Hotel-Agent ----------
hotelAgent = Agent(
    name="HotelService",
    port=8005,
    seed="hotelServiceAgent",
    endpoint=["http://localhost:8005/submit"],
)

zimmer = {
    "einzel": 20,
    "doppel": 10,
    "familie": 5
}

BUCHUNGSSCHLUSS = datetime.time(18, 0)
CHECKIN_SCHLUSS = datetime.time(22, 0)

print("🏨 Hotel-Service gestartet")

# ---------- Nachricht empfangen ----------
@hotelAgent.on_message(model=HotelMessage)  # <- jetzt auf HotelMessage hören
async def hotel_handler(ctx: Context, sender: str, msg: HotelMessage):

    try:
        anfrage_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        antwort = "❌ Ungültige Zeit. Bitte im Format HH:MM senden."
        await ctx.send(sender, HotelMessage(message=antwort))
        return

    text = msg.message.lower()
    antwort = "❌ Kein geeignetes Zimmer verfügbar."

    if "einzel" in text and zimmer["einzel"] > 0:
        zimmer["einzel"] -= 1
        antwort = f"🏨 Einzelzimmer gebucht für {msg.naechte} Nacht/Nächte."
    elif "doppel" in text and zimmer["doppel"] > 0:
        zimmer["doppel"] -= 1
        antwort = f"🏨 Doppelzimmer gebucht für {msg.naechte} Nacht/Nächte."
    elif ("familie" in text or "familien") and zimmer["familie"] > 0:
        zimmer["familie"] -= 1
        antwort = f"🏨 Familienzimmer gebucht für {msg.naechte} Nacht/Nächte."

    await ctx.send(sender, HotelMessage(message=antwort, zeit=msg.zeit, naechte=msg.naechte))

    ctx.logger.info(f"Zimmerstatus: {zimmer}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    hotelAgent.run()
