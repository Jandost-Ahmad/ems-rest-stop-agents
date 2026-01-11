"""Voice assistant agent for rest stop services.

This module implements a wake word-activated voice assistant that enables
hand-free interaction with the rest stop service system. The assistant uses
multi-stage processing to understand driver requests and coordinate with services.

Architecture:
- Speech-to-Text (STT): Faster-Whisper for German transcription
- Intent Classification: LLM-based (Ollama) for natural language understanding
- Text-to-Speech (TTS): Piper for German voice synthesis
- Agent Communication: uAgents framework for service coordination
- Wake Word: "Hallo" activation for hands-free operation

Workflow:
1. Passive listening for wake word ("Hallo")
2. Acknowledge activation: "Wie kann ich Ihnen helfen?"
3. Record and transcribe full request (max 10 seconds)
4. Classify intent using LLM (parking, food, hotel, coffee, pet)
5. Convert to service messages and send to CentralService
6. Receive service responses and speak them back
7. Return to passive listening state

Features:
- Non-blocking async architecture
- Queue-based reply handling for ordered speech
- Multi-service request batching
- Confidence-based intent validation
- Error recovery and user guidance
- German language optimization

Dependencies:
- faster-whisper: STT engine (small model, CPU optimized)
- ollama: LLM inference (gpt-oss:20b-cloud or similar)
- piper: TTS engine (thorsten-low German voice)
- sounddevice/soundfile: Audio I/O
- uagents: Agent communication

Configuration:
- CENTRAL_SERVICE_ADDRESS: Target service router address
- WAKE_WORD: Activation phrase ("Hallo")
- STT_MODEL_SIZE: Whisper model variant ("small")
- PIPER_MODEL_PATH: Path to German voice model

"""

import asyncio
import os
import time
import tempfile
import subprocess
from datetime import datetime, timedelta
from typing import List

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from uagents import Agent, Context, Model

from intent_classifier import LLMIntentClassifier, Intent

# =============================================================================
# SHARED MESSAGE MODELS
# =============================================================================
"""
Message models matching the CentralService and specialized service agents.
These MUST be kept in sync with the service definitions to ensure proper
serialization and communication.

All models include:
- type: Service identifier for routing
- client_sender: Return address for responses
- Service-specific parameters
"""

# ---- Request models (must match service_central + services) ----

class EssenMessage(Model):
    type: str
    zeit: str
    standard: int
    vegetarisch: int
    vegan: int
    glutenfrei: int
    client_sender: str


class KaffeeMessage(Model):
    type: str
    zeit: str
    client_sender: str


class HaustierMessage(Model):
    type: str
    haustierart: str
    zeit: str
    betreuung_von: str
    betreuung_bis: str
    client_sender: str


class HotelMessage(Model):
    type: str
    zimmerart: str
    zeit: str
    naechte: int
    client_sender: str


class ParkplatzMessage(Model):
    type: str
    fahrzeugart: str
    ladestation: bool
    zeit: str
    reservation_id: str
    client_sender: str


class CentralServiceMessage(Model):
    messages: list  # list of dicts


# ---- Generic reply from ANY service ----
# Must match the Message model in all services exactly!
class Message(Model):
    type: str
    message: str
    zeit: str


# =============================================================================
# CONFIGURATION
# =============================================================================
"""
Voice assistant configuration parameters.

CENTRAL_SERVICE_ADDRESS:
    CRITICAL: Must match the address printed by service_central.py on startup.
    Copy the full test-agent:// address from the central service console output.
    Without this, the assistant cannot communicate with services.

STT (Speech-to-Text) Configuration:
    - MODEL_SIZE: "tiny" (fastest), "base", "small" (balanced), "medium", "large"
    - DEVICE: "cpu" or "cuda" (GPU acceleration)
    - COMPUTE_TYPE: "int8" (CPU), "float16" (GPU), "int8_float16" (hybrid)
    - Recommendation: "small"/"cpu"/"int8" for good accuracy with reasonable speed

TTS (Text-to-Speech) Configuration:
    - PIPER_MODEL_PATH: Path to German voice model (.onnx file)
    - thorsten-low: Good quality, fast, natural-sounding German male voice
    - TTS_OUTPUT_DIR: Temporary storage for generated WAV files

Wake Word Configuration:
    - WAKE_WORD: Activation phrase ("Hallo" is short and reliable)
    - WAKE_RECORD_SECONDS: Short chunks for continuous wake word detection
    - Shorter = more responsive, but more CPU usage

Recording Configuration:
    - MAX_RECORD_SECONDS: Maximum request length (10s sufficient for most requests)
    - CURRENT_LANGUAGE: "de" forces German, None auto-detects (slower)
"""

