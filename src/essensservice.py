from uagents import Agent, Context
# Agent 3

# Create an agent named Alice
essensservice = Agent(name="essensservice", seed="YOUR NEW PHRASE", port=8000, endpoint=["http://localhost:8000/submit"])


# Define a periodic task for Alice
@essensservice.on_interval(period=2.0)
async def say_hello(ctx: Context):
    ctx.logger.info(f'Hallo, ich bin ein {essensservice.name}')


# Run the agent
if __name__ == "__main__":
    essensservice.run()