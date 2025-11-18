from uagents import Agent, Context, Model
import datetime

# ---------- Input-Modell ----------
class KaffeeMessage(Model):
    type: str = "kaffee"
    zeit: str = None       # gewünschte Abholzeit HH:MM oder Minuten
    client_sender: str

# ---------- Output-Modell ----------
class Message(Model):
    type: str             # z.B. "kaffee_bestaetigung"
    message: str
    zeit: str = None      # optionale Zeit

# ---------- Kaffee-To-Go-Agent ----------
kaffeeAgent = Agent(
    name="KaffeeService",
    port=8003,
    seed="kaffeeServiceAgent",
    endpoint=["http://localhost:8003/submit"],
)

print(f"\nKaffee-To-Go-Agent gestartet! Adresse: {kaffeeAgent.address}\n")
print("☕ Kaffee-To-Go: 24/7 verfügbar\n")

# ---------- Nachricht empfangen ----------
@kaffeeAgent.on_message(model=KaffeeMessage)
async def message_handler(ctx: Context, sender: str, msg: KaffeeMessage):
    client = msg.client_sender or sender  # Antwort geht an den Client

    # Zeit prüfen
    if msg.zeit:
        try:
            bestell_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M")
        except ValueError:
            # Ungültige Zeit: in 5 Minuten fertig
            bestell_zeit = datetime.datetime.now() + datetime.timedelta(minutes=5)
    else:
        bestell_zeit = datetime.datetime.now() + datetime.timedelta(minutes=5)

    # Fertigstellungszeit: 5 Minuten nach gewünschter Zeit
    fertig_zeit = bestell_zeit + datetime.timedelta(minutes=5)
    fertig_str = fertig_zeit.strftime("%H:%M")

    antwort_text = f"☕ Kaffee-To-Go wird für {fertig_str} fertig sein! Bitte abholen."
    await ctx.send(client, Message(type="kaffee_bestaetigung", message=antwort_text, zeit=fertig_str))
    ctx.logger.info(f"Antwort gesendet an {client}: {antwort_text}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    kaffeeAgent.run()
