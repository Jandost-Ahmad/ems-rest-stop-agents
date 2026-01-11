import datetime
from uagents import Model, Agent, Context


# =============================================================================
# DATA MODELS
# =============================================================================

class EssenMessage(Model):
    """
    Input model for meal reservation requests.
    
    Represents an incoming request to reserve a meal at a specific time.
    The agent processes this message and returns a confirmation or error.
    
    Attributes:
        type (str): Message type identifier (e.g., "essen_anfrage")
        zeit (str): Desired meal time in "HH:MM" format (24-hour)
        standard (int): Quantity of standard meals requested
        vegetarisch (int): Quantity of vegetarian meals requested
        vegan (int): Quantity of vegan meals requested
        glutenfrei (int): Quantity of gluten-free meals requested
        client_sender (str): Address of the originating client agent
    
    Example:
        >>> msg = EssenMessage(
        ...     type="essen_anfrage",
        ...     zeit="12:30",
        ...     standard=1,
        ...     vegetarisch=0,
        ...     vegan=0,
        ...     glutenfrei=0,
        ...     client_sender="agent1q2..."
        ... )
    """
    type: str
    zeit: str
    standard: int
    vegetarisch: int
    vegan: int
    glutenfrei: int
    client_sender: str


class Message(Model):
    """
    Output model for agent responses.
    
    Represents the agent's response to a meal reservation request,
    containing either a confirmation or an error message.
    
    Attributes:
        type (str): Response type identifier
                   - "essen_bestaetigung": Successful reservation
                   - "essen_fehler": Request error or rejection
        message (str): Human-readable confirmation or error message
        zeit (str): Echo of the requested time from the original request
    
    Example:
        >>> response = Message(
        ...     type="essen_bestaetigung",
        ...     message="🍽️ Gericht 'vegan' ist für 12:30 reserviert!",
        ...     zeit="12:30"
        ... )
    """
    type: str
    message: str
    zeit: str


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

