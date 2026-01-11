"""Wardrobe (cloakroom) service agent.

This module defines the `GarderobeAgent` which manages item storage and retrieval
using a QR code-based token system. Supports both digital and physical tokens.

- Capacity: 100 storage slots
- Token types: Digital (photo QR) or Physical (printed QR)
- Secure retrieval: QR code verification required
- Unique identifier: UUID-based QR codes

Workflow:
1. Check-in (Abgabe): Store item → Generate QR → Issue token
2. Check-out (Abholung): Scan QR → Verify → Return item

"""
import uuid
from uagents import Agent, Context, Model


# =============================================================================
# DATA MODELS
# =============================================================================

class GarderobeAbgabeRequest(Model):
    """
    Request model for item check-in (storage).
    
    Used when a customer wants to store an item in the wardrobe.
    The service assigns a slot, generates a QR code, and issues a token.
    
    Attributes:
        artikel (str): Description of the item being stored (e.g., "Jacke", "Rucksack")
        token_typ (str): Token format preference ("digital" or "physisch")
                        - "digital": Customer takes photo of QR on screen
                        - "physisch": QR code is printed on paper
        correlation_id (str): Request tracking ID for matching responses
    
    Example:
        >>> req = GarderobeAbgabeRequest(
        ...     artikel="Winterjacke",
        ...     token_typ="digital",
        ...     correlation_id="req-12345"
        ... )
    """
    artikel: str
    token_typ: str         # "digital" oder "physisch"
    correlation_id: str

class GarderobeAbgabeResponse(Model):
    """
    Response model for item check-in confirmation.
    
    Sent back to the client after storing an item, containing the QR code
    needed for later retrieval.
    
    Attributes:
        qr_code (str): Unique UUID-based QR code for item retrieval
                      (empty string if no slots available)
        info (str): Human-readable status message including:
                   - Slot assignment
                   - Token type confirmation
                   - Error messages if applicable
        correlation_id (str): Echo of the request correlation_id
    
    Example:
        >>> resp = GarderobeAbgabeResponse(
        ...     qr_code="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        ...     info="Artikel 'Jacke' in Fach 42 abgelegt.\n📷 Bitte machen Sie ein Foto!",
        ...     correlation_id="req-12345"
        ... )
    """
    qr_code: str
    info: str
    correlation_id: str

class GarderobeAbholungRequest(Model):
    """
    Request model for item retrieval (check-out).
    
    Used when a customer wants to retrieve a stored item using their QR token.
    
    Attributes:
        qr_code (str): UUID QR code from check-in token
        correlation_id (str): Request tracking ID for matching responses
    
    Example:
        >>> req = GarderobeAbholungRequest(
        ...     qr_code="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        ...     correlation_id="req-12346"
        ... )
    """
    qr_code: str
    correlation_id: str

class GarderobeAbholungResponse(Model):
    """
    Response model for item retrieval confirmation.
    
    Sent back to the client after verifying QR and releasing item.
    
    Attributes:
        artikel (str): Description of retrieved item (empty if QR invalid)
        info (str): Human-readable status message including:
                   - Item description
                   - Slot number
                   - Token type used
                   - Error messages if QR invalid
        correlation_id (str): Echo of the request correlation_id
    
    Example:
        >>> resp = GarderobeAbholungResponse(
        ...     artikel="Winterjacke",
        ...     info="Artikel 'Winterjacke' aus Fach 42 ausgegeben. Token war: digital",
        ...     correlation_id="req-12346"
        ... )
    """
    artikel: str
    info: str
    correlation_id: str


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

garderobe = Agent(
    name="GarderobeAgent",
    port=8006,
    seed="garderoben-seed",
    endpoint=["http://localhost:8006/submit"]
)
"""
Main agent instance for the wardrobe service.

Configuration:
    - name: "GarderobeAgent" - Agent identifier for logging
    - port: 8006 - Network port for agent communication
    - seed: "garderoben-seed" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""


# =============================================================================
# STORAGE MANAGEMENT
# =============================================================================

# Slot storage: Maps slot numbers to item data
# Structure: {slot_number: {artikel, qr, token_typ}}
slots = {}

# Maximum capacity of the wardrobe system
MAX_SLOTS = 100
"""
Storage capacity configuration.

slots (dict): Active storage mapping
    - Key: int (slot number 0-99)
    - Value: dict with:
        - "artikel": str (item description)
        - "qr": str (UUID for retrieval)
        - "token_typ": str ("digital" or "physisch")

