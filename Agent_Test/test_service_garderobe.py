import uuid
from uagents import Agent, Context, Model


# --- Models --- #

class GarderobeAbgabeRequest(Model):
    artikel: str
    token_typ: str       # "digital" oder "physisch"
    correlation_id: str

class GarderobeAbgabeResponse(Model):
    qr_code: str
    info: str
    correlation_id: str

class GarderobeAbholungRequest(Model):
    qr_code: str
    correlation_id: str

class GarderobeAbholungResponse(Model):
    artikel: str
    info: str
    correlation_id: str


# --- Client Agent --- #

client = Agent(
    name="ClientAgent",
    port=9200,
    seed="client-seed",
    endpoint=["http://localhost:9200/submit"]
)

GARDEROBE_ADDRESS = "agent1qv4yln7sn3e7v2r3vq9svvnm3ltx5jfgwm7aa2qg7argntwn62lxxvnrnp2"

last_qr_code = None
counter = 0


# --- Response Handler --- #

@client.on_message(model=GarderobeAbgabeResponse)
async def handle_abgabe(ctx: Context, sender: str, msg: GarderobeAbgabeResponse):
    global last_qr_code
    print("\n📥 Antwort vom Garderoben-Agent:")
    print(msg.info)
    print("QR-Code:", msg.qr_code)
    last_qr_code = msg.qr_code


@client.on_message(model=GarderobeAbholungResponse)
async def handle_abholung(ctx: Context, sender: str, msg: GarderobeAbholungResponse):
    print("\n📥 Abholung abgeschlossen:")
    print(msg.info)
    print("Artikel:", msg.artikel)



# --- PERIODISCHE NACHRICHTEN --- #

@client.on_interval(period=10.0)
async def periodic(ctx: Context):
    global counter, last_qr_code

    print("\n⏳ Periodische Aktion…")

    # gerade Durchläufe → Artikel abgeben
    if counter % 2 == 0:
        cid = str(uuid.uuid4())
        artikel = f"Artikel-{counter}"

        # abwechselnd digital/physisch
        token_typ = "digital" if counter % 4 == 0 else "physisch"

        msg = GarderobeAbgabeRequest(
            artikel=artikel,
            token_typ=token_typ,
            correlation_id=cid
        )

        print(f"➡️ Artikel abgeben: {artikel} (Token: {token_typ})")
        await ctx.send(GARDEROBE_ADDRESS, msg)

    # ungerade Durchläufe → Artikel abholen
    else:
        if last_qr_code:
            cid = str(uuid.uuid4())
            msg = GarderobeAbholungRequest(
                qr_code=last_qr_code,
                correlation_id=cid
            )

            print(f"➡️ Artikel abholen mit QR: {last_qr_code}")
            await ctx.send(GARDEROBE_ADDRESS, msg)
            last_qr_code = None
        else:
            print("⚠️ Kein QR-Code vorhanden – keine Abholung möglich.")

    counter += 1


# --- Main --- #

if __name__ == "__main__":
    client.run()
