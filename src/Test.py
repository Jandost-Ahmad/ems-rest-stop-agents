from uagents import Agent, Context, Model

agent = Agent(
    name="Agent",
    seed="Agent",
    port=8000,
    endpoint=["http://localhost:8000/submit"]
)

Destination_Address = 'agentX'


class Message(Model):
    message: str


message = Message(message='Test')


@agent.on_interval(period=5.0)
async def send_message(ctx: Context):
    await ctx.send(Destination_Address, message)


@agent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Received message from {sender}: {msg.message}")