MAX_SLOTS (int): Total number of available storage slots
"""


def freier_slot():
    """
    Find the first available (unoccupied) storage slot.
    
    Iterates through slot numbers from 0 to MAX_SLOTS-1 and returns
    the first number not currently in use.
    
    Returns:
        int or None: First available slot number, or None if all slots occupied
    
    Example:
        >>> slots = {0: {...}, 2: {...}}
        >>> freier_slot()
        1
    """
    for i in range(MAX_SLOTS):
        if i not in slots:
            return i
    return None


# =============================================================================
# MESSAGE HANDLERS
# =============================================================================

@garderobe.on_message(model=GarderobeAbgabeRequest)
async def handle_abgabe(ctx: Context, sender: str, msg: GarderobeAbgabeRequest):
    """
    Handle item check-in (Abgabe) requests.
    
    Processes incoming requests to store items, assigns available slots,
    generates unique QR codes, and issues appropriate tokens (digital or physical).
    
    Workflow:
        1. Check slot availability
        2. If full: Send error response
        3. If available:
           a. Assign slot
           b. Generate UUID-based QR code
           c. Store item data with QR and token type
           d. Compose token-specific instructions
           e. Send confirmation with QR code
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (GarderobeAbgabeRequest): Item check-in request with artikel and token_typ
    
    Returns:
        None (sends GarderobeAbgabeResponse via ctx.send)
    
    Success Response:
        - qr_code: UUID string (e.g., "a1b2c3d4-e5f6-...")
        - info: Confirmation with slot number and token instructions
    
    Error Response:
        - qr_code: "" (empty string)
        - info: "❌ Keine Plätze mehr frei"
    
    Token Types:
        - "digital": Customer takes photo of on-screen QR code
        - "physisch": QR code is printed on paper ticket
    
    Notes:
        - QR codes are UUIDs (unique per check-in)
        - Slot assignment is sequential (lowest available)
        - In-memory storage (resets on agent restart)
        - No expiration or time limits on storage
    """
    # Step 1: Check for available slot
    slot = freier_slot()
    
    # Step 2: Handle capacity full scenario
    if slot is None:
        await ctx.send(sender, GarderobeAbgabeResponse(
            qr_code="",
            info="❌ Keine Plätze mehr frei",
            correlation_id=msg.correlation_id
        ))
        return

    # Step 3a & 3b: Generate unique QR code (UUID)
    qr = str(uuid.uuid4())
    
    # Step 3c: Store item data in assigned slot
    slots[slot] = {
        "artikel": msg.artikel,
        "qr": qr,
        "token_typ": msg.token_typ
    }

    # Step 3d: Compose token-specific instructions
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

    # Step 3e: Send confirmation with QR code and instructions
    await ctx.send(sender, GarderobeAbgabeResponse(
        qr_code=qr,
        info=f"Artikel '{msg.artikel}' in Fach {slot} abgelegt.\n{token_info}",
        correlation_id=msg.correlation_id
    ))


@garderobe.on_message(model=GarderobeAbholungRequest)
async def handle_abholung(ctx: Context, sender: str, msg: GarderobeAbholungRequest):
    """
    Handle item retrieval (Abholung) requests.
    
    Processes incoming requests to retrieve stored items by verifying the QR code,
    locating the item, releasing the slot, and confirming retrieval.
    
    Workflow:
        1. Search all slots for matching QR code
        2. If found:
           a. Retrieve item and token type information
           b. Delete slot entry (release storage)
           c. Send success response with item details
        3. If not found:
           - Send error response (invalid QR)
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (GarderobeAbholungRequest): Retrieval request with qr_code
    
    Returns:
        None (sends GarderobeAbholungResponse via ctx.send)
    
    Success Response:
        - artikel: Item description from storage
        - info: Confirmation with slot number and token type
    
    Error Response:
        - artikel: "" (empty string)
        - info: "❌ Ungültiger QR-Code"
    
    Notes:
        - QR code must match exactly (case-sensitive UUID)
        - Slot is immediately freed after successful retrieval
        - Each QR code can only be used once
        - No partial matches or fuzzy search
        - Linear search through all slots (O(n) complexity)
    """
    # Step 1: Search for matching QR code in all slots
    for slot, data in list(slots.items()):
        if data["qr"] == msg.qr_code:
            # Step 2a: Retrieve item information
            artikel = data["artikel"]
            token_typ = data["token_typ"]
            
            # Step 2b: Release the slot (delete entry)
            del slots[slot]

            # Step 2c: Send success response
            await ctx.send(sender, GarderobeAbholungResponse(
                artikel=artikel,
                info=f"Artikel '{artikel}' aus Fach {slot} ausgegeben. Token war: {token_typ}",
                correlation_id=msg.correlation_id
            ))
            return

    # Step 3: QR code not found in any slot
    await ctx.send(sender, GarderobeAbholungResponse(
        artikel="",
        info="❌ Ungültiger QR-Code",
        correlation_id=msg.correlation_id
    ))


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the GarderobeAgent (wardrobe service).
    
    Starts the wardrobe/cloakroom service and displays connection information.
    Manages item storage and retrieval with QR code-based tokens.
    
    Usage:
        python service_garderobe.py
    
    Console Output:
        ============================================================
        🧥 GARDEROBE-SERVICE GESTARTET
        ============================================================
        📍 Agent-Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
        🌐 Endpoint: http://localhost:8006/submit
        ============================================================
    
    Features:
        - 100 storage slots
        - UUID-based QR codes
        - Digital and physical token support
        - Secure retrieval verification
        - Automatic slot management
        - Correlation ID tracking
    
    Workflow:
        Check-in:  Customer → Store item → Get QR token
        Check-out: Customer → Present QR → Retrieve item
    
    Limitations:
        - In-memory storage: Data lost on restart
        - No expiration: Items stored indefinitely
        - No duplicate detection: Same item can be stored multiple times
        - Linear search: Performance degrades with many items
    """
    print("=" * 60)
    print("🧥 GARDEROBE-SERVICE GESTARTET")
    print("=" * 60)
    print(f"📍 Agent-Adresse: {garderobe.address}")
    print(f"🌐 Endpoint: http://localhost:8006/submit")
    print("=" * 60)
    print()
    garderobe.run()
