from uagents import Agent, Context, Model

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional für Essensservice

# ---------- Adressen der Agenten ----------
parkplatz_adresse = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
essensservice_adresse = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"

# ---------- LKW-Fahrer-Agent ----------
fahrerAgent = Agent(
    name="LKW_Fahrer",
    port=8010,
    seed="lkwFahrerAgent",
    endpoint=["http://localhost:8010/submit"],
)

# ---------- Automatische Parameter für LKW-Fahrer ----------
fahrzeug_typ = "LKW"
parkplatz_option = "mit Ladesäule"
behindert = False       # kein Behindertenparkplatz
essen_option = "Standard"
bestell_zeit = "19:00"  # feste Zeit für Frühstück
to_go = False            # über Nacht -> To-Go

print("\n--- LKW-Fahrer-Agent gestartet ---")
print(f"Fahrzeugtyp: {fahrzeug_typ}")
print(f"Parkplatz: {parkplatz_option}")
print(f"Behindertenparkplatz: {'Ja' if behindert else 'Nein'}")
print(f"Essen: {essen_option}, Uhrzeit: {bestell_zeit}, To-Go: {to_go}\n")

# ---------- Nachrichten empfangen ----------
@fahrerAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    print(f"Nachricht von {sender}: {msg.message}")

# ---------- Intervallnachricht alle 10 Sekunden ----------
@fahrerAgent.on_interval(period=10.0)
async def send_messages(ctx: Context):
    # Parkplatz-Anfrage (nur einmal nötig, kann aber alle 10s wiederholt werden)
    msg_text = f"Ich suche einen {fahrzeug_typ}-Parkplatz {parkplatz_option}"
    if behindert:
        msg_text += " (Behindert)"
    msg_text += "."
    await ctx.send(parkplatz_adresse, Message(message=msg_text))
    print(f"Nachricht an Parkplatz-Agent gesendet: {msg_text}")

    # Essensbestellung
    msg_text = f"Ich möchte {essen_option}-Essen bestellen."
    if to_go:
        msg_text += " (To-Go)"
    await ctx.send(essensservice_adresse, Message(message=msg_text, zeit=bestell_zeit))
    print(f"Nachricht an Essensservice-Agent gesendet: {msg_text}, Zeit: {bestell_zeit}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    fahrerAgent.run()
