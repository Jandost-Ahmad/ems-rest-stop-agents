import datetime
from uagents import Model, Agent, Context


# ---------- Input-Modell ----------
class EssenMessage(Model):
    type: str
    zeit: str
    standard: int
    vegetarisch: int
    vegan: int
    glutenfrei: int
    client_sender: str


# ---------- Output-Modell ----------
class Message(Model):
    type: str
    message: str
    zeit: str


# ---------- Agent ----------
essensserviceAgent = Agent(
    name="Essensservice",
    port=8002,
    seed="essensserviceAgent",
    endpoint=["http://localhost:8002/submit"],
)


# ---------- Öffnungszeiten ----------
oeffnung = datetime.time(8, 0)
schluss = datetime.time(20, 0)

MAX_PRO_STUNDE = 60
bestellungen_pro_stunde = {str(h).zfill(2): 0 for h in range(oeffnung.hour, schluss.hour)}

gerichte = ["standard", "vegetarisch", "vegan", "glutenfrei"]


@essensserviceAgent.on_message(model=EssenMessage)
async def essen_handler(ctx: Context, sender: str, msg: EssenMessage):
    client = msg.client_sender or sender

    # Zeit prüfen
    try:
        zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        await ctx.send(client, Message(
            type="essen_fehler",
            message="❌ Ungültige Zeit (HH:MM erforderlich).",
            zeit=msg.zeit
        ))
        return

    if not (oeffnung <= zeit < schluss):
        await ctx.send(client, Message(
            type="essen_fehler",
            message=f"❌ Essensservice hat geschlossen. Öffnungszeiten {oeffnung.strftime('%H:%M')}–{schluss.strftime('%H:%M')}.",
            zeit=msg.zeit
        ))
        return

    stunde = str(zeit.hour).zfill(2)

    if bestellungen_pro_stunde[stunde] >= MAX_PRO_STUNDE:
        await ctx.send(client, Message(
            type="essen_fehler",
            message=f"❌ Für {msg.zeit} sind keine Gerichte mehr verfügbar.",
            zeit=msg.zeit
        ))
        return

    # Gericht auswählen
    gewaehlt = None
    for gericht, menge in [
        ("standard", msg.standard),
        ("vegetarisch", msg.vegetarisch),
        ("vegan", msg.vegan),
        ("glutenfrei", msg.glutenfrei)
    ]:
        if menge > 0:
            gewaehlt = gericht
            break

    if not gewaehlt:
        antwort = "😔 Kein Gericht ausgewählt oder Gericht nicht verfügbar."
    else:
        bestellungen_pro_stunde[stunde] += 1
        antwort = f"🍽️ Gericht '{gewaehlt}' ist für {msg.zeit} reserviert!"

    await ctx.send(client, Message(
        type="essen_bestaetigung",
        message=antwort,
        zeit=msg.zeit
    ))

    ctx.logger.info(f"Essen bestätigt: {antwort}")


if __name__ == "__main__":
    essensserviceAgent.run()