# !!! IMPORTANT !!!
# Paste here the address printed by service_central.py when it starts
CENTRAL_SERVICE_ADDRESS = "test-agent://agent1qdxu32w99hg82pmqvulkxttpvqpctvp2vya4w9d2mnl9rhj03mt464747cc"

# STT config
STT_MODEL_SIZE = "small"      # "tiny" is fast, good for testing
STT_DEVICE = "cpu"           # "cuda" if you have GPU
STT_COMPUTE_TYPE = "int8"    # good for CPU speed

# TTS config (Piper CLI)
PIPER_MODEL_PATH = "piper_voices/de_DE-thorsten-low.onnx"  # adjust if needed
TTS_OUTPUT_DIR = "tts_output"
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

# Wake word config
WAKE_WORD = "Hallo"          # what you say to activate the assistant
WAKE_RECORD_SECONDS = 3      # short chunk for wake-word listening

# Max recording length for full requests
MAX_RECORD_SECONDS = 10

# Language for Whisper ("de", "en", or None for auto detect)
CURRENT_LANGUAGE = "de" 

# =============================================================================
# INITIALIZATION - STT, LLM, AGENT, STATE
# =============================================================================
"""
Initialize all components required for voice assistant operation.

Components:
1. Faster-Whisper STT Model:
   - Loaded once at startup for efficiency
   - Configured for German language optimization
   - Uses CPU-optimized int8 quantization

2. LLM Intent Classifier:
   - Connects to Ollama API (local or cloud)
   - Trained with German few-shot examples
   - Classifies 7 intent types: parking, food, hotel, coffee, pet, help, unknown

3. Voice Assistant Agent:
   - Port 8002 for external access
   - Tailscale endpoint for remote connectivity
   - Receives service responses asynchronously

4. State Management:
   - reply_queue: Ensures ordered speech output
   - State flags: Control conversation flow (wake word → request → replies)
   - Reply tracking: Ensures all services respond before next interaction

State Machine:
- waiting_for_wake_word: Passive listening mode
- waiting_for_request: Active, expecting full request after wake word
- awaiting_replies: Request sent, waiting for all service confirmations
"""

print("🔊 Lade Faster-Whisper …")
stt_model = WhisperModel(
    STT_MODEL_SIZE,
    device=STT_DEVICE,
    compute_type=STT_COMPUTE_TYPE,
)

print("🧠 Initialisiere LLM-Intent-Classifier …")
# Use defaults from intent_classifier.py (you can set model/api there)
intent_classifier = LLMIntentClassifier()

assistantAgent = Agent(
    name="VoiceAssistant",
    port=8002,  
    seed="voiceassistant_1",
    endpoint=["http://100.118.74.109:8002/submit"],
)

print(f"[VoiceAssistant] gestartet! Adresse: {assistantAgent.address}")

# Queue for replies so they are spoken in order
reply_queue: asyncio.Queue[Message] = asyncio.Queue()

# State flags
_started = False
waiting_for_wake_word = True
waiting_for_request = False
awaiting_replies = False
expected_replies = 0
received_replies = 0


# ============================================================
#                    AUDIO HELPERS
# ============================================================

def record_audio_blocking(duration: int, samplerate: int = 16000) -> str:
    """Record from microphone and return path to temp WAV file (blocking)."""
    try:
        print(f"\n🎙️ Aufnahme startet (max {duration} Sekunden)…")
        audio = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        print("✅ Aufnahme beendet.")

        tmp = tempfile.NamedTemporaryFile(
            dir=TTS_OUTPUT_DIR, suffix=".wav", delete=False
        )
        sf.write(tmp.name, audio, samplerate)
        return tmp.name

    except Exception as e:
        print(f"❌ Mikrofonfehler: {e}")
        return ""


