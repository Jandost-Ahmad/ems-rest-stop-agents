"""Pet care service agent.

This module defines the `Haustierbetreuung` agent which processes pet care
reservation requests (`HaustierMessage`) and responds with confirmations or 
error messages (`Message`).

- Supported pets: dogs (Hund), cats (Katze)
- Dog capacity: 10 slots
- Cat capacity: 20 slots
- Requires care period: betreuung_von to betreuung_bis

"""
from uagents import Agent, Context, Model
import datetime


# =============================================================================
# DATA MODELS
# =============================================================================

class HaustierMessage(Model):
    """
    Input model for pet care reservation requests.
    
    Represents an incoming request to reserve pet care for a specific time period.
    The agent processes this message and returns a confirmation or error.
    
    Attributes:
        type (str): Message type identifier (e.g., "haustier_anfrage")
        haustierart (str): Type of pet ("Hund" or "Katze")
        zeit (str): Request time in "HH:MM" format (24-hour)
        betreuung_von (str): Care start time in "HH:MM" format
        betreuung_bis (str): Care end time in "HH:MM" format
        client_sender (str): Address of the originating client agent
    
    Example:
        >>> msg = HaustierMessage(
        ...     type="haustier_anfrage",
        ...     haustierart="Hund",
        ...     zeit="10:00",
        ...     betreuung_von="10:00",
        ...     betreuung_bis="18:00",
        ...     client_sender="agent1q2..."
        ... )
    """
    type: str
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str


class Message(Model):
    """
    Output model for agent responses.
    
    Represents the agent's response to a pet care reservation request,
    containing either a confirmation or an error message.
    
    Attributes:
        type (str): Response type identifier
                   - "haustier_bestaetigung": Successful reservation
                   - "haustier_fehler": Request error or rejection
        message (str): Human-readable confirmation or error message
        zeit (str): Echo of the requested time from the original request
    
    Example:
        >>> response = Message(
        ...     type="haustier_bestaetigung",
        ...     message="🐶 Hundebetreuung reserviert!\n⏱️ 10:00 – 18:00",
        ...     zeit="10:00"
        ... )
    """
    type: str
    message: str
    zeit: str



# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