essensserviceAgent = Agent(
    name="Essensservice",
    port=8007,
    seed="essensserviceAgent",
    endpoint=["http://localhost:8007/submit"],
)
"""
Main agent instance for the meal service.

Configuration:
    - name: "Essensservice" - Agent identifier for logging
    - port: 8007 - Network port for agent communication
    - seed: "essensserviceAgent" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""


# =============================================================================
# BUSINESS LOGIC CONFIGURATION
# =============================================================================

# Operating hours: Service available from 08:00 to 20:00 (8 AM to 8 PM)
oeffnung = datetime.time(8, 0)
schluss = datetime.time(20, 0)

# Capacity management: Maximum 60 meals can be reserved per hour
MAX_PRO_STUNDE = 60

# Hourly reservation tracking dictionary
# Keys: "08", "09", ..., "19" (operating hours)
# Values: Current number of reservations for that hour
bestellungen_pro_stunde = {str(h).zfill(2): 0 for h in range(oeffnung.hour, schluss.hour)}

# Available meal types in priority order
# When multiple meal types are requested, the first one with quantity > 0 is selected
gerichte = ["standard", "vegetarisch", "vegan", "glutenfrei"]


# =============================================================================
# MESSAGE HANDLER
# =============================================================================

@essensserviceAgent.on_message(model=EssenMessage)
async def essen_handler(ctx: Context, sender: str, msg: EssenMessage):
    """
    Main message handler for meal reservation requests.
    
    Processes incoming EssenMessage requests, validates the request parameters,
    checks availability, and sends back a confirmation or error message.
    
    Workflow:
        1. Client Identification: Determines the client address for response
        2. Time Validation: Parses and validates the requested time
        3. Operating Hours Check: Ensures request is within service hours
        4. Capacity Check: Verifies hourly reservation limit
        5. Meal Selection: Selects first available meal type
        6. Reservation: Records reservation and sends confirmation
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (EssenMessage): The incoming meal reservation request
    
    Returns:
        None (sends Message response via ctx.send)
    
    Error Responses:
        - Invalid time format: "❌ Ungültige Zeit (HH:MM erforderlich)."
        - Outside hours: "❌ Essensservice hat geschlossen. Öffnungszeiten 08:00–20:00."
        - Fully booked: "❌ Für {zeit} sind keine Gerichte mehr verfügbar."
        - No meal selected: "😔 Kein Gericht ausgewählt oder Gericht nicht verfügbar."
    
    Success Response:
        "🍽️ Gericht '{gericht}' ist für {zeit} reserviert!"
    
    Notes:
        - Only the first meal type with quantity > 0 is processed
        - Reservations are tracked in-memory (reset on agent restart)
        - Time must be in 24-hour "HH:MM" format
        - Hourly capacity is shared across all meal types
    """
    # Step 1: Determine client address for response routing
    # Uses client_sender if provided, otherwise falls back to direct sender
    client = msg.client_sender or sender

    # Step 2: Validate and parse time format
    try:
        zeit = datetime.datetime.strptime(msg.zeit, "%H:%M").time()
    except:
        await ctx.send(client, Message(
            type="essen_fehler",
            message="❌ Ungültige Zeit (HH:MM erforderlich).",
            zeit=msg.zeit
        ))
        return

    # Step 3: Check if requested time falls within operating hours
    if not (oeffnung <= zeit < schluss):
        await ctx.send(client, Message(
            type="essen_fehler",
            message=f"❌ Essensservice hat geschlossen. Öffnungszeiten {oeffnung.strftime('%H:%M')}–{schluss.strftime('%H:%M')}.",
            zeit=msg.zeit
        ))
        return

    # Extract hour for capacity tracking
    stunde = str(zeit.hour).zfill(2)

    # Step 4: Check if hourly capacity limit has been reached
    if bestellungen_pro_stunde[stunde] >= MAX_PRO_STUNDE:
        await ctx.send(client, Message(
            type="essen_fehler",
            message=f"❌ Für {msg.zeit} sind keine Gerichte mehr verfügbar.",
            zeit=msg.zeit
        ))
        return

    # Step 5: Select meal type (first one with quantity > 0)
    # Priority order: standard → vegetarisch → vegan → glutenfrei
    gewaehlt = None
    for gericht, menge in [
        ("standard", msg.standard),
        ("vegetarisch", msg.vegetarisch),
        ("vegan", msg.vegan),
        ("glutenfrei", msg.glutenfrei)
    ]:
        if menge > 0:
            gewaehlt = gericht
            break

    # Step 6: Process reservation or return error
    if not gewaehlt:
        antwort = "😔 Kein Gericht ausgewählt oder Gericht nicht verfügbar."
    else:
        # Increment hourly counter and create confirmation message
        bestellungen_pro_stunde[stunde] += 1
        antwort = f"🍽️ Gericht '{gewaehlt}' ist für {msg.zeit} reserviert!"

    # Send response to client
    await ctx.send(client, Message(
        type="essen_bestaetigung",
        message=antwort,
        zeit=msg.zeit
    ))

    # Log the transaction for monitoring
    ctx.logger.info(f"Essen bestätigt: {antwort}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the Essensservice agent.
    
    Starts the agent and displays connection information.
    The agent will listen for incoming EssenMessage requests and process
    them according to the business logic defined above.
    
    Usage:
        python essensservice_agent.py
    
    Console Output:
        🍽️ Essensservice gestartet…
        📍 Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
    
    Sending a Request (from another agent):
        >>> await ctx.send(
        ...     "agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0",
        ...     EssenMessage(
        ...         type="essen_anfrage",
        ...         zeit="14:30",
        ...         standard=0,
        ...         vegetarisch=1,
        ...         vegan=0,
        ...         glutenfrei=0,
        ...         client_sender=ctx.agent.address
        ...     )
        ... )
    
    Limitations:
        - In-memory storage: Reservations reset on agent restart
        - Single meal selection: Only first meal type with quantity > 0 is processed
        - No cancellation: Reservations cannot be cancelled once made
        - Shared capacity: Hourly limit applies to all meal types combined
    """
    print("🍽️ Essensservice gestartet…")
    print(f"📍 Adresse: {essensserviceAgent.address}")
    essensserviceAgent.run()