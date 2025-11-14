from uagents import Agent, Context, Model
import datetime

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None  # optional für Essensservice

# ---------- Essensservice-Agent ----------
essensserviceAgent = Agent(
    name="Essensservice",
    port=8002,
    seed="essensserviceAgent",
    endpoint=["http://localhost:8002/submit"],
)

print(f"\nEssensservice-Agent gestartet! Adresse: {essensserviceAgent.address}\n")

# ---------- Hardcoded Öffnungszeiten ----------
oeffnung = datetime.time(8, 0)   # 08:00 Uhr
schluss = datetime.time(20, 0)   # 20:00 Uhr

# ---------- Hardcoded Menü ----------
gerichte = {
    "standard": True,
    "vegetarisch": True,
    "vegan": True,
    "glutenfrei": True,
}

# ---------- Maximalanzahl Gerichte pro Stunde ----------
MAX_PRO_STUNDE = 60
# Stunden-Dict von 08 bis 19 (letzte Stunde ist 19:00–20:00)
bestellungen_pro_stunde = {str(h).zfill(2): 0 for h in range(oeffnung.hour, schluss.hour)}

# ---------- Startausgabe ----------
print("Essensservice bereit! 🍽️")
print(f"🕒 Öffnungszeiten: {oeffnung.strftime('%H:%M')} - {schluss.strftime('%H:%M')}")
print("📋 Menü:")
for k, v in gerichte.items():
    print(f"  - {k.capitalize()}: {'✅' if v else '❌'}")
print()

# ---------- Nachricht empfangen ----------
@essensserviceAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    text = msg.message.lower()

    # ---- Normale Gerichte ----
    try:
        fahrer_zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except (ValueError, TypeError):
        await ctx.send(sender, Message(message="❌ Ungültige Zeitangabe. Bitte HH:MM senden.", zeit=msg.zeit))
        return

    # Öffnungszeiten prüfen
    if not (oeffnung <= fahrer_zeit < schluss):
        antwort = f"❌ Wir haben zu dieser Uhrzeit geschlossen.\n🕒 Öffnungszeiten: {oeffnung.strftime('%H:%M')} - {schluss.strftime('%H:%M')}"
        await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
        return

    stunde = str(fahrer_zeit.hour).zfill(2)

    # Maximalanzahl pro Stunde prüfen
    if bestellungen_pro_stunde.get(stunde, 0) >= MAX_PRO_STUNDE:
        next_hour = fahrer_zeit.hour + 1
        gefunden = False
        while next_hour < schluss.hour:
            next_stunde = str(next_hour).zfill(2)
            if bestellungen_pro_stunde.get(next_stunde, 0) < MAX_PRO_STUNDE:
                freie_plaetze = MAX_PRO_STUNDE - bestellungen_pro_stunde[next_stunde]
                antwort = (
                    f"❌ Für {fahrer_zeit.strftime('%H:%M')} sind leider keine Gerichte mehr verfügbar.\n"
                    f"➡️ Bitte buchen Sie für {next_stunde}:00, dort sind noch {freie_plaetze} Gerichte frei."
                )
                gefunden = True
                break
            next_hour += 1
        if not gefunden:
            antwort = "❌ Leider sind für heute keine Gerichte mehr verfügbar."
    else:
        # Gericht prüfen
        verfuegbar = None
        for gericht in gerichte.keys():
            if gericht in text:
                verfuegbar = gerichte[gericht]
                break

        if verfuegbar:
            bestellungen_pro_stunde[stunde] += 1
            antwort = f"✅ Ihr gewünschtes Gericht ist für {fahrer_zeit.strftime('%H:%M')} reserviert!"
        else:
            antwort = "😔 Das gewünschte Gericht ist heute leider nicht verfügbar."

    # Antwort senden
    await ctx.send(sender, Message(message=antwort, zeit=msg.zeit))
    ctx.logger.info(f"Antwort gesendet an {sender}: {antwort}")

# ---------- Agent starten ----------
if __name__ == "__main__":
    essensserviceAgent.run()