petHotelAgent = Agent(
    name="Haustierbetreuung",
    port=8010,
    seed="petHotelAgent",
    endpoint=["http://localhost:8010/submit"],
)
"""
Main agent instance for the pet care service.

Configuration:
    - name: "Haustierbetreuung" - Agent identifier for logging
    - port: 8010 - Network port for agent communication
    - seed: "petHotelAgent" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""


# =============================================================================
# BUSINESS LOGIC CONFIGURATION
# =============================================================================

# Capacity management: Available slots per pet type
# Dogs: 10 slots available
# Cats: 20 slots available
# Note: Capacity is shared and decrements with each reservation
kapazitaet = {
    "hund": 10,
    "katze": 20
}



# =============================================================================
# MESSAGE HANDLER
# =============================================================================

@petHotelAgent.on_message(model=HaustierMessage)
async def handler(ctx: Context, sender: str, msg: HaustierMessage):
    """
    Main message handler for pet care reservation requests.
    
    Processes incoming HaustierMessage requests, validates the request parameters,
    checks capacity availability, and sends back a confirmation or error message.
    
    Workflow:
        1. Client Identification: Determines the client address for response
        2. Time Validation: Parses and validates the requested time
        3. Care Period Validation: Validates betreuung_von and betreuung_bis
        4. Pet Type Check: Identifies dog or cat from haustierart field
        5. Capacity Check: Verifies available slots for the pet type
        6. Reservation: Records reservation and sends confirmation
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (HaustierMessage): The incoming pet care reservation request
    
    Returns:
        None (sends Message response via ctx.send)
    
    Error Responses:
        - Invalid time format: "❌ Ungültige Zeit. Bitte HH:MM."
        - Invalid care period: "❌ betreuung_von/bis müssen HH:MM sein."
        - No dog capacity: "❌ Keine Hundekapazität mehr verfügbar."
        - No cat capacity: "❌ Keine Katzenkapazität mehr verfügbar."
        - Invalid pet type: "❌ Bitte 'Hund' oder 'Katze' angeben."
    
    Success Responses:
        - Dog: "🐶 Hundebetreuung reserviert!\n⏱️ {von} – {bis}"
        - Cat: "🐱 Katzenbetreuung reserviert!\n⏱️ {von} – {bis}"
    
    Notes:
        - Pet type matching is case-insensitive ("hund", "Hund", "HUND" all work)
        - Reservations are tracked in-memory (reset on agent restart)
        - Time must be in 24-hour "HH:MM" format
        - Capacity is decremented per reservation, not per hour
    """
    # Step 1: Determine client address for response routing
    # Uses client_sender if provided, otherwise falls back to direct sender
    client = msg.client_sender or sender

    # Step 2: Validate and parse request time format
    try:
        datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="haustier_fehler",
                message="❌ Ungültige Zeit. Bitte HH:MM.",
                zeit=msg.zeit
            )
        )
        return

    # Step 3: Validate and parse care period (start and end times)
    try:
        start = datetime.datetime.strptime(msg.betreuung_von, "%H:%M").time()
        ende = datetime.datetime.strptime(msg.betreuung_bis, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="haustier_fehler",
                message="❌ betreuung_von/bis müssen HH:MM sein.",
                zeit=msg.zeit
            )
        )
        return

    # Step 4: Normalize pet type for matching (case-insensitive)
    art = msg.haustierart.lower()

    # Step 5 & 6: Check capacity and process reservation based on pet type
    antwort = "❌ Es sind keine Plätze mehr frei."

    # Dog reservation logic
    if "hund" in art:
        if kapazitaet["hund"] > 0:
            # Reserve slot by decrementing available capacity
            kapazitaet["hund"] -= 1
            antwort = (
                f"🐶 Hundebetreuung reserviert!\n"
                f"⏱️ {msg.betreuung_von} – {msg.betreuung_bis}"
            )

        else:
            antwort = "❌ Keine Hundekapazität mehr verfügbar."

    # Cat reservation logic
    elif "katze" in art:
        if kapazitaet["katze"] > 0:
            # Reserve slot by decrementing available capacity
            kapazitaet["katze"] -= 1
            antwort = (
                f"🐱 Katzenbetreuung reserviert!\n"
                f"⏱️ {msg.betreuung_von} – {msg.betreuung_bis}"
            )

        else:
            antwort = "❌ Keine Katzenkapazität mehr verfügbar."

    # Invalid pet type
    else:
        antwort = "❌ Bitte 'Hund' oder 'Katze' angeben."

    # Send response to client
    await ctx.send(
        client,
        Message(
            type="haustier_bestaetigung",
            message=antwort,
            zeit=msg.zeit
        )
    )

    # Log the transaction for monitoring with current capacity status
    ctx.logger.info(
        f"Antwort an {client} gesendet | Hund={kapazitaet['hund']} | Katze={kapazitaet['katze']}"
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the Haustierbetreuung (pet care) agent.
    
    Starts the agent and displays connection information.
    The agent will listen for incoming HaustierMessage requests and process
    them according to the business logic defined above.
    
    Usage:
        python service_haustierbetreuung.py
    
    Console Output:
        🐾 Haustierbetreuung gestartet…
        📍 Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
    
    Sending a Request (from another agent):
        >>> await ctx.send(
        ...     "agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0",
        ...     HaustierMessage(
        ...         type="haustier_anfrage",
        ...         haustierart="Hund",
        ...         zeit="10:00",
        ...         betreuung_von="10:00",
        ...         betreuung_bis="18:00",
        ...         client_sender=ctx.agent.address
        ...     )
        ... )
    
    Limitations:
        - In-memory storage: Reservations and capacity reset on agent restart
        - No cancellation: Reservations cannot be cancelled once made
        - Global capacity: Total capacity shared, not per time slot
        - Two pet types only: Currently supports dogs and cats only
    """
    print("🐾 Haustierbetreuung gestartet…")
    print(f"📍 Adresse: {petHotelAgent.address}")
    petHotelAgent.run()
