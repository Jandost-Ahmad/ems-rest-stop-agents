from uagents import Agent, Context, Model

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # Uhrzeit für die Bestellung (HH:MM)

# ---------- Pedler/Kunde-Agent ----------
pendlerAgent = Agent(
    name="Pedler",
    port=8012,
    seed="pendlerAgent",
    endpoint=["http://localhost:8012/submit"],
)

# Adresse des Essensservice-Agenten (hier für Kaffee-To-Go)
kaffeeservice_adresse = "test-agent://agent1q2u5pp8cuq0fdzrh94842mu6scwyfv9ese0amr872t0xmdy9mfdncedjv7l"

# Bestellzeit
bestellzeit = "09:30"

print("\nPedler-Agent gestartet! 🍵")
print(f"Sendet Kaffee-To-Go-Bestellungen an: {kaffeeservice_adresse}\n")

# ---------- Nachrichten empfangen ----------
@pendlerAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    print(f"[Antwort vom Agenten] {sender}: {msg.message}")

# ---------- Intervallnachricht (alle 10 Sekunden) ----------
@pendlerAgent.on_interval(period=10.0)  # alle 10 Sekunden
async def sende_kaffee(ctx: Context):
    msg_text = f"Ich möchte einen Kaffee To-Go"
    await ctx.send(kaffeeservice_adresse, Message(message=msg_text, zeit=bestellzeit))
    print(f"[Kaffee bestellt für {bestellzeit}] Nachricht gesendet!")

# ---------- Agent starten ----------
if __name__ == "__main__":
    pendlerAgent.run()
