from typing import List

from pydantic import Field
from uagents import Agent, Context, Model
from datetime import datetime, timedelta
import uuid

# ---------- Service-Nachrichten ----------
class EssenMessage(Model):
    type: str = "essensservice"
    zeit: str
    standard: int = 0
    vegetarisch: int = 0
    vegan: int = 0
    glutenfrei: int = 0
    client_sender: str = ""

class KaffeeMessage(Model):
    type: str = "kaffee"
    zeit: str = None
    client_sender: str = ""

class HaustierMessage(Model):
    type: str = "haustierbetreuung"
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str

class HotelMessage(Model):
    type: str = "hotel"
    zimmerart: str
    zeit: str
    naechte: int = 1
    client_sender: str

class ParkplatzMessage(Model):
    type: str = "parkplatz"
    fahrzeugart: str
    ladestation: bool
    zeit: str
    reservation_id: str
    client_sender: str

class Message(Model):
    type: str
    message: str
    zeit: str = None

# ---------- Zentral-Nachricht ----------
class CentralServiceMessage(Model):
    messages: List[Model]  # keine Field() hier

    def __init__(self, **data):
        # Standard-Liste initialisieren, falls nichts übergeben
        if "messages" not in data or data["messages"] is None:
            data["messages"] = []
        super().__init__(**data)

    def add_message(self, message: Model):
        self.messages.append(message)

# ---------- Central Service Adresse ----------
central_service_address = "test-agent://agent1qddjgf6j894fattuq250mfcla8ljvknfmxyndt6uvkdzcpk9ngjck2ltx7v"

# ---------- Test-Agent ----------
testAgent = Agent(
    name="TestClient",
    port=9100,
    seed="testClient",
    endpoint=[central_service_address],
)

# ---------- Antworten empfangen ----------
@testAgent.on_message(model=Message)
async def response_handler(ctx: Context, sender: str, msg: Message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Antwort von {sender}: {msg.type} | {msg.message} | {msg.zeit}")

# ---------- Intervall: Nachrichten senden ----------
@testAgent.on_interval(period=10.0)
async def send_test_messages(ctx: Context):
    client_id = testAgent.address
    jetzt = datetime.now().strftime("%H:%M")
    in_10_min = (datetime.now() + timedelta(minutes=10)).strftime("%H:%M")

    # Erzeuge alle Service-Nachrichten
    essen_msg = EssenMessage(
        zeit=jetzt,
        standard=2,
        vegetarisch=1,
        vegan=1,
        glutenfrei=0,
        client_sender=client_id
    )
    kaffee_msg = KaffeeMessage(
        zeit=in_10_min,
        client_sender=client_id
    )
    haustier_msg = HaustierMessage(
        haustierart="Hund",
        zeit=jetzt,
        betreuung_von=jetzt,
        betreuung_bis=in_10_min,
        client_sender=client_id
    )
    hotel_msg = HotelMessage(
        zimmerart="Einzelzimmer",
        zeit=jetzt,
        naechte=2,
        client_sender=client_id
    )
    parkplatz_msg = ParkplatzMessage(
        fahrzeugart="PKW",
        ladestation=True,
        zeit=in_10_min,
        reservation_id=str(uuid.uuid4())[:8],
        client_sender=client_id
    )

    # Alles in eine CentralServiceMessage packen
    central_msg = CentralServiceMessage()
    for msg in [essen_msg, kaffee_msg, haustier_msg, hotel_msg, parkplatz_msg]:
        central_msg.add_message(msg)

    # Nachricht an den Central Service senden
    await ctx.send(central_service_address, central_msg)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gesendet: CentralServiceMessage mit {len(central_msg.messages)} Nachrichten")

# ---------- Agent starten ----------
if __name__ == "__main__":
    print("TestClient-Agent startet...")
    testAgent.run()
