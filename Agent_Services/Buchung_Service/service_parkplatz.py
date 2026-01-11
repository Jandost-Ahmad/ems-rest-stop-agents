"""Parking space reservation service agent.

This module defines the `ParkplatzService` agent which processes parking
space reservation requests (`ParkplatzMessage`) and responds with
confirmations or error messages (`Message`).

- Vehicle types: PKW (car), LKW (truck), BUS
- Supports charging stations and accessibility requirements
- Reservation tracking with expiration and reminder system
- Fallback allocation when primary capacity is full

Capacity:
- Cars (PKW): 100 total (50 with charging)
- Trucks (LKW): 300 total (with charging)
- Buses (BUS): 3 total (with charging)
- Accessibility spots: 2% of each category

"""
from uagents import Agent, Context, Model
import uuid
from datetime import datetime, timedelta
import re


# ============================================================
#                     DATA MODELS
# ============================================================

class ParkplatzMessage(Model):
    """
    Input model for parking space reservation requests.
    
    Represents an incoming request to reserve a parking space for a specific
    vehicle type, optionally with charging station and accessibility needs.
    
    Attributes:
        type (str): Message type identifier (e.g., "parkplatz_anfrage")
        fahrzeugart (str): Vehicle type ("PKW", "LKW", "BUS", optionally "behindert")
        ladestation (bool): Whether a charging station is required
        zeit (str): Reservation duration in minutes (digits) or end time ("HH:MM")
        reservation_id (str): Optional existing reservation ID
        client_sender (str): Address of the originating client agent
    
    Example:
        >>> msg = ParkplatzMessage(
        ...     type="parkplatz_anfrage",
        ...     fahrzeugart="PKW",
        ...     ladestation=True,
        ...     zeit="120",  # 120 minutes
        ...     reservation_id="",
        ...     client_sender="agent1q2..."
        ... )
    """
    type: str
    fahrzeugart: str
    ladestation: bool
    zeit: str
    reservation_id: str
    client_sender: str


class Message(Model):
    """
    Output model for agent responses.
    
    Represents the agent's response to a parking reservation request,
    containing either a confirmation with reservation ID or an error message.
    
    Attributes:
        type (str): Response type identifier
                   - "parkplatz_bestaetigung": Successful reservation
                   - "parkplatz_reminder": Reservation expiring soon
                   - "parkplatz_abgelaufen": Reservation expired
        message (str): Human-readable confirmation or error message
        zeit (str): Time associated with the reservation
    
    Example:
        >>> response = Message(
        ...     type="parkplatz_bestaetigung",
        ...     message="🚗 PKW-Parkplatz reserviert. (RID=abc12345)",
        ...     zeit="14:30"
        ... )
    """
    type: str
    message: str
    zeit: str


# ============================================================
#                     AGENT CONFIGURATION
# ============================================================

parkplatzAgent = Agent(
    name="ParkplatzService",
    port=8001,
    seed="parkplatzAgent",
    endpoint=["http://localhost:8001/submit"],
)
"""
Main agent instance for the parking service.

Configuration:
    - name: "ParkplatzService" - Agent identifier for logging
    - port: 8001 - Network port for agent communication
    - seed: "parkplatzAgent" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""

print("=" * 60)
print("🚗 PARKPLATZ-SERVICE GESTARTET")
print("=" * 60)
print(f"📍 Agent-Adresse: {parkplatzAgent.address}")
print(f"🌐 Endpoint: http://localhost:8001/submit")
print("=" * 60)
print()


# ============================================================
#                     PARKING CAPACITY CONFIGURATION
# ============================================================
"""
Capacity allocation and management for different vehicle types.

Initial Capacity:
- PKW (cars): 100 total spaces
  - 50 with charging stations
  - 2% reserved for accessibility (calculated from total)
- LKW (trucks): 300 total spaces (all with charging capability)
  - 2% reserved for accessibility
- BUS: 3 total spaces (all with charging capability)

Accessibility Allocation:
- Calculated as 2% of base capacity per category
- Minimum 1 spot per accessibility category
- Separate tracking for charging vs. non-charging accessible spots

