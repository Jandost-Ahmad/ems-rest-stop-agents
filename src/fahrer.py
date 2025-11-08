from uagents import Agent, Context, Model

class Message(Model):
    message: str

parkplatz_adresse = (
    "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
)

fahrerAgent = Agent(
    name="Fahrer",
    port=8000,
    seed="faherAgent",
    endpoint=["http://localhost:8000/submit"],
)

print(fahrerAgent.address)


@fahrerAgent.on_interval(period=2.0)
async def send_message(ctx: Context):
    await ctx.send(parkplatz_adresse, Message(message="Hallo, ich suche einen Parkplatz!"))


@fahrerAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Received message from {sender}: {msg.message}")


if __name__ == "__main__":
    fahrerAgent.run()
