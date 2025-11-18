import datetime
from uagents import Model, Agent, Context

class EssenMessage(Model):
    type: str = "essensservice"
    zeit: str
    standard: int = 0
    vegetarisch: int = 0
    vegan: int = 0
    glutenfrei: int = 0
    client_sender: str = ""  # Wer die Nachricht geschickt hat

# ---------- Essensservice-Agent ----------
essensserviceAgent = Agent(
    name="Essensservice",
    port=8002,
    seed="essensserviceAgent",
    endpoint=["http://localhost:8002/submit"],
)

class Message(Model):
    type:str
    message: str
    zeit: str = None

# ---------- Hardcoded Öffnungszeiten und Menü ----------
oeffnung = datetime.time(8, 0)
schluss = datetime.time(20, 0)
gerichte = {
    "standard": True,
    "vegetarisch": True,
    "vegan": True,
    "glutenfrei": True,
}
MAX_PRO_STUNDE = 60
bestellungen_pro_stunde = {str(h).zfill(2): 0 for h in range(oeffnung.hour, schluss.hour)}

# ---------- Nachricht empfangen ----------


@essensserviceAgent.on_message(model=EssenMessage)
async def essen_message_handler(ctx: Context, sender: str, msg: EssenMessage):

    client = msg.client_sender

    # Zeit prüfen
    try:
        fahrer_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except (ValueError, TypeError):
        await ctx.send(client, Message(
            message="❌ Ungültige Zeitangabe. Bitte HH:MM senden.",
            zeit=msg.zeit
        ))
        return

    if not (oeffnung <= fahrer_zeit < schluss):
        await ctx.send(client, Message(
            type=essensserviceAgent.name,
            message=f"❌ Wir haben geschlossen. Öffnungszeiten: "
                    f"{oeffnung.strftime('%H:%M')} - {schluss.strftime('%H:%M')}",
            zeit=msg.zeit
        ))
        return

    stunde = str(fahrer_zeit.hour).zfill(2)

    if bestellungen_pro_stunde[stunde] >= MAX_PRO_STUNDE:
        await ctx.send(client, Message(
            type=essensserviceAgent.name,
            message=f"❌ Für {msg.zeit} sind keine Gerichte mehr verfügbar.",
            zeit=msg.zeit
        ))
        return

    bestellt = None
    for gericht, menge in [
        ("standard", msg.standard),
        ("vegetarisch", msg.vegetarisch),
        ("vegan", msg.vegan),
        ("glutenfrei", msg.glutenfrei)
    ]:
        if menge > 0 and gerichte.get(gericht):
            bestellt = gericht
            break

    if bestellt:
        bestellungen_pro_stunde[stunde] += 1
        antwort = f"✅ Ihr Gericht '{bestellt}' ist für {msg.zeit} reserviert!"
    else:
        antwort = "😔 Das gewünschte Gericht ist heute nicht verfügbar."

    await ctx.send(client, Message(
        type=essensserviceAgent.name,
        message=antwort,
        zeit=msg.zeit
    ))

    ctx.logger.info(f"Antwort gesendet an {client}: {antwort}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    essensserviceAgent.run()
