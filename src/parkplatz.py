from uagents import Agent, Context, Model


# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional, kann None sein


# ---------- Initialisierung ----------
print("\n--- Parkplatz-Agent Initialisierung ---")
try:
    pkw_plaetze = int(input("Wie viele PKW-Parkplätze gibt es? "))
    lkw_plaetze = int(input("Wie viele LKW-Parkplätze gibt es? "))
    pkw_ladesaeulen = int(input("Wie viele PKW-Plätze mit Ladesäule? "))
    lkw_ladesaeulen = int(input("Wie viele LKW-Plätze mit Ladesäule? "))
except ValueError:
    print("⚠️ Ungültige Eingabe! Bitte nur Zahlen verwenden.")
    exit(1)

# Status speichern
parkplatz_status = {
    "PKW": {"frei": pkw_plaetze, "lade": pkw_ladesaeulen},
    "LKW": {"frei": lkw_plaetze, "lade": lkw_ladesaeulen},
}

print("\nParkplatz-Agent startet mit:")
print(f" - {pkw_plaetze} PKW-Plätzen ({pkw_ladesaeulen} mit Ladesäule)")
print(f" - {lkw_plaetze} LKW-Plätzen ({lkw_ladesaeulen} mit Ladesäule)\n")

# ---------- Agent definieren ----------
parkplatzAgent = Agent(
    name="ParkplatzAgent",
    port=8001,
    seed="parkplatzAgent",
    endpoint=["http://localhost:8001/submit"],
)

print(f"Parkplatz-Agent Adresse: {parkplatzAgent.address}\n")


# ---------- Nachrichten-Handler ----------
@parkplatzAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Nachricht von {sender}: {msg.message}")

    text = msg.message.lower()
    antwort = "❌ Leider keine passenden Parkplätze frei."

    # PKW-Anfragen
    if "pkw" in text:
        if "lade" in text and parkplatz_status["PKW"]["lade"] > 0:
            parkplatz_status["PKW"]["lade"] -= 1
            antwort = "✅ PKW-Parkplatz mit Ladesäule reserviert."
        elif parkplatz_status["PKW"]["frei"] > 0:
            parkplatz_status["PKW"]["frei"] -= 1
            antwort = "✅ PKW-Parkplatz ohne Ladesäule reserviert."

    # LKW-Anfragen
    elif "lkw" in text:
        if "lade" in text and parkplatz_status["LKW"]["lade"] > 0:
            parkplatz_status["LKW"]["lade"] -= 1
            antwort = "✅ LKW-Parkplatz mit Ladesäule reserviert."
        elif parkplatz_status["LKW"]["frei"] > 0:
            parkplatz_status["LKW"]["frei"] -= 1
            antwort = "✅ LKW-Parkplatz ohne Ladesäule reserviert."

    # Antwort senden
    await ctx.send(sender, Message(message=antwort))

    # Aktuellen Status loggen
    ctx.logger.info(
        f"Aktueller Status: PKW frei={parkplatz_status['PKW']['frei']} "
        f"(Lade={parkplatz_status['PKW']['lade']}), "
        f"LKW frei={parkplatz_status['LKW']['frei']} "
        f"(Lade={parkplatz_status['LKW']['lade']})"
    )


# ---------- Agent starten ----------
if __name__ == "__main__":
    parkplatzAgent.run()
