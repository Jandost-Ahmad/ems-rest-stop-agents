from uagents import Agent, Context, Model

# ---------- Nachrichtenmodell ----------
class Message(Model):
    message: str
    zeit: str = None

# ---------- Initialisierung ----------
try:
    pkw_total = 100
    pkw_lade_total = 50
    lkw_total = 300   # alle LKW haben Ladeinfrastruktur
    bus_total = 3     # neue Bus-Parkplätze mit Ladeinfrastruktur
except ValueError:
    print("⚠️ Ungültige Eingabe! Bitte nur Zahlen verwenden.")
    exit(1)

# ---------- 2 % Behindertenparkplätze ----------
def two_percent(x):
    return max(1, round(x * 0.02))

# PKW behindert
behindert_pkw_ohne_lade = two_percent(pkw_total)
behindert_pkw_mit_lade = two_percent(pkw_total)

# LKW behindert (ALLE MIT LADE!)
behindert_lkw_mit_lade = two_percent(lkw_total)

# ---------- Normale PKW-Berechnung ----------
pkw_rest = pkw_total - behindert_pkw_ohne_lade - behindert_pkw_mit_lade

pkw_lade = min(pkw_lade_total, pkw_rest)
pkw_frei = pkw_rest - pkw_lade

# ---------- Normale LKW-Berechnung ----------
# ALLE LKW-Parkplätze haben Ladeinfrastruktur
lkw_lade = lkw_total - behindert_lkw_mit_lade

# ---------- Bus-Parkplätze ----------
bus_lade = bus_total  # alle Bus-Parkplätze haben Ladeinfrastruktur

# ---------- Status speichern ----------
parkplatz_status = {
    "PKW": {
        "frei": pkw_frei,
        "lade": pkw_lade
    },
    "PKW_Behindert": {
        "frei": behindert_pkw_ohne_lade,
        "lade": behindert_pkw_mit_lade
    },
    "LKW": {
        "lade": lkw_lade
    },
    "LKW_Behindert": {
        "lade": behindert_lkw_mit_lade  # kein "frei" mehr!
    },
    "BUS": {
        "lade": bus_lade
    }
}

print("\nParkplatz-Agent startet mit:")
# PKW
print("🅿️ PKW:")
print(f"   - Normal frei: {parkplatz_status['PKW']['frei']}")
print(f"   - Mit Ladesäule: {parkplatz_status['PKW']['lade']}")

# PKW Behindert
print("♿ PKW Behindertengerecht:")
print(f"   - Normal frei: {parkplatz_status['PKW_Behindert']['frei']}")
print(f"   - Mit Ladesäule: {parkplatz_status['PKW_Behindert']['lade']}")

# LKW
print("🚚 LKW:")
print(f"   - Mit Ladesäule: {parkplatz_status['LKW']['lade']}")

# LKW Behindert
print("♿🚚 LKW Behindertengerecht:")
print(f"   - Mit Ladesäule: {parkplatz_status['LKW_Behindert']['lade']}")

# Bus
print("🚌 Bus:")
print(f"   - Mit Ladesäule: {parkplatz_status['BUS']['lade']} \n")

# ---------- Agent definieren ----------
parkplatzAgent = Agent(
    name="ParkplatzAgent",
    port=8001,
    seed="parkplatzAgent",
    endpoint=["http://localhost:8001/submit"],
)

# ---------- Nachrichten-Handler ----------
@parkplatzAgent.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    text = msg.message.lower()
    antwort = "❌ Leider keine passenden Parkplätze frei."

    # ---- Behindertenparkplätze PKW ----
    if "behindert" in text and "pkw" in text:
        if "lade" in text:
            if parkplatz_status["PKW_Behindert"]["lade"] > 0:
                parkplatz_status["PKW_Behindert"]["lade"] -= 1
                antwort = "♿🔌 Behinderten-PKW-Ladeparkplatz reserviert."
        else:
            if parkplatz_status["PKW_Behindert"]["frei"] > 0:
                parkplatz_status["PKW_Behindert"]["frei"] -= 1
                antwort = "♿ PKW-Behindertenparkplatz reserviert."

    # ---- Behindertenparkplätze LKW (ALLE MIT LADE!) ----
    elif "behindert" in text and "lkw" in text:
        if parkplatz_status["LKW_Behindert"]["lade"] > 0:
            parkplatz_status["LKW_Behindert"]["lade"] -= 1
            antwort = "♿🚚🔌 Behinderten-LKW-Ladeparkplatz reserviert."

    # ---- Normale PKW ----
    elif "pkw" in text:
        if "lade" in text and parkplatz_status["PKW"]["lade"] > 0:
            parkplatz_status["PKW"]["lade"] -= 1
            antwort = "🔌🚗 PKW-Ladeparkplatz reserviert."
        elif parkplatz_status["PKW"]["frei"] > 0:
            parkplatz_status["PKW"]["frei"] -= 1
            antwort = "🚗 PKW-Parkplatz ohne Ladesäule reserviert."

    # ---- Normale LKW (ALLE MIT LADE!) ----
    elif "lkw" in text:
        if parkplatz_status["LKW"]["lade"] > 0:
            parkplatz_status["LKW"]["lade"] -= 1
            antwort = "🚚🔌 LKW-Ladeparkplatz reserviert."

    # ---- Bus ----
    elif "bus" in text:
        if parkplatz_status["BUS"]["lade"] > 0:
            parkplatz_status["BUS"]["lade"] -= 1
            antwort = "🚌🔌 Bus-Ladeparkplatz reserviert."

    # Antwort senden
    await ctx.send(sender, Message(message=antwort))

    # Logging
    ctx.logger.info(
        f"PKW frei={parkplatz_status['PKW']['frei']} | "
        f"PKW Lade={parkplatz_status['PKW']['lade']} | "
        f"PKW Behindert frei={parkplatz_status['PKW_Behindert']['frei']} | "
        f"PKW Behindert Lade={parkplatz_status['PKW_Behindert']['lade']} | "
        f"LKW Lade={parkplatz_status['LKW']['lade']} | "
        f"LKW Behindert Lade={parkplatz_status['LKW_Behindert']['lade']} | "
        f"BUS Lade={parkplatz_status['BUS']['lade']}"
    )

# ---------- Agent starten ----------
if __name__ == "__main__":
    parkplatzAgent.run()
