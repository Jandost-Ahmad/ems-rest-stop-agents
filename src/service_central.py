# ---------- Uagents-Importe ----------
from typing import List, Union

from pydantic import Field
from uagents import Agent, Context, Model  # Message existiert nicht, wir benutzen Dictionaries

# ---------- Adressen der Service-Agenten ----------
parkplatz_adresse = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
essensservice_adresse = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"
kaffeeservice_adresse = "test-agent://agent1q2u5pp8cuq0fdzrh94842mu6scwyfv9ese0amr872t0xmdy9mfdncedjv7l"
hotel_adresse = "test-agent://agent1q2ar07qp4r8kale8pz2w5paefx90lf8w8z05xuja43rrwc75mw5j2s6e0zj"
haustier_adresse = "test-agent://agent1qffjvchcs36qed3ghwng43l9zw4x3pefxck3t8rsdsakkaww9trpwyh9qx0"

# ---------- Nachrichtenmodelle ----------
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
    client_sender: str

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

class CentralServiceMessage(Model):
    messages: List[Model]  # keine Field() hier

    def __init__(self, **data):
        # Standard-Liste initialisieren, falls nichts übergeben
        if "messages" not in data or data["messages"] is None:
            data["messages"] = []
        super().__init__(**data)

    def add_message(self, message: Model):
        self.messages.append(message)

# ---------- Service Map für den Dispatcher ----------
service_map = {
    "essensservice": essensservice_adresse,
    "haustierbetreuung": haustier_adresse,
    "hotel": hotel_adresse,
    "kaffee": kaffeeservice_adresse,
    "parkplatz": parkplatz_adresse
}

# ---------- CentralService-Agent ----------
centralserviceAgent = Agent(
    name="Centralservice",
    port=8000,
    seed="centralserviceAgent",
    endpoint=["http://localhost:8000/submit"],
)

# Handler für CentralServiceMessage
@centralserviceAgent.on_message(model=CentralServiceMessage)
async def central_message_handler(ctx: Context, sender: str, msg: CentralServiceMessage):
    if not msg.messages:
        print(f"[CentralServiceAgent] Ungültige Nachricht empfangen von {sender}")
        return

    for sub_msg in msg.messages:
        data = sub_msg.dict() if hasattr(sub_msg, "dict") else sub_msg
        msg_type = data.get("type")
        if not msg_type:
            print(f"[CentralServiceAgent] Nachricht ohne Typ: {data}")
            continue
        target_address = service_map.get(msg_type)
        if not target_address:
            print(f"[CentralServiceAgent] Kein Service für Typ '{msg_type}' gefunden")
            continue
        # Sende als dict, nicht als Pydantic-Model
        await ctx.send(target_address, data)


if __name__ == "__main__":
    print(f"[CentralServiceAgent] gestartet!")
    centralserviceAgent.run()