Fallback Logic:
- LKW can use BUS spots if LKW capacity is full
- LKW can use 3 PKW spots if both LKW and BUS are full
- Accessible vehicles can use regular spots if accessible spots are full
"""

# Base capacity constants
pkw_total = 100
pkw_lade_total = 50
lkw_total = 300
bus_total = 3


def two_percent(x):
    """
    Calculate 2% of capacity for accessibility allocation.
    
    Args:
        x (int): Total capacity for a vehicle type
    
    Returns:
        int: Number of accessible spots (minimum 1)
    """
    return max(1, round(x * 0.02))


# Calculate accessibility spots (2% of each category)
behindert_pkw_ohne_lade = two_percent(pkw_total - pkw_lade_total)
behindert_pkw_mit_lade = two_percent(pkw_lade_total)
behindert_lkw_mit_lade = two_percent(lkw_total)

# Calculate remaining regular capacity after reserving accessibility spots
pkw_rest = pkw_total - behindert_pkw_ohne_lade - behindert_pkw_mit_lade
pkw_lade = pkw_lade_total - behindert_pkw_mit_lade
pkw_frei = pkw_rest - pkw_lade

# LKW capacity after accessibility allocation
lkw_lade = lkw_total - behindert_lkw_mit_lade

# BUS capacity (all spots have charging)
bus_lade = bus_total

# Main capacity tracking dictionary
# Structure: {vehicle_type: {"frei": non_charging, "lade": charging}}
parkplatz_status = {
    "PKW": {"frei": pkw_frei, "lade": pkw_lade},
    "PKW_Behindert": {"frei": behindert_pkw_ohne_lade, "lade": behindert_pkw_mit_lade},
    "LKW": {"lade": lkw_lade},
    "LKW_Behindert": {"lade": behindert_lkw_mit_lade},
    "BUS": {"lade": bus_lade}
}



# ============================================================
#                     RESERVATION TRACKING
# ============================================================
"""
Active reservation storage.

