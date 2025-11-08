from uagents import Agent, Context, Model


# NOTE: Run ReceiverAgent.py before running SenderAgent.py


class Message(Model):
    message: str


parkplatzAgent = Agent(
    name="ReceiverAgent",
    port=8001,
    seed="parkplatzAgent",
    endpoint=["http://localhost:8001/submit"],
)

print(parkplatzAgent.address)


@parkplatzAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Received message from {sender}: {msg.message}")
    print(sender)
    destination = ("test-agent://" + sender)
    # send the response
    await ctx.send(destination, Message(message="Komm vorbei. Wir haben noch etwas frei!"))


if __name__ == "__main__":
    parkplatzAgent.run()
