"""Hotel room booking service agent.

This module defines the `HotelService` agent which processes hotel room
reservation requests (`HotelMessage`) and responds with confirmations or
error messages (`Message`).

- Room types: single (Einzel), double (Doppel), family (Familie)
- Single room capacity: 20 rooms
- Double room capacity: 10 rooms
- Family room capacity: 5 rooms

"""
from uagents import Agent, Context, Model
import datetime


# =============================================================================
# DATA MODELS
# =============================================================================

class HotelMessage(Model):
    """
    Input model for hotel room reservation requests.
    
    Represents an incoming request to reserve a hotel room for a specific
    number of nights. The agent processes this message and returns a
    confirmation or error.
    
    Attributes:
        type (str): Message type identifier (e.g., "hotel_anfrage")
        zimmerart (str): Type of room requested ("Einzel", "Doppel", "Familie")
        zeit (str): Request time in "HH:MM" format (24-hour)
        naechte (int): Number of nights to book
        client_sender (str): Address of the originating client agent
    
    Example:
        >>> msg = HotelMessage(
        ...     type="hotel_anfrage",
        ...     zimmerart="Doppel",
        ...     zeit="15:00",
        ...     naechte=2,
        ...     client_sender="agent1q2..."
        ... )
    """
    type: str
    zimmerart: str
    zeit: str
    naechte: int
    client_sender: str


# ---------- Antwortmodell ----------
class Message(Model):
    """
    Output model for agent responses.
    
    Represents the agent's response to a hotel room reservation request,
    containing either a confirmation or an error message.
    
    Attributes:
        type (str): Response type identifier
                   - "hotel_bestaetigung": Successful reservation
                   - "hotel_fehler": Request error or rejection
        message (str): Human-readable confirmation or error message
        zeit (str): Echo of the requested time from the original request
    
    Example:
        >>> response = Message(
        ...     type="hotel_bestaetigung",
        ...     message="🏨 Doppelzimmer gebucht für 2 Nacht/Nächte.",
        ...     zeit="15:00"
        ... )
    """
    type: str
    message: str
    zeit: str


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

hotelAgent = Agent(
    name="HotelService",
    port=8009,
    seed="hotelServiceAgent",
    endpoint=["http://localhost:8009/submit"],
)
"""
Main agent instance for the hotel service.

Configuration:
    - name: "HotelService" - Agent identifier for logging
    - port: 8009 - Network port for agent communication
    - seed: "hotelServiceAgent" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""


# =============================================================================
# BUSINESS LOGIC CONFIGURATION
# =============================================================================

# Room capacity management: Available rooms per type
# - Single rooms: 20 available
# - Double rooms: 10 available
# - Family rooms: 5 available
# Note: Capacity decrements with each booking and persists until agent restart
zimmer = {
    "einzel": 20,
    "doppel": 10,
    "familie": 5
}



# =============================================================================
# MESSAGE HANDLER
# =============================================================================

@hotelAgent.on_message(model=HotelMessage)
async def hotel_handler(ctx: Context, sender: str, msg: HotelMessage):
    """
    Main message handler for hotel room reservation requests.
    
    Processes incoming HotelMessage requests, validates the request parameters,
    checks room availability, and sends back a confirmation or error message.
    
    Workflow:
        1. Client Identification: Determines the client address for response
        2. Time Validation: Parses and validates the requested time
        3. Room Type Check: Identifies room type (single/double/family)
        4. Availability Check: Verifies capacity for the requested room type
        5. Reservation: Records booking and sends confirmation
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (HotelMessage): The incoming hotel room reservation request
    
    Returns:
        None (sends Message response via ctx.send)
    
    Error Responses:
        - Invalid time format: "❌ Ungültige Zeit. Bitte HH:MM."
        - No rooms available: "❌ Kein geeignetes Zimmer verfügbar."
    
    Success Responses:
        - Single: "🏨 Einzelzimmer gebucht für {n} Nacht/Nächte."
        - Double: "🏨 Doppelzimmer gebucht für {n} Nacht/Nächte."
        - Family: "🏨 Familienzimmer gebucht für {n} Nacht/Nächte."
    
    Notes:
        - Room type matching is case-insensitive
        - Bookings are tracked in-memory (reset on agent restart)
        - Time must be in 24-hour "HH:MM" format
        - Each booking consumes one room of the specified type
    """
    # msg IST bereits ein HotelMessage → KEIN dict!
    hotel_msg = msg

    # Step 1: Determine client address for response routing
    # Uses client_sender if provided, otherwise falls back to direct sender
    client = hotel_msg.client_sender or sender

    # Step 2: Validate and parse request time format
    try:
        datetime.datetime.strptime(hotel_msg.zeit, "%H:%M").time()
    except:
        await ctx.send(
            client,
            Message(
                type="hotel_fehler",
                message="❌ Ungültige Zeit. Bitte HH:MM.",
                zeit=hotel_msg.zeit
            )
        )
        return

    # Step 3 & 4 & 5: Check room type and availability, then process booking
    antwort_text = "❌ Kein geeignetes Zimmer verfügbar."

    # Normalize room type for matching (case-insensitive)
    z = hotel_msg.zimmerart.lower()

    # Single room booking
    if "einzel" in z and zimmer["einzel"] > 0:
        zimmer["einzel"] -= 1
        antwort_text = f"🏨 Einzelzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    # Double room booking
    elif "doppel" in z and zimmer["doppel"] > 0:
        zimmer["doppel"] -= 1
        antwort_text = f"🏨 Doppelzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    # Family room booking
    elif ("familie" in z or "familien" in z) and zimmer["familie"] > 0:
        zimmer["familie"] -= 1
        antwort_text = f"🏨 Familienzimmer gebucht für {hotel_msg.naechte} Nacht/Nächte."

    # Send response to client
    await ctx.send(
        client,
        Message(
            type="hotel_bestaetigung",
            message=antwort_text,
            zeit=hotel_msg.zeit
        )
    )

    # Log the transaction for monitoring with current room status
    ctx.logger.info(f"Antwort an {client} gesendet. Zimmerstatus: {zimmer}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the HotelService agent.
    
    Starts the agent and displays connection information.
    The agent will listen for incoming HotelMessage requests and process
    them according to the business logic defined above.
    
    Usage:
        python service_hotel.py
    
    Console Output:
        🏨 Hotel-Service gestartet…
        📍 Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
    
    Sending a Request (from another agent):
        >>> await ctx.send(
        ...     "agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0",
        ...     HotelMessage(
        ...         type="hotel_anfrage",
        ...         zimmerart="Doppel",
        ...         zeit="15:00",
        ...         naechte=2,
        ...         client_sender=ctx.agent.address
        ...     )
        ... )
    
    Limitations:
        - In-memory storage: Bookings and capacity reset on agent restart
        - No cancellation: Bookings cannot be cancelled once made
        - Global capacity: Total capacity shared, not per time slot
        - Three room types only: Single, double, and family rooms
    """
    print("🏨 Hotel-Service gestartet…")
    print(f"📍 Adresse: {hotelAgent.address}")
    hotelAgent.run()
