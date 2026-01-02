"""
voice_assistant.py

Voice Assistant Agent for your rest-stop simulation.

- Faster-Whisper (tiny) for STT
- Ollama + LLMIntentClassifier for intent → structured command
- Piper TTS for speech output (via CLI + WAV files)
- Talks to CentralService, which forwards to the service agents
- Uses a wake word ("DAINO") so it only listens when called
- Non-blocking: uses asyncio.to_thread so the agent can receive replies
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

# ============================================================
#                  SHARED MESSAGE MODELS
# ============================================================

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


# ============================================================
#                    CONFIGURATION
# ============================================================

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

# ============================================================
#              INIT STT + LLM + AGENT + QUEUE
# ============================================================

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
    """Use Faster-Whisper to transcribe audio file (blocking)."""
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
    """Use Piper CLI to synthesize and play speech (blocking)."""
    if not text:
        return

    try:
        # FIRST: Remove/replace emojis and problematic characters BEFORE any processing
        def clean_text_for_tts(s: str) -> str:
            """Remove emojis and sanitize text for TTS."""
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


# ============================================================
#           BUILD CENTRAL SERVICE MESSAGE FROM INTENT
# ============================================================

def build_central_message(intent: Intent, sender_address: str) -> CentralServiceMessage | None:
    """Turn an Intent into a CentralServiceMessage (list of service messages)."""
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


# ============================================================
#        RECEIVE REPLIES FROM SERVICES (NON-BLOCKING)
# ============================================================

@assistantAgent.on_message(model=Message)
async def on_service_reply(ctx: Context, sender: str, msg: Message):
    """
    Called when any service sends a reply.
    We push it to the queue for TTS and track how many replies we got.
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
    """Background task: read replies from queue and speak them one by one."""
    while True:
        msg: Message = await reply_queue.get()
        await asyncio.to_thread(tts_speak_blocking, msg.message)


# ============================================================
#              MAIN VOICE LOOP  (WAKE WORD)
# ============================================================

async def voice_main(ctx: Context):
    """
    Main voice interaction loop with wake word.

    Flow:
      1. Listen in short chunks until we hear the wake word
      2. Say: "Wie kann ich Ihnen helfen?"
      3. Record full request, classify, send to CentralService
      4. Wait until all service replies are spoken
      5. Go back to step 1
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


# ============================================================
#          STARTUP HOOK – START BACKGROUND TASKS ONCE
# ============================================================

@assistantAgent.on_interval(period=1.0)
async def starter(ctx: Context):
    """Start the voice loop + speaker loop once, without blocking the agent."""
    global _started
    if _started:
        return
    _started = True

    asyncio.create_task(speaker_loop())
    asyncio.create_task(voice_main(ctx))


# ============================================================
#                  RUN AGENT
# ============================================================

if __name__ == "__main__":
    assistantAgent.run()