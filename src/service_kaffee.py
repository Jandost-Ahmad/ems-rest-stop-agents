from uagents import Agent, Context, Model
import datetime

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional, Uhrzeit für Kaffee-Bestellung (HH:MM)

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
@kaffeeAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    text = msg.message.lower()

    # Prüfen, ob Kaffee bestellt wird
    if "kaffee" in text:
        # Zeit aus Nachricht prüfen
        if msg.zeit:
            try:
                bestell_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M")
            except ValueError:
                # Ungültige Zeit: nächste Zeit in 5 Minuten
                bestell_zeit = datetime.datetime.now() + datetime.timedelta(minutes=5)
        else:
            # Keine Zeit: nächste Zeit in 5 Minuten
            bestell_zeit = datetime.datetime.now() + datetime.timedelta(minutes=5)

        # Fertigstellungszeit: z. B. 5 Minuten nach gewünschter Uhrzeit
        fertig_zeit = bestell_zeit + datetime.timedelta(minutes=5)
        fertig_str = fertig_zeit.strftime("%H:%M")

        antwort = f"☕ Kaffee-To-Go wird für {fertig_str} fertig sein! Bitte abholen."
        await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
        ctx.logger.info(f"Antwort gesendet an {sender}: {antwort}")
        return

    # Sonstige Nachrichten
    antwort = "❌ Bitte nur Kaffee-To-Go bestellen."
    await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
    ctx.logger.info(f"Antwort gesendet an {sender}: {antwort}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    kaffeeAgent.run()
