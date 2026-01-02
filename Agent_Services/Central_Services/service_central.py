from uagents import Agent, Context, Model
from typing import List


# ---- Gemeinsame Models (IDENTISCH zum TestClient!) ----
class EssenMessage(Model):
    type: str
    zeit: str
    standard: int
    vegetarisch: int
    vegan: int
    glutenfrei: int
    client_sender: str

class KaffeeMessage(Model):
    type: str
    zeit: str
    client_sender: str

class HaustierMessage(Model):
    type: str
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str

class HotelMessage(Model):
    type: str
    zimmerart: str
    zeit: str
    naechte: int
    client_sender: str

class ParkplatzMessage(Model):
    type: str
    fahrzeugart: str
    ladestation: bool
    zeit: str
    reservation_id: str
    client_sender: str


# ---------- CentralServiceMessage ----------
class CentralServiceMessage(Model):
    messages: list   # Liste aus dicts


# ---------- MODEL-REKONSTRUKTION ----------
model_factory = {
    "essensservice": EssenMessage,
    "kaffee": KaffeeMessage,
    "haustierbetreuung": HaustierMessage,
    "hotel": HotelMessage,
    "parkplatz": ParkplatzMessage,
}

# ---------- Zieladressen ----------
service_map = {
    "essensservice": "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5",
    "kaffee": "test-agent://agent1q2u5pp8cuq0fdzrh94842mu6scwyfv9ese0amr872t0xmdy9mfdncedjv7l",
    "haustierbetreuung": "test-agent://agent1qffjvchcs36qed3ghwng43l9zw4x3pefxck3t8rsdsakkaww9trpwyh9qx0",
    "hotel": "test-agent://agent1q2ar07qp4r8kale8pz2w5paefx90lf8w8z05xuja43rrwc75mw5j2s6e0zj",
    "parkplatz": "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9",
}


central = Agent(
    name="CentralService",
    port=8000,
    seed="centralservice",
    endpoint=["http://localhost:8000/submit"]
)


@central.on_message(model=CentralServiceMessage)
async def handle(ctx: Context, sender: str, msg: CentralServiceMessage):

    print(f"\n📨 [Central] {len(msg.messages)} Nachricht(en) erhalten von {sender[:20]}...")

    for entry in msg.messages:

        msg_type = entry.get("type")
        target = service_map.get(msg_type)

        if not target:
            print(f"❌ [Central] Kein Ziel für Typ '{msg_type}'")
            continue

        constructor = model_factory.get(msg_type)
        if not constructor:
            print(f"❌ [Central] Kein Model-Constructor für Typ '{msg_type}'")
            continue

        # dict -> spezifisches Model konvertieren
        try:
            reconstructed = constructor(**entry)
            print(f"✅ [Central] Weiterleiten an {msg_type} → {target[:40]}...")
            await ctx.send(target, reconstructed)
        except Exception as e:
            print(f"❌ [Central] Fehler beim Verarbeiten von {msg_type}: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CENTRAL SERVICE GESTARTET")
    print("=" * 60)
    print(f"📍 Agent-Adresse: {central.address}")
    print(f"🌐 Endpoint: http://localhost:8000/submit")
    print("=" * 60)
    print("\n⚠️  WICHTIG: Kopiere die Agent-Adresse oben in:")
    print("   - Agent_Fahrer/fahrer_gui.py (CENTRAL_SERVICE_ADDRESS)")
    print("   - Agent_Fahrer/voice_assistant.py (CENTRAL_SERVICE_ADDRESS)")
    print("=" * 60)
    print()
    central.run()
