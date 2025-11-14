from uagents import Agent, Context, Model

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional für Essensservice

# ---------- Adressen der Agenten ----------
parkplatz_adresse = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
essensservice_adresse = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"

# ---------- Reisebus-Agent ----------
reisebusAgent = Agent(
    name="Reisebus",
    port=8011,
    seed="reisebusAgent",
    endpoint=["http://localhost:8011/submit"],
)

# ---------- Busparameter ----------
anzahl_passagiere = 60
gerichte = ["Standard", "Vegetarisch", "Vegan", "Glutenfrei"]
bestell_zeit = "12:00"  # Mittag
parkplatz_option = "mit Ladesäule"
behindert = False  # Bus benötigt keinen Behindertenparkplatz

print("\n--- Reisebus-Agent gestartet ---")
print(f"Anzahl Passagiere: {anzahl_passagiere}")
print(f"Parkplatz: {parkplatz_option}, Behindertenparkplatz: {'Ja' if behindert else 'Nein'}")
print(f"Menü: {gerichte}, Bestellzeit: {bestell_zeit}\n")

# ---------- Nachrichten empfangen ----------
@reisebusAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    print(f"Nachricht von {sender}: {msg.message}")

# ---------- Intervallnachricht einmalig ----------
@reisebusAgent.on_interval(period=10.0)
async def send_messages(ctx: Context):
    # ---- Parkplatz anfragen ----
    msg_text = f"Ich suche einen Bus-Parkplatz {parkplatz_option}"
    if behindert:
        msg_text += " (Behindert)"
    msg_text += "."
    await ctx.send(parkplatz_adresse, Message(message=msg_text))
    print(f"Nachricht an Parkplatz-Agent gesendet: {msg_text}")

    # ---- Sammelbestellung für alle 60 Passagiere ----
    bestell_text = "Sammelbestellung für Reisebus: "
    anteil = anzahl_passagiere // len(gerichte)
    rest = anzahl_passagiere % len(gerichte)

    bestellungen = {g: anteil for g in gerichte}
    for i in range(rest):
        # Rest zufällig verteilen
        bestellungen[gerichte[i % len(gerichte)]] += 1

    bestell_text += ", ".join([f"{anzahl}x {g}" for g, anzahl in bestellungen.items()])
    bestell_text += f". Zeit: {bestell_zeit}"

    await ctx.send(essensservice_adresse, Message(message=bestell_text, zeit=bestell_zeit))
    print(f"Sammelbestellung an Essensservice gesendet: {bestell_text}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    reisebusAgent.run()
