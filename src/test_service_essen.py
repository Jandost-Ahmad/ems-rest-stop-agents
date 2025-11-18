from uagents import Agent, Model, Context
from datetime import datetime

# ---------- Nachrichtenmodelle ----------
class EssenMessage(Model):
    type: str = "essensservice"
    zeit: str
    standard: int = 0
    vegetarisch: int = 0
    vegan: int = 0
    glutenfrei: int = 0
    client_sender: str = ""

class CentralServiceMessage(Model):
    messages: list[EssenMessage] = []

    def add_message(self, message: EssenMessage):
        self.messages.append(message)

class Message(Model):
    type: str
    message: str
    zeit: str = None

# ---------- Test-Agent ----------
testAgent = Agent(
    name="TestAgent",
    port=8100,
    seed="testAgent",
    endpoint=["http://localhost:8100/submit"],
)

central_service_address = "test-agent://agent1qddjgf6j894fattuq250mfcla8ljvknfmxyndt6uvkdzcpk9ngjck2ltx7v"

print(f"[TestAgent] gestartet! Adresse: {testAgent.address}")

# ---------- Nachricht periodisch senden ----------
@testAgent.on_interval(period=30)  # alle 30 Sekunden
async def send_test_message_periodic(ctx):
    essen_msg = EssenMessage(
        zeit=datetime.now().strftime("%H:%M"),
        standard=1,
        vegetarisch=0,
        vegan=0,
        glutenfrei=0,
        client_sender=testAgent.address
    )

    central_msg = CentralServiceMessage(messages=[essen_msg])

    # Nachricht als Model senden
    await ctx.send(central_service_address, central_msg)
    print(f"[TestAgent] CentralServiceMessage gesendet an {central_service_address} um {datetime.now().strftime('%H:%M:%S')}")

# Handler für Message
@testAgent.on_message(model=Message)
async def central_message_handler(ctx: Context, sender: str, msg: Message):
    print(f"[{msg.type}] {msg.message}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    testAgent.run()
