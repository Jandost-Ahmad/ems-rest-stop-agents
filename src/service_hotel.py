from uagents import Agent, Context, Model
import datetime

# ---------- Input-Modell ----------
class HotelMessage(Model):
    type: str = "hotel"          # Für Routing im CentralService
    zimmerart: str               # Anfrage: „Einzelzimmer“, „Doppelzimmer“…
    zeit: str                    # Uhrzeit der Anfrage
    naechte: int = 1             # Anzahl der Nächte
    client_sender: str           # Wohin die Antwort gehen soll

# ---------- Output-Modell ----------
class Message(Model):
    type: str                    # z.B. "hotel_bestaetigung"
    message: str
    zeit: str = None

# ---------- Hotel-Agent ----------
hotelAgent = Agent(
    name="HotelService",
    port=8004,
    seed="hotelServiceAgent",
    endpoint=["http://localhost:8004/submit"],
)

zimmer = {
    "einzel": 20,
    "doppel": 10,
    "familie": 5
}

print("🏨 Hotel-Service gestartet")

# ---------- Nachricht empfangen ----------
@hotelAgent.on_message(model=HotelMessage)
async def hotel_handler(ctx: Context, sender: str, msg: HotelMessage):
    client = msg.client_sender or sender

    # Zeit prüfen
    try:
        anfrage_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        antwort_text = "❌ Ungültige Zeit. Bitte im Format HH:MM senden."
        await ctx.send(client, Message(type="hotel_fehler", message=antwort_text, zeit=msg.zeit))
        return

    antwort_text = "❌ Kein geeignetes Zimmer verfügbar."

    zimmerart_lower = msg.zimmerart.lower()
    if "einzel" in zimmerart_lower and zimmer["einzel"] > 0:
        zimmer["einzel"] -= 1
        antwort_text = f"🏨 Einzelzimmer gebucht für {msg.naechte} Nacht/Nächte."
    elif "doppel" in zimmerart_lower and zimmer["doppel"] > 0:
        zimmer["doppel"] -= 1
        antwort_text = f"🏨 Doppelzimmer gebucht für {msg.naechte} Nacht/Nächte."
    elif ("familie" in zimmerart_lower or "familien" in zimmerart_lower) and zimmer["familie"] > 0:
        zimmer["familie"] -= 1
        antwort_text = f"🏨 Familienzimmer gebucht für {msg.naechte} Nacht/Nächte."

    # Antwort an den Client senden
    await ctx.send(client, Message(type="hotel_bestaetigung", message=antwort_text, zeit=msg.zeit))
    ctx.logger.info(f"Antwort an {client} gesendet. Zimmerstatus: {zimmer}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    hotelAgent.run()