def transcribe_blocking(path: str, language: str = CURRENT_LANGUAGE) -> str:
    """
    Transcribe audio file to text using Faster-Whisper (blocking operation).
    
    Uses the pre-loaded Whisper model to convert speech to German text.
    Optimized for accuracy with beam search decoding.
    
    Args:
        path (str): Path to WAV file to transcribe
        language (str): Language code ("de" for German, None for auto-detect)
    
    Returns:
        str: Transcribed text, or empty string on error
    
    Notes:
        - Beam size 5 provides good accuracy-speed balance
        - Language set to "de" forces German (faster than auto-detect)
        - Segments are joined with spaces for natural text
        - Errors are logged but don't raise exceptions
        - Empty files or silence return empty string
    
    Performance:
        - small model: ~1-2 seconds for 10 second audio on CPU
        - Beam size 5: Good balance between speed and accuracy
    """
    if not path:
        return ""

    try:
        print("📝 Transkribiere Audio …")
        segments, info = stt_model.transcribe(
            path,
            beam_size=5,
            language=language,  # forced to 'de'
        )
        text = " ".join(seg.text for seg in segments).strip()
        print(f"🗣️ Erkannt: {text}")
        return text
    except Exception as e:
        print(f"❌ STT-Fehler: {e}")
        return ""


