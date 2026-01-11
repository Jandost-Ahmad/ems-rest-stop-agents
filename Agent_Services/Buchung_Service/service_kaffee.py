"""Coffee ordering service agent.

This module defines the `KaffeeService` agent which processes coffee order
requests (`KaffeeMessage`) and responds with pickup time confirmations
(`Message`).

- Preparation time: 5 minutes from order time
- No capacity limits (instant processing)
- Returns estimated pickup time

"""
from uagents import Agent, Context, Model
import datetime


# =============================================================================
# DATA MODELS
# =============================================================================

class KaffeeMessage(Model):
    """
    Input model for coffee order requests.
    
    Represents an incoming request to order coffee at a specific time.
    The agent calculates preparation time and returns the pickup time.
    
    Attributes:
        type (str): Message type identifier (e.g., "kaffee_anfrage")
        zeit (str): Desired order time in "HH:MM" format (24-hour)
        client_sender (str): Address of the originating client agent
    
    Example:
        >>> msg = KaffeeMessage(
        ...     type="kaffee_anfrage",
        ...     zeit="09:30",
        ...     client_sender="agent1q2..."
        ... )
    """
    type: str
    zeit: str
    client_sender: str


# ---------- Output-Modell ----------
class Message(Model):
    """
    Output model for agent responses.
    
    Represents the agent's response to a coffee order request,
    containing the estimated pickup time.
    
    Attributes:
        type (str): Response type identifier ("kaffee_bestaetigung")
        message (str): Human-readable confirmation with pickup time
        zeit (str): Calculated pickup time in "HH:MM" format
    
    Example:
        >>> response = Message(
        ...     type="kaffee_bestaetigung",
        ...     message="☕ Kaffee ist um 09:35 abholbereit.",
        ...     zeit="09:35"
        ... )
    """
    type: str
    message: str
    zeit: str


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

kaffeeAgent = Agent(
    name="KaffeeService",
    port=8008,
    seed="kaffeeServiceAgent",
    endpoint=["http://localhost:8008/submit"],
)
"""
Main agent instance for the coffee service.

Configuration:
    - name: "KaffeeService" - Agent identifier for logging
    - port: 8008 - Network port for agent communication
    - seed: "kaffeeServiceAgent" - Deterministic seed for address generation
    - endpoint: HTTP endpoint for message submission

The agent will be accessible at the generated address printed on startup.
"""


# =============================================================================
# BUSINESS LOGIC CONFIGURATION
# =============================================================================

# Preparation time: Coffee is ready 5 minutes after order time
PREPARATION_TIME_MINUTES = 5


# =============================================================================
# MESSAGE HANDLER
# =============================================================================

@kaffeeAgent.on_message(model=KaffeeMessage)
async def kaffee_handler(ctx: Context, sender: str, msg: KaffeeMessage):
    """
    Main message handler for coffee order requests.
    
    Processes incoming KaffeeMessage requests, calculates the pickup time
    based on order time plus preparation time, and sends back a confirmation.
    
    Workflow:
        1. Client Identification: Determines the client address for response
        2. Time Parsing: Parses the requested order time
        3. Pickup Calculation: Adds 5 minutes to order time
        4. Confirmation: Sends pickup time back to client
    
    Args:
        ctx (Context): Agent context for sending messages and logging
        sender (str): Address of the message sender
        msg (KaffeeMessage): The incoming coffee order request
    
    Returns:
        None (sends Message response via ctx.send)
    
    Success Response:
        "☕ Kaffee ist um {pickup_time} abholbereit."
    
    Notes:
        - If time parsing fails, uses current time as fallback
        - No capacity limits: all orders are accepted
        - Preparation time is fixed at 5 minutes
        - Time must be in 24-hour "HH:MM" format
    """
    # Step 1: Determine client address for response routing
    # Uses client_sender if provided, otherwise falls back to direct sender
    client = msg.client_sender or sender

    # Step 2: Parse order time, fallback to current time if invalid
    try:
        bestellzeit = datetime.datetime.strptime(msg.zeit, "%H:%M")
    except:
        # If time format is invalid, use current time
        bestellzeit = datetime.datetime.now()

    # Step 3: Calculate pickup time (order time + 5 minutes)
    fertig = bestellzeit + datetime.timedelta(minutes=PREPARATION_TIME_MINUTES)
    fertig_str = fertig.strftime("%H:%M")

    # Step 4: Create confirmation message with pickup time
    antwort = f"☕ Kaffee ist um {fertig_str} abholbereit."

    # Send response to client
    await ctx.send(client, Message(
        type="kaffee_bestaetigung",
        message=antwort,
        zeit=fertig_str
    ))

    # Log the transaction for monitoring
    ctx.logger.info(f"Kaffee-Bestätigung: {antwort}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Main entry point for the KaffeeService agent.
    
    Starts the agent and displays connection information.
    The agent will listen for incoming KaffeeMessage requests and process
    them according to the business logic defined above.
    
    Usage:
        python service_kaffee.py
    
    Console Output:
        ☕ Kaffee-Service gestartet…
        📍 Adresse: agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0
    
    Sending a Request (from another agent):
        >>> await ctx.send(
        ...     "agent1q2w3e4r5t6y7u8i9o0p1a2s3d4f5g6h7j8k9l0",
        ...     KaffeeMessage(
        ...         type="kaffee_anfrage",
        ...         zeit="09:30",
        ...         client_sender=ctx.agent.address
        ...     )
        ... )
    
    Features:
        - No capacity limits: All orders are accepted immediately
        - Fixed preparation time: Always 5 minutes
        - Automatic fallback: Uses current time if order time is invalid
        - Simple workflow: Order → Confirmation with pickup time
    """
    print("☕ Kaffee-Service gestartet…")
    print(f"📍 Adresse: {kaffeeAgent.address}")
    kaffeeAgent.run()
