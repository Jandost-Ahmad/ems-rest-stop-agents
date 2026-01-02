from uagents import Agent, Context, Model
from datetime import datetime, timedelta
import uuid


# ---- IDENTISCHE Models wie CentralService ----
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


class CentralServiceMessage(Model):
    messages: list


class Message(Model):
    type: str
    message: str
    zeit: str


# ---------- Adresse des CentralService ----------
central_service_address = "test-agent://agent1qdxu32w99hg82pmqvulkxttpvqpctvp2vya4w9d2mnl9rhj03mt464747cc"


testAgent = Agent(
    name="TestClient",
    port=9100,
    seed="testclient",
    endpoint=["http://100.68.40.75:9100/submit"],
)


@testAgent.on_interval(period=10)
async def send_test_msgs(ctx: Context):

    now = datetime.now()
    jetzt = now.strftime("%H:%M")
    in_10_min = (now + timedelta(minutes=10)).strftime("%H:%M")

    messages = [
        EssenMessage(
            type="essensservice",
            zeit=jetzt,
            standard=1,
            vegetarisch=2,
            vegan=0,
            glutenfrei=1,
            client_sender=testAgent.address
        ).dict(),

        KaffeeMessage(
            type="kaffee",
            zeit=in_10_min,
            client_sender=testAgent.address
        ).dict(),

        HaustierMessage(
            type="haustierbetreuung",
            haustierart="Hund",
            zeit=jetzt,
            betreuung_von=jetzt,
            betreuung_bis=in_10_min,
            client_sender=testAgent.address
        ).dict(),

        HotelMessage(
            type="hotel",
            zimmerart="Einzelzimmer",
            zeit=jetzt,
            naechte=2,
            client_sender=testAgent.address
        ).dict(),

        ParkplatzMessage(
            type="parkplatz",
            fahrzeugart="PKW",
            ladestation=True,
            zeit=in_10_min,
            reservation_id=str(uuid.uuid4())[:8],
            client_sender=testAgent.address
        ).dict(),
    ]

    msg = CentralServiceMessage(messages=messages)
    print("[Client] Sende Nachrichten an CentralService…")
    await ctx.send(central_service_address, msg)


@testAgent.on_message(model=Message)
async def handle(ctx: Context, sender: str, msg: Message):
    print(f"[Testclient] {msg.message} {msg.zeit}")

if __name__ == "__main__":
    print("[TestClient] gestartet…")
    testAgent.run()