Structure: {reservation_id: {sender, end, reminder_sent}}
- reservation_id: 8-character UUID identifier
- sender: Client agent address for notifications
- end: datetime object when reservation expires
- reminder_sent: bool flag to prevent duplicate reminders
"""
reservations = {}


# ============================================================
#                     HELPER FUNCTIONS
# ============================================================

def parse_time_field(zeit_str: str):
    """
    Parse time field to calculate reservation end time.
    
    Supports two formats:
    1. "HH:MM" - Absolute time (if past, assumes next day)
    2. Digits only - Duration in minutes from now
    
    Args:
        zeit_str (str): Time string from request
    
    Returns:
        datetime or None: Calculated end time, or None if invalid
    
    Examples:
        >>> parse_time_field("14:30")  # Absolute time
        datetime(2026, 1, 11, 14, 30)
        >>> parse_time_field("120")    # 120 minutes from now
        datetime(2026, 1, 11, 12, 30)
    """
    if not zeit_str:
        return None
    zeit_str = zeit_str.strip()
    # Try parsing HH:MM format
    hhmm = re.match(r"^(\d{1,2}):(\d{2})$", zeit_str)
    if hhmm:
        h, m = int(hhmm.group(1)), int(hhmm.group(2))
        now = datetime.now()
        end = now.replace(hour=h, minute=m, second=0, microsecond=0)
        # If time has passed today, assume tomorrow
        if end <= now:
            end += timedelta(days=1)
        return end
    # Try parsing duration in minutes
    if zeit_str.isdigit():
        return datetime.now() + timedelta(minutes=int(zeit_str))
    return None


def total_pkw_available():
    """
    Get total available PKW capacity (charging + non-charging).
    
    Returns:
        int: Total number of available car parking spots
    """
    return parkplatz_status["PKW"]["frei"] + parkplatz_status["PKW"]["lade"]


def consume_pkw_slots(n: int):
    """
    Consume n PKW parking slots, prioritizing non-charging spots.
    
    Decrements capacity from non-charging spots first, then charging spots.
    
    Args:
        n (int): Number of slots to consume
    
    Returns:
        int: Actual number of slots consumed (may be less if insufficient)
    """
    consumed = 0
    # First consume non-charging spots
    take = min(n, parkplatz_status["PKW"]["frei"])
    parkplatz_status["PKW"]["frei"] -= take
    consumed += take
    rest = n - consumed
    # Then consume charging spots if needed
    if rest > 0:
        take2 = min(rest, parkplatz_status["PKW"]["lade"])
        parkplatz_status["PKW"]["lade"] -= take2
        consumed += take2
    return consumed


def try_allocate_lkw():
    """
    Attempt to allocate an LKW (truck) parking spot with fallback logic.
    
    Tries in order:
    1. Regular LKW charging spot
    2. BUS spot (if LKW full)
    3. 3x PKW spots (if both LKW and BUS full)
    
    Returns:
        tuple: (success: bool, message: str or None)
    """
    # Try regular LKW spot
    if parkplatz_status["LKW"]["lade"] > 0:
        parkplatz_status["LKW"]["lade"] -= 1
        return True, "🚚🔌 LKW-Ladeparkplatz reserviert."
    # Fallback to BUS spot
    if parkplatz_status.get("BUS", {}).get("lade", 0) > 0:
        parkplatz_status["BUS"]["lade"] -= 1
        return True, "🚚 (Fallback) Bus-Parkplatz für LKW reserviert."
    # Fallback to 3 PKW spots
    if total_pkw_available() >= 3 and consume_pkw_slots(3) == 3:
        return True, "🚚 (Fallback) 3× PKW → LKW-Platz reserviert."
    return False, None


# ============================================================
#                     MAIN MESSAGE HANDLER
# ============================================================

@parkplatzAgent.on_message(model=ParkplatzMessage)
async def parkplatz_handler(ctx: Context, sender: str, msg: ParkplatzMessage):
    """
    Main message handler for parking space reservation requests.
    
    Processes incoming ParkplatzMessage requests with complex allocation logic
    including accessibility requirements, charging station needs, and fallback
    strategies when primary capacity is exhausted.
    
    Workflow:
        1. Client Identification: Determines the client address for response
        2. Vehicle Type Check: Parses vehicle type and accessibility flags
        3. Capacity Check: Verifies availability based on vehicle type and requirements
        4. Fallback Allocation: Attempts alternative allocations if primary is full
        5. Reservation: Creates reservation ID and tracks expiration
        6. Confirmation: Sends response with reservation details
    
    Vehicle Type Matching (case-insensitive):
        - "PKW" or "pkw" → Car parking
        - "PKW behindert" → Accessible car parking
        - "LKW" or "lkw" → Truck parking
        - "LKW behindert" → Accessible truck parking
        - "BUS" or "bus" → Bus parking
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (ParkplatzMessage): The incoming parking reservation request
    
    Returns:
        None (sends Message response via ctx.send)
    
    Success Responses:
        - Car: "🚗 PKW-Parkplatz reserviert. (RID=xxxxxxxx)"
        - Car charging: "🔌🚗 PKW-Ladeparkplatz reserviert. (RID=xxxxxxxx)"
        - Accessible car: "♿ PKW-Behindertenparkplatz reserviert. (RID=xxxxxxxx)"
        - Truck: "🚚🔌 LKW-Ladeparkplatz reserviert. (RID=xxxxxxxx)"
        - Bus: "🚌🔌 Bus-Parkplatz reserviert. (RID=xxxxxxxx)"
        - Fallbacks: Include "(Fallback)" prefix in message
    
    Error Response:
        "❌ Kein geeigneter Parkplatz verfügbar."
    
    Notes:
        - Generates 8-character UUID for each reservation
        - Tracks reservation expiration based on zeit field
        - Supports both duration (minutes) and absolute time (HH:MM)
        - Fallback logic prioritizes resource efficiency
    """
    # Step 1: Parse vehicle type and identify client
    fahrzeugart = msg.fahrzeugart.lower()
    lade = bool(msg.ladestation)
    client = msg.client_sender or sender

    # Step 2 & 3 & 4: Initialize response and process by vehicle type
    antwort = "❌ Kein geeigneter Parkplatz verfügbar."
    rid = None

    # ============================================================
    #               PKW BEHINDERT (Accessible Car Parking)
    # ============================================================
    if "pkw" in fahrzeugart and "behindert" in fahrzeugart:

        # Try accessible spot with charging
        if lade and parkplatz_status["PKW_Behindert"]["lade"] > 0:
            parkplatz_status["PKW_Behindert"]["lade"] -= 1
            antwort = "♿🔌 Behinderten-PKW-Ladeparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

        # Try accessible spot without charging
        elif not lade and parkplatz_status["PKW_Behindert"]["frei"] > 0:
            parkplatz_status["PKW_Behindert"]["frei"] -= 1
            antwort = "♿ PKW-Behindertenparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

        # Fallback: Use 2 regular PKW spots for accessible vehicle
        elif total_pkw_available() >= 2 and consume_pkw_slots(2) == 2:
            antwort = "♿ (Fallback) 2× PKW → Behindertenplatz reserviert."
            rid = str(uuid.uuid4())[:8]


    # ============================================================
    #               PKW NORMAL (Regular Car Parking)
    # ============================================================
    elif "pkw" in fahrzeugart:

        # Try charging spot
        if lade and parkplatz_status["PKW"]["lade"] > 0:
            parkplatz_status["PKW"]["lade"] -= 1
            antwort = "🔌🚗 PKW-Ladeparkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

        # Try non-charging spot
        elif not lade and parkplatz_status["PKW"]["frei"] > 0:
            parkplatz_status["PKW"]["frei"] -= 1
            antwort = "🚗 PKW-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]


    # ============================================================
    #               LKW BEHINDERT (Accessible Truck Parking)
    # ============================================================
    elif "lkw" in fahrzeugart and "behindert" in fahrzeugart:

        # Try accessible LKW spot
        if parkplatz_status["LKW_Behindert"]["lade"] > 0:
            parkplatz_status["LKW_Behindert"]["lade"] -= 1
            antwort = "♿🚚🔌 Behinderten-LKW-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]

        # Fallback: Try regular LKW allocation
        else:
            ok, msg2 = try_allocate_lkw()
            if ok:
                antwort = "♿🚚 (Fallback) " + msg2
                rid = str(uuid.uuid4())[:8]


    # ============================================================
    #               LKW NORMAL (Regular Truck Parking)
    # ============================================================
    elif "lkw" in fahrzeugart:

        # Use helper function with fallback logic
        ok, msg2 = try_allocate_lkw()
        if ok:
            antwort = msg2
            rid = str(uuid.uuid4())[:8]


    # ============================================================
    #               BUS (Bus Parking)
    # ============================================================
    elif "bus" in fahrzeugart:

        if parkplatz_status["BUS"]["lade"] > 0:
            parkplatz_status["BUS"]["lade"] -= 1
            antwort = "🚌🔌 Bus-Parkplatz reserviert."
            rid = str(uuid.uuid4())[:8]


    # ============================================================
    #              SEND RESPONSE BACK TO CLIENT
    # ============================================================
    # Step 5: Send confirmation or error message with reservation ID
    await ctx.send(
        client,
        Message(
            type="parkplatz_bestaetigung",
            message=antwort + (f" (RID={rid})" if rid else ""),
            zeit=msg.zeit
        )
    )

    # Log transaction with reservation details
    ctx.logger.info(
        f"[Parkplatz] Gesendet an {client} | Antwort: '{antwort}' | RID={rid or '-'}"
    )

    # ============================================================
    #              SAVE RESERVATION IF VALID
    # ============================================================
    # Step 6: Track reservation for expiration and reminder system
    if rid:
        # Parse time field or default to 60 minutes
        end_dt = parse_time_field(msg.zeit) or (datetime.now() + timedelta(minutes=60))
        reservations[rid] = {
            "sender": client,
            "end": end_dt,
            "reminder_sent": False
        }


# ============================================================
#             RESERVATION MAINTENANCE LOOP
# ============================================================

@parkplatzAgent.on_interval(period=30.0)
async def reservation_maintenance(ctx: Context):
    """
    Background task for reservation expiration and reminder management.
    
    Runs every 30 seconds to:
    1. Send reminders 5 minutes before expiration
    2. Clean up expired reservations
    3. Notify clients of expired reservations
    
    Reminder Logic:
        - Sent once per reservation when 5 minutes or less remain
        - Prevents duplicate reminders using reminder_sent flag
    
    Expiration Logic:
        - Removes expired reservations from tracking
        - Sends expiration notification to client
        - Note: Does not automatically restore parking capacity
    
    Args:
        ctx (Context): Agent context for sending messages and logging
    
    Returns:
        None
    """
    REMINDER_MINUTES = 5
    now = datetime.now()
    expired = []

    # Check all active reservations
    for rid, r in reservations.items():
        end = r["end"]

        # Send reminder if within 5 minutes of expiration
        if not r["reminder_sent"] and now + timedelta(minutes=REMINDER_MINUTES) >= end > now:
            await ctx.send(
                r["sender"],
                Message(type="parkplatz_reminder",
                        message=f"⏰ Ihre Reservierung {rid} läuft um {end.strftime('%H:%M')} ab.",
                        zeit=end.strftime("%H:%M"))
            )
            r["reminder_sent"] = True

        # Mark for deletion if expired
        if now >= end:
            expired.append(rid)

    # Clean up expired reservations
    for rid in expired:
        data = reservations.pop(rid)
        await ctx.send(
            data["sender"],
            Message(type="parkplatz_abgelaufen",
                    message=f"❗ Ihre Reservierung {rid} ist abgelaufen und wurde freigegeben.",
                    zeit=datetime.now().strftime("%H:%M"))
        )


# ============================================================
#                     MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    """
    Main entry point for the ParkplatzService agent.
    
    Starts the agent with detailed startup information including:
    - Agent address for communication
    - HTTP endpoint for message submission
    - Background maintenance task for reservation management
    
    Usage:
        python service_parkplatz.py
    
    Console Output:
        ============================================================
        🚗 PARKPLATZ-SERVICE GESTARTET
        ============================================================
        📍 Agent-Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
        🌐 Endpoint: http://localhost:8001/submit
        ============================================================
    
    Features:
        - Multi-vehicle support: Cars, trucks, buses
        - Accessibility compliance: 2% capacity per category
        - Charging station management
        - Intelligent fallback allocation
        - Automatic expiration and reminders
        - Reservation tracking with unique IDs
    """
    parkplatzAgent.run()
