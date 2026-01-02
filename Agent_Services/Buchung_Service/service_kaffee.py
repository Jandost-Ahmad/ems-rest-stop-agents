from uagents import Agent, Context, Model
import datetime


# ---------- Input-Modell ----------
class KaffeeMessage(Model):
    type: str
    zeit: str
    client_sender: str


# ---------- Output-Modell ----------
class Message(Model):
    type: str
    message: str
    zeit: str


# ---------- Agent ----------
kaffeeAgent = Agent(
    name="KaffeeService",
    port=8008,
    seed="kaffeeServiceAgent",
    endpoint=["http://localhost:8008/submit"],
)


@kaffeeAgent.on_message(model=KaffeeMessage)
async def kaffee_handler(ctx: Context, sender: str, msg: KaffeeMessage):
    client = msg.client_sender or sender

    # Zeit prüfen
    try:
        bestellzeit = datetime.datetime.strptime(msg.zeit, "%H:%M")
    except:
        bestellzeit = datetime.datetime.now()

    fertig = bestellzeit + datetime.timedelta(minutes=5)
    fertig_str = fertig.strftime("%H:%M")

    antwort = f"☕ Kaffee ist um {fertig_str} abholbereit."

    await ctx.send(client, Message(
        type="kaffee_bestaetigung",
        message=antwort,
        zeit=fertig_str
    ))

    ctx.logger.info(f"Kaffee-Bestätigung: {antwort}")


if __name__ == "__main__":
    print("☕ Kaffee-Service gestartet…")
    print(f"📍 Adresse: {kaffeeAgent.address}")
    kaffeeAgent.run()
