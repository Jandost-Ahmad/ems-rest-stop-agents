import uuid
from uagents import Agent, Context, Model


# --- Models --- #

class GarderobeAbgabeRequest(Model):
    artikel: str
    token_typ: str         # "digital" oder "physisch"
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


# --- Garderobe Agent --- #

garderobe = Agent(
    name="GarderobeAgent",
    port=8006,
    seed="garderoben-seed",
    endpoint=["http://localhost:8006/submit"]
)

slots = {}
MAX_SLOTS = 100


def freier_slot():
    for i in range(MAX_SLOTS):
        if i not in slots:
            return i
    return None


@garderobe.on_message(model=GarderobeAbgabeRequest)
async def handle_abgabe(ctx: Context, sender: str, msg: GarderobeAbgabeRequest):

    slot = freier_slot()
    if slot is None:
        await ctx.send(sender, GarderobeAbgabeResponse(
            qr_code="",
            info="❌ Keine Plätze mehr frei",
            correlation_id=msg.correlation_id
        ))
        return

    qr = str(uuid.uuid4())
    slots[slot] = {
        "artikel": msg.artikel,
        "qr": qr,
        "token_typ": msg.token_typ
    }

    # -----------------------------------
    #   Neue Logik: Token-Ausgabe
    # -----------------------------------
    if msg.token_typ == "digital":
        token_info = (
            "📧 Digitaler Token ausgegeben.\n"
            "📷 Bitte machen Sie ein Foto dieses QR-Codes!"
        )
    else:
        token_info = (
            "🖨️ Physischer Token erstellt.\n"
            "🖨️ QR-Code wurde ausgedruckt."
        )

    await ctx.send(sender, GarderobeAbgabeResponse(
        qr_code=qr,
        info=f"Artikel '{msg.artikel}' in Fach {slot} abgelegt.\n{token_info}",
        correlation_id=msg.correlation_id
    ))


@garderobe.on_message(model=GarderobeAbholungRequest)
async def handle_abholung(ctx: Context, sender: str, msg: GarderobeAbholungRequest):

    for slot, data in list(slots.items()):
        if data["qr"] == msg.qr_code:
            artikel = data["artikel"]
            token_typ = data["token_typ"]
            del slots[slot]

            await ctx.send(sender, GarderobeAbholungResponse(
                artikel=artikel,
                info=f"Artikel '{artikel}' aus Fach {slot} ausgegeben. Token war: {token_typ}",
                correlation_id=msg.correlation_id
            ))
            return

    await ctx.send(sender, GarderobeAbholungResponse(
        artikel="",
        info="❌ Ungültiger QR-Code",
        correlation_id=msg.correlation_id
    ))


if __name__ == "__main__":
    garderobe.run()