def tts_speak_blocking(text: str):
    """
    Synthesize and play German speech using Piper TTS (blocking operation).
    
    Converts text to speech using Piper CLI with German voice model,
    then plays the audio through the default sound device. Includes
    comprehensive text sanitization to handle emojis and special characters.
    
    Args:
        text (str): Text to speak (German). May contain emojis and special chars.
    
    Returns:
        None
    
    Text Processing:
        - Removes all emojis (Unicode ranges 0x1F300-0x1F9FF, etc.)
        - Filters surrogate pairs and control characters
        - Replaces problematic characters with spaces
        - Normalizes multiple spaces
    
    Fallback Behavior:
        1. Primary: Piper CLI with thorsten-low German voice
        2. Fallback: pyttsx3 (if Piper fails and pyttsx3 is available)
        3. Silent failure: Logs error if both fail
    
    Notes:
        - Blocks until speech completes
        - Cleans up old WAV files before generating new ones
        - Temporary WAV files stored in TTS_OUTPUT_DIR
        - Piper must be installed and in system PATH
        - UTF-8 encoding for German umlauts (ä, ö, ü, ß)
    
    Performance:
        - Generation: ~0.5-1 second for typical sentence
        - Playback: Real-time (depends on text length)
    """
    if not text:
        return

    try:
        # FIRST: Remove/replace emojis and problematic characters BEFORE any processing
        def clean_text_for_tts(s: str) -> str:
            """
            Remove emojis and sanitize text for TTS.
            
            Filters out:
            - Emoji characters (various Unicode ranges)
            - Surrogate pairs
            - Control characters (except whitespace)
            - Invalid Unicode code points
            
            Args:
                s (str): Input text with potential emojis
            
            Returns:
                str: Cleaned text safe for TTS processing
            """
            if not s:
                return s
            
            out_chars = []
            for ch in s:
                cp = ord(ch)
                
                # Skip emojis (most are in these ranges)
                if (0x1F300 <= cp <= 0x1F9FF or  # Emoticons, symbols, pictographs
                    0x2600 <= cp <= 0x26FF or     # Miscellaneous symbols
                    0x2700 <= cp <= 0x27BF or     # Dingbats
                    0xFE00 <= cp <= 0xFE0F or     # Variation selectors
                    0x1F000 <= cp <= 0x1F02F or   # Mahjong, domino tiles
                    0x1F0A0 <= cp <= 0x1F0FF):    # Playing cards
                    continue
                
                # Skip surrogates (0xD800-0xDFFF)
                if 0xD800 <= cp <= 0xDFFF:
                    continue
                
                # Replace control characters (except whitespace) with space
                if cp < 0x20 and ch not in "\n\r\t":
                    out_chars.append(" ")
                    continue
                
                # Skip other problematic characters
                if cp > 0x10FFFF:  # Beyond valid Unicode
                    continue
                    
                out_chars.append(ch)
            
            result = "".join(out_chars)
            # Clean up multiple spaces
            while "  " in result:
                result = result.replace("  ", " ")
            return result.strip()

        cleaned_text = clean_text_for_tts(text)
        
        if not cleaned_text:
            print("⚠️ TTS: Text wurde vollständig gefiltert, nichts zu sagen.")
            return
            
        print(f"🔈 Assistant sagt: {cleaned_text}")

        # Clean old wav files in the folder
        for fname in os.listdir(TTS_OUTPUT_DIR):
            if fname.lower().endswith(".wav"):
                try:
                    os.remove(os.path.join(TTS_OUTPUT_DIR, fname))
                except OSError:
                    pass

        tmp = tempfile.NamedTemporaryFile(
            dir=TTS_OUTPUT_DIR, suffix=".wav", delete=False
        )
        tmp.close()
        wav_path = tmp.name

        cmd = [
            "piper",
            "-m", PIPER_MODEL_PATH,
            "-f", wav_path,
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                input=cleaned_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except Exception as e:
            print(f"❌ Fehler beim Aufruf von Piper: {e}")
            proc = None

        if not proc or proc.returncode != 0:
            stderr = b""
            if proc is not None:
                stderr = proc.stderr or b""
            print(f"❌ Piper-Fehler: {stderr.decode('utf-8', errors='ignore')}")
            # fallback to pyttsx3 if available
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(cleaned_text)
                engine.runAndWait()
                return
            except Exception:
                print("❌ Kein TTS-Fallback verfügbar (pyttsx3 fehlgeschlagen oder nicht installiert).")
                return

        data, samplerate = sf.read(wav_path)
        sd.play(data, samplerate)
        sd.wait()

    except FileNotFoundError:
        print("❌ Piper nicht gefunden. Ist es installiert und im PATH?")
    except Exception as e:
        print(f"❌ TTS-Fehler: {e}")


# =============================================================================
# INTENT TO SERVICE MESSAGE CONVERSION
# =============================================================================

def build_central_message(intent: Intent, sender_address: str) -> CentralServiceMessage | None:
    """
    Convert classified intent into service request messages for CentralService.
    
    Transforms a high-level intent (from LLM classification) into concrete
    service messages that can be routed to specialized agents.
    
    Args:
        intent (Intent): Classified user intent with action and parameters
        sender_address (str): Voice assistant agent address for responses
    
    Returns:
        CentralServiceMessage: Batch message with service requests, or None if
                              intent cannot be converted (help/unknown actions)
    
    Supported Intents:
        - parking: Creates ParkplatzMessage with vehicle type, charging, duration
        - food: Creates EssenMessage with meal type selection
        - hotel: Creates HotelMessage with room type and nights
        - coffee: Creates KaffeeMessage for coffee orders
        - pet: Creates HaustierMessage with animal type and care period
        - extend_parking: Updates existing parking reservation
    
    Default Values:
        - Current time (HH:MM) for all timestamps
        - 2-hour care period for pets (now + 2 hours)
        - 1 night for hotel if not specified
    
    Notes:
        - help and unknown intents return None (no service action)
        - All messages include client_sender for response routing
        - Parameters extracted from intent.parameters dict
        - Confidence score is not included in service messages
    """
    now = datetime.now()
    jetzt = now.strftime("%H:%M")
    in_2_stunden = (now + timedelta(hours=2)).strftime("%H:%M")

    msgs: list[dict] = []

    if intent.action in ("parking", "extend_parking"):
        vehicle = intent.parameters.get("vehicle", "PKW").upper()
        charging = intent.parameters.get("charging", "ohne")
        has_charging = charging == "mit"

        park_msg = ParkplatzMessage(
            type="parkplatz",
            fahrzeugart=vehicle,
            ladestation=has_charging,
            zeit=jetzt,
            reservation_id=intent.parameters.get("reservation_id", ""),
            client_sender=sender_address,
        )
        msgs.append(park_msg.dict())

    elif intent.action == "food":
        food_type = intent.parameters.get("food_type", "Standard")
        standard = 1 if food_type == "Standard" else 0
        vegetarisch = 1 if food_type == "Vegetarisch" else 0
        vegan = 1 if food_type == "Vegan" else 0
        glutenfrei = 1 if food_type == "Glutenfrei" else 0

        essen_msg = EssenMessage(
            type="essen",
            zeit=jetzt,
            standard=standard,
            vegetarisch=vegetarisch,
            vegan=vegan,
            glutenfrei=glutenfrei,
            client_sender=sender_address,
        )
        msgs.append(essen_msg.dict())

    elif intent.action == "hotel":
        room_type = intent.parameters.get("room_type", "einzel")
        naechte = int(intent.parameters.get("nights", 1))

        hotel_msg = HotelMessage(
            type="hotel",
            zimmerart=room_type,
            zeit=jetzt,
            naechte=naechte,
            client_sender=sender_address,
        )
        msgs.append(hotel_msg.dict())

    elif intent.action == "coffee":
        kaffee_msg = KaffeeMessage(
            type="kaffee",
            zeit=jetzt,
            client_sender=sender_address,
        )
        msgs.append(kaffee_msg.dict())

    elif intent.action == "pet":
        animal = intent.parameters.get("animal", "hund")

        haustier_msg = HaustierMessage(
            type="haustierbetreuung",
            haustierart=animal,
            zeit=jetzt,
            betreuung_von=jetzt,
            betreuung_bis=in_2_stunden,
            client_sender=sender_address,
        )
        msgs.append(haustier_msg.dict())

    else:
        return None

    return CentralServiceMessage(messages=msgs)


# =============================================================================
# MESSAGE HANDLERS
# =============================================================================

@assistantAgent.on_message(model=Message)
async def on_service_reply(ctx: Context, sender: str, msg: Message):
    """
    Handle service responses and queue them for speech synthesis.
    
    Receives responses from all specialized services (parking, food, hotel, 
    coffee, pet care) and adds them to a FIFO queue for ordered speech output.
    
    Args:
        ctx (Context): Agent context (unused)
        sender (str): Address of responding service agent
        msg (Message): Service response with type, message text, and timestamp
    
    State Management:
        - Tracks received_replies count vs expected_replies
        - Sets awaiting_replies=False when all responses received
        - Resets to waiting_for_wake_word state after completion
    
    Queue Structure:
        Each entry: Message model with type, message text, zeit timestamp
        Processing: speaker_loop() consumes queue and speaks each message
    
    Notes:
        - Non-blocking: Only queues message, doesn't wait for TTS
        - Multiple service responses are processed in order received
        - Global state synchronization for multi-service requests
    """
    global awaiting_replies, received_replies, expected_replies, waiting_for_wake_word

    print(f"\n📨 Antwort erhalten ({msg.type}) von {sender}: {msg.message} (zeit={msg.zeit})")
    await reply_queue.put(msg)

    if awaiting_replies:
        received_replies += 1
        if received_replies >= expected_replies:
            awaiting_replies = False
            waiting_for_wake_word = True


async def speaker_loop():
    """
    Background task continuously reading and speaking queued service responses.
    
    Consumes messages from reply_queue in FIFO order and synthesizes each
    response using TTS. Runs indefinitely as an async background task.
    
    Processing Loop:
        1. Wait for message in queue (blocking)
        2. Extract message text and optional timestamp
        3. Format speech output with type and content
        4. Call tts_speak_blocking() to synthesize
        5. Repeat
    
    Queue Behavior:
        - Empty queue: Blocks until message arrives
        - Multiple messages: Processes sequentially
        - No timeout: Waits forever for next message
    
    Speech Format:
        "Service Type: Message text. Time: HH:MM" (if timestamp provided)
        Example: "Parkplatz: Reservierung bestätigt. Zeit: 14:30"
    
    Notes:
        - Must be started with asyncio.create_task(speaker_loop())
        - Blocking TTS calls prevent message overlap
        - Error handling in tts_speak_blocking prevents crashes
    """
    while True:
        msg: Message = await reply_queue.get()
        await asyncio.to_thread(tts_speak_blocking, msg.message)


# =============================================================================
# MAIN VOICE INTERACTION LOOP
# =============================================================================

async def voice_main(ctx: Context):
    """
    Main voice interaction loop implementing wake word-based conversation flow.
    
    Implements a state machine for hands-free voice interaction with services:
    1. waiting_for_wake_word: Listen for "Hallo" in short audio chunks
    2. waiting_for_request: Record full user request after wake word
    3. awaiting_replies: Process service responses and speak them
    
    Conversation Flow:
        User: "Hallo"
        Assistant: "Wie kann ich Ihnen helfen?"
        User: "Ich brauche einen Parkplatz für mein Auto"
        [System: Classifies intent, sends to services]
        Assistant: [Speaks all service responses from queue]
        [Reset to waiting_for_wake_word]
    
    State Management:
        - waiting_for_wake_word: True when ready for wake word
        - waiting_for_request: True after wake word detected
        - awaiting_replies: True when services are processing
        - expected_replies: Number of services to wait for
        - received_replies: Counter for responses received
    
    Wake Word Detection:
        - Records 4-second audio chunks continuously
        - Transcribes each chunk to text
        - Checks for WAKE_WORD ("hallo") case-insensitive
        - Triggers request recording on match
    
    Request Processing:
        1. Record 8-second user request
        2. Transcribe audio to text
        3. Classify intent with LLM
        4. Build service messages from intent
        5. Send to CentralService
        6. Set expected_replies count
        7. Wait for all responses via speaker_loop()
    
    Error Handling:
        - Audio errors: Print and continue listening
        - Transcription failures: Skip chunk
        - Classification errors: Notify user via TTS
        - Service errors: Handled by service agents
    
    Notes:
        - Runs indefinitely as background task
        - Non-blocking: Uses asyncio.to_thread for blocking operations
        - speaker_loop() handles TTS output asynchronously
        - Global state variables synchronized across handlers
    """
    global waiting_for_wake_word, waiting_for_request
    global awaiting_replies, expected_replies, received_replies

    print("\n🎧 Voice Assistant bereit.")
    print(f"   Sag einfach '{WAKE_WORD}', wenn du Hilfe brauchst.\n")

    while True:
        try:
            if awaiting_replies:
                await asyncio.sleep(0.3)
                continue

            # 1) WAIT FOR WAKE WORD
            if waiting_for_wake_word:
                wav_path = await asyncio.to_thread(
                    record_audio_blocking, WAKE_RECORD_SECONDS
                )
                text = await asyncio.to_thread(
                    transcribe_blocking, wav_path, CURRENT_LANGUAGE
                )

                if text:
                    lower = text.lower()
                    if WAKE_WORD.lower() in lower:
                        await asyncio.to_thread(
                            tts_speak_blocking, "Wie kann ich Ihnen helfen?"
                        )
                        waiting_for_wake_word = False
                        waiting_for_request = True
                        continue

                continue

            # 2) RECORD THE DRIVER'S REQUEST
            if waiting_for_request:
                wav_path = await asyncio.to_thread(
                    record_audio_blocking, MAX_RECORD_SECONDS
                )
                text = await asyncio.to_thread(
                    transcribe_blocking, wav_path, CURRENT_LANGUAGE
                )

                if not text:
                    msg = (
                        "Ich habe nichts verstanden. "
                        f"Bitte sag '{WAKE_WORD}', um es noch einmal zu versuchen."
                    )
                    print(msg)
                    await asyncio.to_thread(tts_speak_blocking, msg)
                    waiting_for_request = False
                    waiting_for_wake_word = True
                    continue

                print(f"🗣️ Fahreranfrage: {text}")

                # Intent classification
                intent = await asyncio.to_thread(intent_classifier.classify, text)
                print(
                    f"→ Intent: {intent.action}, "
                    f"params={intent.parameters}, conf={intent.confidence:.2f}"
                )

                if intent.confidence < 0.4 or intent.action in ("unknown", "help"):
                    msg = (
                        "Ich kann dir bei Parkplatz, Essen, Hotel, Kaffee "
                        "und Haustierbetreuung helfen. "
                        f"Bitte sag '{WAKE_WORD}' und formuliere deine Anfrage noch einmal."
                    )
                    print(msg)
                    await asyncio.to_thread(tts_speak_blocking, msg)
                    waiting_for_request = False
                    waiting_for_wake_word = True
                    continue

                central_msg = build_central_message(intent, assistantAgent.address)
                if not central_msg:
                    msg = "Ich konnte keine passende Aktion finden."
                    print(msg)
                    await asyncio.to_thread(tts_speak_blocking, msg)
                    waiting_for_request = False
                    waiting_for_wake_word = True
                    continue

                # Send to CentralService
                await ctx.send(CENTRAL_SERVICE_ADDRESS, central_msg)
                print("📨 Anfrage an CentralService gesendet …")

                expected_replies = len(central_msg.messages)
                received_replies = 0
                awaiting_replies = expected_replies > 0
                waiting_for_request = False
                continue

        except KeyboardInterrupt:
            print("\n👋 Voice Assistant manuell beendet.")
            break
        except Exception as e:
            print(f"❌ Fehler im Voice-Loop: {e}")
            await asyncio.to_thread(
                tts_speak_blocking,
                "Es ist ein Fehler aufgetreten. Bitte versuche es erneut.",
            )
            waiting_for_wake_word = True
            waiting_for_request = False
            awaiting_replies = False


# =============================================================================
# AGENT INITIALIZATION HOOK
# =============================================================================

@assistantAgent.on_interval(period=1.0)
async def starter(ctx: Context):
    """
    Initialize voice assistant background tasks on first agent startup.
    
    Ensures voice_main() and speaker_loop() are started exactly once when
    the agent begins running. Uses global flag to prevent duplicate task
    creation on subsequent interval triggers.
    
    Background Tasks:
        1. speaker_loop(): Consumes reply_queue and speaks service responses
        2. voice_main(): Listens for wake word and handles user requests
    
    Args:
        ctx (Context): Agent context for voice_main loop
    
    Execution:
        - Triggered every 1.0 seconds by @on_interval decorator
        - Returns immediately after first execution (_started=True)
        - Both tasks run indefinitely until agent shutdown
    
    Notes:
        - Global _started flag prevents duplicate task creation
        - Tasks are created with asyncio.create_task (non-blocking)
        - No await needed - tasks run in background
        - Interval continues but has no effect after _started=True
    """
    global _started
    if _started:
        return
    _started = True

    asyncio.create_task(speaker_loop())
    asyncio.create_task(voice_main(ctx))


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Launch the voice assistant agent.
    
    Prerequisites:
        - Faster-Whisper: Speech-to-text transcription
        - Piper TTS: German voice synthesis (thorsten-low model)
        - Ollama: LLM service for intent classification
        - Intent classifier: Must be initialized in INTENT_CLASSIFIER
        - CentralService: Running at CENTRAL_SERVICE_ADDRESS
    
    Configuration:
        Modify constants at top of file:
        - WAKE_WORD: Change activation phrase
        - MAX_RECORD_SECONDS: Adjust request recording duration
        - CHUNK_SECONDS: Change wake word detection sensitivity
        - MODEL_SIZE: Faster-Whisper model (tiny/base/small/medium)
        - PIPER_MODEL: Path to Piper voice model
    
    Usage:
        python voice_assistant.py
        
        Then say "Hallo" to activate voice interaction.
    
    Monitoring:
        - Console output shows transcriptions and service responses
        - Emoji indicators: 🎧 (ready), 📨 (response), ❌ (error)
    
    Shutdown:
        Ctrl+C to stop (graceful shutdown)
    
    Notes:
        - Requires microphone and speakers
        - Audio devices auto-selected by sounddevice
        - CentralService must be running for service requests
        - LLM connection tested at startup
    """
    assistantAgent.run()
