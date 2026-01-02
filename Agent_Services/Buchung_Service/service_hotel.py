from uagents import Agent, Context, Model
import datetime


# ---------- Hotel-Input Modell ----------
class HotelMessage(Model):
    type: str
    zimmerart: str
    zeit: str
    naechte: int
    client_sender: str


# ---------- Antwortmodell ----------
class Message(Model):
    type: str
    message: str
    zeit: str


# ---------- Hotel-Agent ----------
hotelAgent = Agent(
    name="HotelService",
    port=8009,
    seed="hotelServiceAgent",
    endpoint=["http://localhost:8009/submit"],
)

zimmer = {
    "einzel": 20,
    "doppel": 10,
    "familie": 5
}


@hotelAgent.on_message(model=HotelMessage)
async def hotel_handler(ctx: Context, sender: str, msg: HotelMessage):
    # msg IST bereits ein HotelMessage → KEIN dict!
    hotel_msg = msg

    client = hotel_msg.client_sender or sender

    # Zeit prüfen
    try:
        datetime.datetime.strptime(hotel_msg.zeit, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="hotel_fehler",
                message="❌ Ungültige Zeit. Bitte HH:MM.",
                zeit=hotel_msg.zeit
            )
        )
        return

    antwort_text = "❌ Kein geeignetes Zimmer verfügbar."

    z = hotel_msg.zimmerart.lower()

    if "einzel" in z and zimmer["einzel"] > 0:
        zimmer["einzel"] -= 1
        antwort_text = f"🏨 Einzelzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    elif "doppel" in z and zimmer["doppel"] > 0:
        zimmer["doppel"] -= 1
        antwort_text = f"🏨 Doppelzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    elif ("familie" in z or "familien" in z) and zimmer["familie"] > 0:
        zimmer["familie"] -= 1
        antwort_text = f"🏨 Familienzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    # Antwort senden
    await ctx.send(
        client,
        Message(
            type="hotel_bestaetigung",
            message=antwort_text,
            zeit=hotel_msg.zeit
        )
    )

    ctx.logger.info(f"Antwort an {client} gesendet. Zimmerstatus: {zimmer}")


if __name__ == "__main__":
    print("🏨 Hotel-Service gestartet…")
    print(f"📍 Adresse: {hotelAgent.address}")
    hotelAgent.run()
