from uagents import Agent, Context, Model
import datetime


# ---------- Input-Modell ----------
class HaustierMessage(Model):
    type: str
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str


# ---------- Output-Modell ----------
class Message(Model):
    type: str
    message: str
    zeit: str


# ---------- Haustier-Agent ----------
petHotelAgent = Agent(
    name="Haustierbetreuung",
    port=8005,
    seed="petHotelAgent",
    endpoint=["http://localhost:8005/submit"],
)

# Kapazitäten
kapazitaet = {
    "hund": 10,
    "katze": 20
}


@petHotelAgent.on_message(model=HaustierMessage)
async def handler(ctx: Context, sender: str, msg: HaustierMessage):

    client = msg.client_sender or sender

    # Zeit prüfen (HH:MM)
    try:
        datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="haustier_fehler",
                message="❌ Ungültige Zeit. Bitte HH:MM.",
                zeit=msg.zeit
            )
        )
        return

    # Betreuungs-Zeiten prüfen
    try:
        start = datetime.datetime.strptime(msg.betreuung_von, "%H:%M").time()
        ende = datetime.datetime.strptime(msg.betreuung_bis, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="haustier_fehler",
                message="❌ betreuung_von/bis müssen HH:MM sein.",
                zeit=msg.zeit
            )
        )
        return

    art = msg.haustierart.lower()

    antwort = "❌ Es sind keine Plätze mehr frei."

    # Hund
    if "hund" in art:
        if kapazitaet["hund"] > 0:
            kapazitaet["hund"] -= 1
            antwort = (
                f"🐶 Hundebetreuung reserviert!\n"
                f"⏱️ {msg.betreuung_von} – {msg.betreuung_bis}"
            )

        else:
            antwort = "❌ Keine Hundekapazität mehr verfügbar."

    # Katze
    elif "katze" in art:
        if kapazitaet["katze"] > 0:
            kapazitaet["katze"] -= 1
            antwort = (
                f"🐱 Katzenbetreuung reserviert!\n"
                f"⏱️ {msg.betreuung_von} – {msg.betreuung_bis}"
            )

        else:
            antwort = "❌ Keine Katzenkapazität mehr verfügbar."

    else:
        antwort = "❌ Bitte 'Hund' oder 'Katze' angeben."

    # Antwort senden
    await ctx.send(
        client,
        Message(
            type="haustier_bestaetigung",
            message=antwort,
            zeit=msg.zeit
        )
    )

    ctx.logger.info(
        f"Antwort an {client} gesendet | Hund={kapazitaet['hund']} | Katze={kapazitaet['katze']}"
    )


if __name__ == "__main__":
    print("🐾 Haustierbetreuung gestartet…")
    petHotelAgent.run()
