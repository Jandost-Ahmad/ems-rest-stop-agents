from uagents import Agent, Context, Model
import datetime


# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional, kann None sein


# ---------- Essensservice-Agent ----------
essensserviceAgent = Agent(
    name="Essensservice",
    port=8002,
    seed="essensserviceAgent",
    endpoint=["http://localhost:8002/submit"],
)

print(f"\nEssensservice-Agent gestartet! Adresse: {essensserviceAgent.address}\n")

# ---------- Initialisierung ----------
print("--- Essensservice-Initialisierung ---")

def parse_time(prompt):
    while True:
        value = input(prompt).strip()
        try:
            return datetime.datetime.strptime(value, "%H:%M").time()
        except ValueError:
            print("❌ Ungültiges Format. Bitte HH:MM eingeben (z. B. 08:00).")

oeffnung = parse_time("Öffnungszeit (z. B. 08:00): ")
schluss = parse_time("Schließzeit (z. B. 20:00): ")

# Verfügbare Gerichte
print("\nWelche Gerichte sind heute verfügbar? (j/n)")
gerichte = {
    "Standard": input("Standard-Essen verfügbar? (j/n): ").strip().lower() == "j",
    "Vegetarisch": input("Vegetarisch verfügbar? (j/n): ").strip().lower() == "j",
    "Vegan": input("Vegan verfügbar? (j/n): ").strip().lower() == "j",
    "Glutenfrei": input("Glutenfrei verfügbar? (j/n): ").strip().lower() == "j",
}

print("\nEssensservice bereit! 🍽️")
print(f"Öffnungszeiten: {oeffnung.strftime('%H:%M')} - {schluss.strftime('%H:%M')}")
print("Verfügbare Gerichte:")
for k, v in gerichte.items():
    print(f"  - {k}: {'✅' if v else '❌'}")


# ---------- Nachricht empfangen ----------
@essensserviceAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Nachricht empfangen von {sender}: {msg.message}, Zeit: {msg.zeit}")

    # Schritt 1: Uhrzeit von Fahrer-Agent prüfen
    try:
        fahrer_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except ValueError:
        await ctx.send(sender, Message(message="❌ Ungültige Zeitangabe. Bitte HH:MM senden.", zeit=msg.zeit))
        return

    # Schritt 2: Öffnungszeiten prüfen
    if not (oeffnung <= fahrer_zeit <= schluss):
        antwort = (
            f"❌ Wir haben zu dieser Uhrzeit geschlossen.\n"
            f"🕒 Öffnungszeiten: {oeffnung.strftime('%H:%M')} - {schluss.strftime('%H:%M')}"
        )
    else:
        # Schritt 3: Gericht prüfen
        gericht = msg.message.lower()
        verfuegbar = False
        for key in gerichte.keys():
            if key.lower() in gericht:
                verfuegbar = gerichte[key]
                break

        if verfuegbar:
            antwort = "✅ Ihr gewünschtes Gericht ist verfügbar! Bitte kommen Sie vorbei."
        else:
            antwort = "😔 Das gewünschte Gericht ist leider nicht verfügbar."

    # Antwort senden
    await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
    ctx.logger.info(f"Antwort gesendet an {sender}: {antwort}")


# ---------- Agent starten ----------
if __name__ == "__main__":
    essensserviceAgent.run()
