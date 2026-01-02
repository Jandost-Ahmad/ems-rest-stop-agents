"""
intent_classifier.py

LLM-based intent classifier for the Rest-Stop Voice Assistant.

- Talks to Ollama (local daemon or cloud) via /api/chat
- System prompt and examples are fully in German
- Output is a strict JSON object with:
    action: "parking|food|hotel|coffee|pet|help|unknown"
    parameters: { ... }
    confidence: 0.0 - 1.0
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import requests


@dataclass
class Intent:
    action: str
    parameters: Dict
    confidence: float
    original_text: str


class LLMIntentClassifier:
    """Uses an LLM (local or cloud via Ollama) to classify user intents."""

    def __init__(
        self,
        model: str = "gpt-oss:20b-cloud",
        api_url: str = "http://localhost:11434",
        request_timeout: int = 60,
    ):
        """
        Args:
            model: Name of the Ollama model, e.g. "gpt-oss:20b-cloud" or "deepseek-v3.1:671b-cloud"
            api_url: Ollama API base URL ("http://localhost:11434" for local daemon)
            request_timeout: HTTP timeout in seconds
        """
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.request_timeout = request_timeout

        # ------------------------------------------------------------
        # System prompt: completely German, narrow domain
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # Deutsche Few-Shot-Beispiele
        # ------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def classify(self, text: str) -> Intent:
        """
        Classify user intent using the configured LLM via Ollama.

        Args:
            text: User's transcribed speech (German)

        Returns:
            Intent object
        """
        try:
            messages = [{"role": "system", "content": self.system_prompt}]

            # Few-shot examples
            for ex in self.examples:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": ex["response"]})

            # User query
            messages.append({"role": "user", "content": text})

            response = requests.post(
                f"{self.api_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
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

            # Handle ```json ... ``` wrappers if present
            json_str = assistant_message
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

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

    # ------------------------------------------------------------------
    def test_connection(self) -> bool:
        """Test if Ollama is reachable and the model exists."""
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


if __name__ == "__main__":
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
