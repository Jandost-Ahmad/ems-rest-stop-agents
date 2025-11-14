from uagents import Agent, Context, Model
import datetime

# ---------- Nachrichtenmodelle ----------
class HaustierMessage(Model):
    message: str
    zeit: str = None
    betreuung_von: str = None
    betreuung_bis: str = None

class HotelMessage(Model):
    message: str
    zeit: str = None
    naechte: int = 1

class Message(Model):
    message: str
    zeit: str = None


# ---------- Adressen ----------
hotel_adresse = "test-agent://agent1q2ar07qp4r8kale8pz2w5paefx90lf8w8z05xuja43rrwc75mw5j2s6e0zj"
haustier_adresse = "test-agent://agent1qffjvchcs36qed3ghwng43l9zw4x3pefxck3t8rsdsakkaww9trpwyh9qx0"
parkplatz_adresse = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"


# ---------- Familien-Agent ----------
familyAgent = Agent(
    name="FamilienAgent",
    port=8016,
    seed="familienAgent",
    endpoint=["http://localhost:8016/submit"],
)

print("\n👨‍👩‍👧🐶🚗 Familien-Agent gestartet!")
print(f"Hotel-Adresse:        {hotel_adresse}")
print(f"Haustier-Adresse:     {haustier_adresse}")
print(f"Parkplatz-Adresse:    {parkplatz_adresse}\n")


# ---------- Antworten empfangen ----------
@familyAgent.on_message(model=HotelMessage)
async def hotel_reply(ctx: Context, sender: str, msg: HotelMessage):
    print(f"[Antwort HOTEL] {sender}: {msg.message}")

@familyAgent.on_message(model=HaustierMessage)
async def hund_reply(ctx: Context, sender: str, msg: Message):
    print(f"[Antwort HAUSTIERE] {sender}: {msg.message}")

@familyAgent.on_message(model=Message)
async def park_reply(ctx: Context, sender: str, msg: Message):
    print(f"[Antwort PARKPLATZ] {sender}: {msg.message}")


# ---------- Periodische Buchung ----------
@familyAgent.on_interval(period=10.0)
async def sende_buchung(ctx: Context):

    jetzt = datetime.datetime.now().strftime("%H:%M")

    # --- 1) Familienzimmer buchen (Hotel) ---
    hotel_text = "Wir möchten ein Familienzimmer buchen"
    await ctx.send(
        hotel_adresse,
        HotelMessage(
            message=hotel_text,
            zeit=jetzt,
            naechte=2  # Beispiel: 2 Nächte
        )
    )
    print(f"[Familie → Hotel] Buchung gesendet für {jetzt} (2 Nächte)")

    # --- 2) Hund über Nacht anmelden (Haustierbetreuung) ---
    hund_von = "20:00"  # heute
    hund_bis = "07:00"  # morgen

    hund_text = "Wir möchten einen Hund anmelden"
    await ctx.send(
        haustier_adresse,
        HaustierMessage(
            message=hund_text,
            zeit=jetzt,
            betreuung_von=hund_von,
            betreuung_bis=hund_bis
        )
    )
    print(f"[Familie → Haustiere] Hundebetreuung {hund_von}–{hund_bis} gesendet")

    # --- 3) Parkplatz reservieren (Parkplatz-Agent) ---
    park_text = "Wir möchten einen PKW Parkplatz buchen"

    await ctx.send(
        parkplatz_adresse,
        Message(
            message=park_text,
            zeit=jetzt
        )
    )
    print(f"[Familie → Parkplatz] Parkplatzanfrage für {jetzt} gesendet")


# ---------- Start ----------
if __name__ == "__main__":
    familyAgent.run()
