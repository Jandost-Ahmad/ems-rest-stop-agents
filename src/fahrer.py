from uagents import Agent, Context, Model

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional für Essensservice

# ---------- Adressen der Agenten ----------
parkplatz_adresse = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
essensservice_adresse = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"

# ---------- Fahrer-Agent ----------
fahrerAgent = Agent(
    name="Fahrer",
    port=8000,
    seed="fahrerAgent",
    endpoint=["http://localhost:8000/submit"],
)

# ---------- Initialisierung ----------
print("\n--- Fahrer-Initialisierung ---")
fahrzeug_typ = input("Fahrzeugtyp (PKW/LKW): ").strip().upper()
if fahrzeug_typ not in ["PKW", "LKW"]:
    print("⚠️ Ungültige Eingabe. Standard PKW ausgewählt.")
    fahrzeug_typ = "PKW"
print(f"Fahrzeugtyp: {fahrzeug_typ}\n")

# Hauptmenü
print("--- Fahrer-Agent Menü ---")
print("1. Parkplatz suchen")
print("2. Essensservice anfragen")
print("3. Beides")
wahl = input("Bitte wählen (1/2/3): ").strip()

# Untermenüs
parkplatz_option = None
essen_option = None
bestell_zeit = None

if wahl in ["1","3"]:
    print("\nParkplatz-Optionen:")
    print("1. Mit Ladesäule ⚡")
    print("2. Ohne Ladesäule")
    p_option = input("Bitte wählen (1/2): ").strip()
    parkplatz_option = "mit Ladesäule" if p_option == "1" else "ohne Ladesäule"

if wahl in ["2","3"]:
    print("\nEssens-Optionen:")
    print("1. Standard 🍔")
    print("2. Vegetarisch 🥦")
    print("3. Vegan 🌱")
    print("4. Glutenfrei 🌾")
    e_option = input("Bitte wählen (1/2/3/4): ").strip()
    essen_map = {"1": "Standard", "2": "Vegetarisch", "3": "Vegan", "4": "Glutenfrei"}
    essen_option = essen_map.get(e_option, "Standard")
    bestell_zeit = input("Wann möchten Sie essen? (HH:MM): ").strip()

# ---------- Nachrichten empfangen ----------
@fahrerAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    print(f"Nachricht von {sender}: {msg.message}")

# ---------- Intervallnachricht alle 10 Sekunden ----------
@fahrerAgent.on_interval(period=10.0)  # alle 10 Sekunden
async def send_messages(ctx: Context):
    if wahl in ["1","3"]:
        msg_text = f"Ich suche einen {fahrzeug_typ}-Parkplatz {parkplatz_option}."
        await ctx.send(parkplatz_adresse, Message(message=msg_text))
        print(f"Nachricht an Parkplatz-Agent gesendet: {msg_text}")

    if wahl in ["2","3"]:
        msg_text = f"Ich möchte {essen_option}-Essen bestellen."
        await ctx.send(essensservice_adresse, Message(message=msg_text, zeit=bestell_zeit))
        print(f"Nachricht an Essensservice-Agent gesendet: {msg_text}, Zeit: {bestell_zeit}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    fahrerAgent.run()
