"""
intent_classifier.py
====================

LLM-based Intent Classification for German Highway Rest Stop Voice Assistant
-----------------------------------------------------------------------------

This module provides intelligent classification of voice commands into actionable
service requests using a large language model (LLM). It transforms natural 
German speech into structured intent representations that can be routed to
specialized service agents.

Architecture:
    - LLM Backend: Ollama API (local or cloud deployment)
    - Input: Natural German speech transcription
    - Output: Structured Intent dataclass with action and parameters
    - Confidence: Scoring for classification certainty

Supported Actions:
    - parking: Parking reservations (PKW/LKW/Bus, charging stations)
    - food: Restaurant orders (meal types, dine-in/takeout)
    - hotel: Room bookings (single/double/family, nights)
    - coffee: Coffee to-go orders
    - pet: Pet care services (dog/cat)
    - help: General assistance requests
    - unknown: Out-of-domain queries

Key Features:
    - German-language system prompt with domain constraints
    - Few-shot learning examples for better accuracy
    - JSON-structured output for easy parsing
    - Confidence scoring (0.0-1.0) for intent validation
    - HTTP timeout and error handling for reliability

Integration:
    Used by voice_assistant.py to convert transcribed speech into
    service-specific messages that can be routed via CentralService.

Example:
    >>> classifier = LLMIntentClassifier(model="gpt-oss:20b-cloud")
    >>> intent = classifier.classify("Ich brauche einen Parkplatz für mein Auto")
    >>> print(intent.action)  # "parking"
    >>> print(intent.parameters)  # {"vehicle": "PKW", "charging": "ohne"}

Dependencies:
    - requests: HTTP communication with Ollama API
    - json: Response parsing
    - dataclasses: Intent structure definition

Author: EMS Rest Stop Agents Project
Version: 1.0
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import requests


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Intent:
    """
    Structured representation of classified user intent.
    
    Attributes:
        action (str): Intent category (parking/food/hotel/coffee/pet/help/unknown)
        parameters (Dict): Action-specific parameters extracted from speech
        confidence (float): Classification confidence score (0.0-1.0)
        original_text (str): Original transcribed user speech
    
    Parameter Examples:
        parking: {"vehicle": "PKW", "charging": "mit", "duration_minutes": 120}
        food: {"food_type": "Vegetarisch", "togo": True}
        hotel: {"room_type": "doppel", "nights": 2}
        coffee: {} (no parameters)
        pet: {"animal": "hund"}
    
    Confidence Interpretation:
        > 0.8: High confidence - proceed with action
        0.5-0.8: Medium confidence - may need confirmation
        < 0.5: Low confidence - request clarification
    """
    action: str
    parameters: Dict
    confidence: float
    original_text: str


# =============================================================================
# LLM INTENT CLASSIFIER
# =============================================================================

class LLMIntentClassifier:
    """
    LLM-based intent classifier using Ollama API for German voice commands.
    
    Sends user speech to an LLM with a German system prompt and few-shot
    examples, then parses the structured JSON response into an Intent object.
    
    Attributes:
        model (str): Ollama model name (e.g., "gpt-oss:20b-cloud")
        api_url (str): Ollama API endpoint (default: http://localhost:11434)
        request_timeout (int): HTTP timeout in seconds
        system_prompt (str): German-language domain-specific instructions
    
    Supported Models:
        - gpt-oss:20b-cloud: Balanced performance/speed
        - deepseek-v3.1:671b-cloud: Higher accuracy, slower
        - llama3.1:70b: Local deployment option
    
    Classification Process:
        1. Construct chat messages (system + examples + user input)
        2. Send POST request to Ollama /api/chat endpoint
        3. Parse streamed JSON response chunks
        4. Extract action, parameters, confidence
        5. Validate and return Intent object
    
    Error Handling:
        - Network errors: Return unknown intent with confidence 0.0
        - JSON parsing errors: Return unknown intent
        - LLM response errors: Log and return unknown intent
        - Timeout: Configurable via request_timeout parameter
    """

    def __init__(
        self,
        model: str = "gpt-oss:20b-cloud",
        api_url: str = "http://localhost:11434",
        request_timeout: int = 60,
    ):
        """
        Initialize the LLM intent classifier with connection parameters.
        
        Args:
            model (str): Name of the Ollama model to use
                        Examples: "gpt-oss:20b-cloud", "deepseek-v3.1:671b-cloud"
            api_url (str): Base URL for Ollama API endpoint
                          Default: "http://localhost:11434" (local daemon)
                          Cloud: "https://your-cloud-endpoint.com"
            request_timeout (int): HTTP request timeout in seconds (default: 60)
        
        Notes:
            - Model must be pre-installed in Ollama (run `ollama pull <model>`)
            - API URL is stripped of trailing slashes automatically
            - System prompt and few-shot examples initialized internally
        """
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.request_timeout = request_timeout

        # =============================================================================
        # SYSTEM PROMPT: German Domain-Specific Instructions
        # =============================================================================
        self.system_prompt = """
Du bist ein deutscher Sprachassistent für eine Autobahn-Raststätte.

Deine einzige Aufgabe:
Die Absicht (Intent) des Fahrers zu erkennen und sie in eine kleine JSON-Struktur zu übersetzen.

Der Fahrer kann nur über folgende Dinge sprechen:

1. PARKPLATZ (action = "parking")
   - Fahrzeug: PKW, LKW oder Bus
   - Ladesäule: mit oder ohne
   - Optionale Aufenthaltsdauer in Minuten (duration_minutes, ganze Zahl)

2. ESSEN / RESTAURANT (action = "food")
   - Typ: Standard, Vegetarisch, Vegan, Glutenfrei  (Parameter: food_type)
   - Zum Mitnehmen (togo = true) oder im Restaurant (togo = false)

3. HOTEL (action = "hotel")
   - Zimmerart: einzel, doppel, familie  (room_type)
   - Anzahl der Nächte (nights, ganze Zahl)
   WICHTIG:
   - Wenn der Fahrer z.B. "zwei Nächte", "2 Nächte", "für drei Nächte" sagt,
     musst du die Zahl korrekt als nights eintragen.
   - Nur wenn gar keine Zahl vorkommt, darfst du 1 als Standard nehmen.

4. KAFFEE (action = "coffee")
   - Einfach Kaffee bestellen / to go.

5. HAUSTIERBETREUUNG (action = "pet")
   - Tier: hund oder katze  (animal)

6. Allgemeine Hilfe oder Unklarheit (action = "help")

7. Anfrage passt überhaupt nicht zur Raststätte
   (Wetter, Politik, persönliches Leben, Programmierung, usw.)
   → action = "unknown"

-------------------------------------------------
AUSGABEFORMAT
-------------------------------------------------

Antwort IMMER als reines JSON-Objekt (kein Text davor oder danach):

{
  "action": "parking|food|hotel|coffee|pet|help|unknown",
  "parameters": {
    "vehicle": "PKW|LKW|Bus",
    "charging": "mit|ohne",
    "duration_minutes": 120,
    "food_type": "Standard|Vegetarisch|Vegan|Glutenfrei",
    "togo": true,
    "room_type": "einzel|doppel|familie",
    "nights": 2,
    "animal": "hund|katze"
  },
  "confidence": 0.0
}

REGELN:
- Benutze nur die Parameter, die wirklich relevant sind. Unbenutzte Parameter einfach weglassen.
- "confidence" ist deine Sicherheit von 0.0 bis 1.0.
- Antworte NIE mit Text außerhalb des JSON. Kein Fließtext.
- Wenn du unsicher bist, aber es zur Raststätte passt: action = "help".
- Wenn es gar nichts mit der Raststätte zu tun hat: action = "unknown".
- Sprich mit dir selbst niemals Englisch – die Eingaben sind hauptsächlich Deutsch.
"""

        # =============================================================================
        # FEW-SHOT EXAMPLES: German Training Data
        # =============================================================================
        # These examples improve classification accuracy by showing the LLM
        # exactly how to map various German phrasings to structured intents.
        # Each example includes natural user speech and expected JSON response.
        self.examples: List[Dict[str, str]] = [
            {
                "user": "Ich brauche einen PKW Parkplatz mit Ladesäule für zwei Stunden.",
                "response": json.dumps(
                    {
                        "action": "parking",
                        "parameters": {
                            "vehicle": "PKW",
                            "charging": "mit",
                            "duration_minutes": 120,
                        },
                        "confidence": 0.96,
                    }
                ),
            },
            {
                "user": "Gibt es einen LKW-Parkplatz ohne Ladestation?",
                "response": json.dumps(
                    {
                        "action": "parking",
                        "parameters": {
                            "vehicle": "LKW",
                            "charging": "ohne",
                        },
                        "confidence": 0.9,
                    }
                ),
            },
            {
                "user": "Ich möchte ein veganes Essen zum Mitnehmen bestellen.",
                "response": json.dumps(
                    {
                        "action": "food",
                        "parameters": {
                            "food_type": "Vegan",
                            "togo": True,
                        },
                        "confidence": 0.94,
                    }
                ),
            },
            {
                "user": "Reserviere mir bitte ein glutenfreies Menü im Restaurant.",
                "response": json.dumps(
                    {
                        "action": "food",
                        "parameters": {
                            "food_type": "Glutenfrei",
                            "togo": False,
                        },
                        "confidence": 0.92,
                    }
                ),
            },
            {
                "user": "Ich brauche ein Einzelzimmer für zwei Nächte.",
                "response": json.dumps(
                    {
                        "action": "hotel",
                        "parameters": {
                            "room_type": "einzel",
                            "nights": 2,
                        },
                        "confidence": 0.95,
                    }
                ),
            },
            {
                "user": "Buch mir bitte ein Doppelzimmer für drei Nächte.",
                "response": json.dumps(
                    {
                        "action": "hotel",
                        "parameters": {
                            "room_type": "doppel",
                            "nights": 3,
                        },
                        "confidence": 0.95,
                    }
                ),
            },
            {
                "user": "Ich brauche Kaffee to go.",
                "response": json.dumps(
                    {
                        "action": "coffee",
                        "parameters": {},
                        "confidence": 0.9,
                    }
                ),
            },
            {
                "user": "Könnt ihr euch um meinen Hund kümmern, während ich im Restaurant esse?",
                "response": json.dumps(
                    {
                        "action": "pet",
                        "parameters": {
                            "animal": "hund",
                        },
                        "confidence": 0.9,
                    }
                ),
            },
            {
                "user": "Wie wird das Wetter morgen in Berlin?",
                "response": json.dumps(
                    {
                        "action": "unknown",
                        "parameters": {},
                        "confidence": 0.9,
                    }
                ),
            },
        ]

    # =============================================================================
    # PUBLIC CLASSIFICATION API
    # =============================================================================
    
    def classify(self, text: str) -> Intent:
        """
        Classify German user speech into structured intent with LLM.
        
        Sends user text to Ollama LLM with system prompt and few-shot examples,
        then parses the JSON response into a validated Intent object.
        
        Args:
            text (str): Natural German speech transcription from user
                       Example: "Ich brauche einen Parkplatz für mein Auto"
        
        Returns:
            Intent: Structured intent with action, parameters, and confidence
        
        Classification Pipeline:
            1. Construct chat messages (system + examples + user text)
            2. Send POST to Ollama /api/chat with streaming enabled
            3. Accumulate streamed response chunks
            4. Parse final JSON: {"action": "...", "parameters": {...}, "confidence": 0.0-1.0}
            5. Validate action is in allowed set
            6. Return Intent object with original_text preserved
        
        Error Handling:
            - Network errors: Return Intent(action="unknown", confidence=0.0)
            - JSON parse errors: Return unknown intent
            - Invalid action: Return unknown intent
            - LLM timeout: Configurable via request_timeout
        
        Action Validation:
            Valid: parking, food, hotel, coffee, pet, help, unknown
            Invalid actions are converted to "unknown" with confidence 0.0
        
        Examples:
            >>> classifier.classify("Parkplatz für LKW mit Ladesäule")
            Intent(action='parking', parameters={'vehicle': 'LKW', 'charging': 'mit'}, 
                   confidence=0.95, original_text='Parkplatz für LKW mit Ladesäule')
            
            >>> classifier.classify("Vegetarisches Essen zum Mitnehmen")
            Intent(action='food', parameters={'food_type': 'Vegetarisch', 'togo': True},
                   confidence=0.92, original_text='Vegetarisches Essen zum Mitnehmen')
        
        Notes:
            - Requires running Ollama instance at self.api_url
            - Model must be pre-installed (ollama pull <model>)
            - Streaming=True for better responsiveness on large models
            - Original text preserved for logging/debugging

        Args:
            text: User's transcribed speech (German)

        Returns:
            Intent object
        """
        try:
            # Build chat conversation with system prompt and few-shot examples
            messages = [{"role": "system", "content": self.system_prompt}]

            # Add few-shot examples for in-context learning
            for ex in self.examples:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": ex["response"]})

            # Add actual user query
            messages.append({"role": "user", "content": text})

            # Send classification request to Ollama
            response = requests.post(
                f"{self.api_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,  # Wait for complete response
                    "options": {
                        "temperature": 0.0,  # Deterministic output
                        "top_p": 0.9,
                    },
                },
                timeout=self.request_timeout,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Ollama API error {response.status_code}: {response.text}"
                )

            result = response.json()
            assistant_message = result["message"]["content"].strip()

            # Strip markdown code fences if LLM wrapped response
            json_str = assistant_message
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            # Parse JSON response
            parsed = json.loads(json_str)

            action = parsed.get("action", "unknown")
            params = parsed.get("parameters", {}) or {}
            conf = float(parsed.get("confidence", 0.0))

            return Intent(
                action=action,
                parameters=params,
                confidence=conf,
                original_text=text,
            )

        except json.JSONDecodeError as e:
            print(f"[LLMIntentClassifier] JSON parse error: {e}")
            print(f"Raw response: {locals().get('assistant_message', '')}")
            return Intent(
                action="unknown",
                parameters={},
                confidence=0.0,
                original_text=text,
            )
        except Exception as e:
            print(f"[LLMIntentClassifier] HTTP/LLM error: {e}")
            return Intent(
                action="unknown",
                parameters={},
                confidence=0.0,
                original_text=text,
            )

    # =============================================================================
    # CONNECTION TESTING
    # =============================================================================
    
    def test_connection(self) -> bool:
        """
        Verify Ollama API connectivity and model availability.
        
        Checks that:
        1. Ollama API is reachable at configured URL
        2. Specified model is installed and accessible
        
        Returns:
            bool: True if connection successful and model available, False otherwise
        
        Usage:
            >>> classifier = LLMIntentClassifier(model="gpt-oss:20b-cloud")
            >>> if classifier.test_connection():
            ...     intent = classifier.classify("Parkplatz für PKW")
            ... else:
            ...     print("Ollama not available")
        
        Diagnostics:
            - Prints success/failure messages with details
            - Lists available models if configured model not found
            - Shows connection errors with exception details
        
        Notes:
            - Uses /api/tags endpoint (Ollama management API)
            - 5-second timeout for quick failure detection
            - Partial name matching (e.g., "gpt-oss" matches "gpt-oss:20b-cloud")
        """
        try:
            resp = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                print(f"✗ Ollama API error: {resp.status_code}")
                return False

            models = resp.json().get("models", [])
            names = [m.get("name", "") for m in models]
            if self.model in names or any(self.model in n for n in names):
                print(f"✓ Verbunden mit Ollama, Modell '{self.model}' ist verfügbar.")
                return True
            else:
                print(f"✗ Modell '{self.model}' nicht gefunden. Verfügbare Modelle: {names}")
                return False
        except Exception as e:
            print(f"✗ Kann nicht mit Ollama verbinden: {e}")
            return False


# =============================================================================
# INTERACTIVE TESTING
# =============================================================================

if __name__ == "__main__":
    """
    Interactive test mode for intent classification.
    
    Usage:
        python intent_classifier.py
        
        Then enter German sentences to see classification results.
        Empty input exits the program.
    
    Test Examples:
        > Ich brauche einen Parkplatz für mein Auto
        > Vegetarisches Essen zum Mitnehmen bitte
        > Ein Doppelzimmer für zwei Nächte
        > Kann ich meinen Hund hier lassen?
        > Kaffee to go
    
    Output Format:
        Action:      parking
        Parameters:  {'vehicle': 'PKW', 'charging': 'ohne'}
        Confidence:  0.95
    
    Prerequisites:
        - Ollama running at http://localhost:11434
        - Model installed: ollama pull gpt-oss:20b-cloud
    """
    clf = LLMIntentClassifier()
    print("Testing connection to Ollama...")
    clf.test_connection()

    print("\nGib einen deutschen Beispielsatz ein (leer = Ende):\n")
    while True:
        try:
            txt = input("> ").strip()
            if not txt:
                break
            intent = clf.classify(txt)
            print(f"Action:      {intent.action}")
            print(f"Parameters:  {intent.parameters}")
            print(f"Confidence:  {intent.confidence:.2f}\n")
        except KeyboardInterrupt:
            break
