"""Central routing service agent.

This module defines the `CentralService` agent which acts as a message router,
receiving batched service requests (`CentralServiceMessage`) and forwarding
them to the appropriate specialized service agents.

- Acts as single entry point for all service requests
- Routes messages to: Essen, Kaffee, Haustier, Hotel, Parkplatz services
- Handles message reconstruction and validation
- Batch processing support for multiple requests

Service Endpoints:
- Essensservice (port 8007): Meal reservations
- Kaffee (port 8008): Coffee orders
- Haustierbetreuung (port 8010): Pet care
- Hotel (port 8009): Room bookings
- Parkplatz (port 8001): Parking reservations

"""
from uagents import Agent, Context, Model
from typing import List


# =============================================================================
# DATA MODELS - Service-Specific Messages
# =============================================================================
"""
These models MUST match exactly with the specialized service agents.
Any changes here should be synchronized with the respective service files.
"""

class EssenMessage(Model):
    """
    Message model for meal service requests.
    
    Attributes:
        type (str): Message type ("essensservice")
        zeit (str): Meal time in HH:MM format
        standard (int): Quantity of standard meals
        vegetarisch (int): Quantity of vegetarian meals
        vegan (int): Quantity of vegan meals
        glutenfrei (int): Quantity of gluten-free meals
        client_sender (str): Originating client address
    """
    type: str
    zeit: str
    standard: int
    vegetarisch: int
    vegan: int
    glutenfrei: int
    client_sender: str

class KaffeeMessage(Model):
    """
    Message model for coffee service requests.
    
    Attributes:
        type (str): Message type ("kaffee")
        zeit (str): Order time in HH:MM format
        client_sender (str): Originating client address
    """
    type: str
    zeit: str
    client_sender: str

class HaustierMessage(Model):
    """
    Message model for pet care service requests.
    
    Attributes:
        type (str): Message type ("haustierbetreuung")
        haustierart (str): Pet type ("Hund" or "Katze")
        zeit (str): Request time in HH:MM format
        betreuung_von (str): Care start time in HH:MM format
        betreuung_bis (str): Care end time in HH:MM format
        client_sender (str): Originating client address
    """
    type: str
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str

class HotelMessage(Model):
    """
    Message model for hotel service requests.
    
    Attributes:
        type (str): Message type ("hotel")
        zimmerart (str): Room type ("Einzel", "Doppel", "Familie")
        zeit (str): Request time in HH:MM format
        naechte (int): Number of nights
        client_sender (str): Originating client address
    """
    type: str
    zimmerart: str
    zeit: str
    naechte: int
    client_sender: str

class ParkplatzMessage(Model):
    """
    Message model for parking service requests.
    
    Attributes:
        type (str): Message type ("parkplatz")
        fahrzeugart (str): Vehicle type ("PKW", "LKW", "BUS")
        ladestation (bool): Charging station required
        zeit (str): Reservation duration or end time
        reservation_id (str): Optional existing reservation ID
        client_sender (str): Originating client address
    """
    type: str
    fahrzeugart: str
    ladestation: bool
    zeit: str
    reservation_id: str
    client_sender: str


# =============================================================================
# CENTRAL SERVICE MESSAGE
# =============================================================================

class CentralServiceMessage(Model):
    """
    Batch message container for the central routing service.
    
    Accepts multiple service requests in a single message and routes each
    to the appropriate specialized service agent.
    
    Attributes:
        messages (list): List of dictionaries, each representing a service request.
                        Each dict must contain a "type" field matching one of the
                        registered service types.
    
    Example:
        >>> msg = CentralServiceMessage(
        ...     messages=[
        ...         {
        ...             "type": "kaffee",
        ...             "zeit": "09:30",
        ...             "client_sender": "agent1q2..."
        ...         },
        ...         {
        ...             "type": "essensservice",
        ...             "zeit": "12:00",
        ...             "standard": 1,
        ...             "vegetarisch": 0,
        ...             "vegan": 0,
        ...             "glutenfrei": 0,
        ...             "client_sender": "agent1q2..."
        ...         }
        ...     ]
        ... )
    """
    messages: list   # Liste aus dicts


# =============================================================================
# ROUTING CONFIGURATION
# =============================================================================

# Model factory: Maps service type to corresponding Model class
# Used for reconstructing typed messages from dict entries
model_factory = {
    "essensservice": EssenMessage,
    "kaffee": KaffeeMessage,
    "haustierbetreuung": HaustierMessage,
    "hotel": HotelMessage,
    "parkplatz": ParkplatzMessage,
}
"""
Model factory registry.

Maps message type strings to their corresponding Model constructors.
Enables dynamic message reconstruction from generic dictionaries.
"""

# Service address map: Routes message types to agent addresses
# NOTE: These addresses are generated deterministically from seeds.
# Update these if service agents are restarted with different seeds.
service_map = {
    "essensservice": "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5",
    "kaffee": "test-agent://agent1q2u5pp8cuq0fdzrh94842mu6scwyfv9ese0amr872t0xmdy9mfdncedjv7l",
    "haustierbetreuung": "test-agent://agent1qffjvchcs36qed3ghwng43l9zw4x3pefxck3t8rsdsakkaww9trpwyh9qx0",
    "hotel": "test-agent://agent1q2ar07qp4r8kale8pz2w5paefx90lf8w8z05xuja43rrwc75mw5j2s6e0zj",
    "parkplatz": "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9",
}
"""
Service routing table.

Maps message types to their destination agent addresses.
These addresses are deterministically generated from agent seeds.

IMPORTANT: Verify these addresses match your running service agents.
If services use different seeds, update these addresses accordingly.
"""


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

central = Agent(
    name="CentralService",
    port=8000,
    seed="centralservice",
    endpoint=["http://localhost:8000/submit"]
)
"""
Main agent instance for the central routing service.

Configuration:
    - name: "CentralService" - Agent identifier for logging
    - port: 8000 - Network port for agent communication (primary entry point)
    - seed: "centralservice" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

This is the main entry point for all client applications (GUI, voice assistant).
"""


# =============================================================================
# MESSAGE HANDLER - Routing Logic
# =============================================================================

@central.on_message(model=CentralServiceMessage)
async def handle(ctx: Context, sender: str, msg: CentralServiceMessage):
    """
    Main message handler for routing service requests.
    
    Receives batched service requests, validates message types, reconstructs
    typed messages from dictionaries, and forwards each to the appropriate
    specialized service agent.
    
    Workflow:
        1. Log batch receipt with count and sender
        2. For each message in batch:
           a. Extract message type from dict
           b. Look up target service address
           c. Look up model constructor
           d. Reconstruct typed message from dict
           e. Forward to target service
        3. Handle errors gracefully (unknown types, construction failures)
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender (typically GUI or voice client)
        msg (CentralServiceMessage): Batch message containing list of service requests
    
    Returns:
        None (forwards messages to specialized services)
    
    Error Handling:
        - Unknown message type: Logs error, skips message, continues batch
        - Missing model constructor: Logs error, skips message
        - Construction failure: Logs exception, skips message
        - No exceptions propagate to caller
    
    Notes:
        - Processes all messages in batch regardless of individual failures
        - Responses come directly from specialized services, not via central
        - Each message is independent; one failure doesn't affect others
        - Supports heterogeneous batches (mixed service types)
    
    Example Message Flow:
        Client → CentralService → EssensService → Client
                                ↘ KaffeeService → Client
    """
    # Step 1: Log receipt of batch message
    print(f"\n📨 [Central] {len(msg.messages)} Nachricht(en) erhalten von {sender[:20]}...")

    # Step 2: Process each message in the batch
    for entry in msg.messages:

        # Step 2a: Extract message type
        msg_type = entry.get("type")

        # Step 2b: Look up target service address
        target = service_map.get(msg_type)
        if not target:
            print(f"❌ [Central] Kein Ziel für Typ '{msg_type}'")
            continue

        # Step 2c: Look up model constructor for this service type
        constructor = model_factory.get(msg_type)
        if not constructor:
            print(f"❌ [Central] Kein Model-Constructor für Typ '{msg_type}'")
            continue

        # Step 2d & 2e: Reconstruct typed message and forward to service
        try:
            # Convert dict to specific Model instance
            reconstructed = constructor(**entry)
            print(f"✅ [Central] Weiterleiten an {msg_type} → {target[:40]}...")
            await ctx.send(target, reconstructed)
        except Exception as e:
            # Log error but continue processing remaining messages
            print(f"❌ [Central] Fehler beim Verarbeiten von {msg_type}: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the CentralService routing agent.
    
    Starts the central routing service and displays critical setup information
    including the agent address that must be configured in client applications.
    
    Usage:
        python service_central.py
    
    Console Output:
        ============================================================
        🚀 CENTRAL SERVICE GESTARTET
        ============================================================
        📍 Agent-Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
        🌐 Endpoint: http://localhost:8000/submit
        ============================================================
        
        ⚠️  WICHTIG: Kopiere die Agent-Adresse oben in:
           - Agent_Fahrer/fahrer_gui.py (CENTRAL_SERVICE_ADDRESS)
           - Agent_Fahrer/voice_assistant.py (CENTRAL_SERVICE_ADDRESS)
        ============================================================
    
    Setup Requirements:
        1. Start this service first (before clients)
        2. Copy the displayed agent address
        3. Update CENTRAL_SERVICE_ADDRESS in client files:
           - fahrer_gui.py
           - voice_assistant.py
        4. Ensure all specialized services are running:
           - service_essen.py (port 8007)
           - service_kaffee.py (port 8008)
           - service_hotel.py (port 8009)
           - service_haustierbetreuung.py (port 8010)
           - service_parkplatz.py (port 8001)
    
    Architecture:
        Client Apps → CentralService (8000) → Specialized Services
        
        Benefits:
        - Single point of contact for clients
        - Centralized routing logic
        - Easy addition of new services
        - Batch request support
        - Error isolation per message
    """
    print("=" * 60)
    print("🚀 CENTRAL SERVICE GESTARTET")
    print("=" * 60)
    print(f"📍 Agent-Adresse: {central.address}")
    print(f"🌐 Endpoint: http://localhost:8000/submit")
    print("=" * 60)
    print("\n⚠️  WICHTIG: Kopiere die Agent-Adresse oben in:")
    print("   - Agent_Fahrer/fahrer_gui.py (CENTRAL_SERVICE_ADDRESS)")
    print("   - Agent_Fahrer/voice_assistant.py (CENTRAL_SERVICE_ADDRESS)")
    print("=" * 60)
    print()
    central.run()
