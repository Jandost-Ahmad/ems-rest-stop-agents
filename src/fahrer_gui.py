import threading
import queue
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime, timedelta

import customtkinter as ctk
from PIL import Image, ImageTk

from uagents import Agent, Context, Model

# Shared queues
command_queue = queue.Queue()
message_queue = queue.Queue()


# ---------- Message Model ----------
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



# Driver Presets
DRIVER_PRESETS = {
    "Benutzerdefiniert": {
        "vehicle": "PKW",
        "parkplatz": "mit Ladesäule",
        "behindert": False,
        "park_zeit": "60",
        "essen": "Standard",
        "to_go": False,
        "icon": "🎯",
        "color": "#3B82F6"
    },
    "LKW-Fahrer": {
        "vehicle": "LKW",
        "parkplatz": "mit Ladesäule",
        "behindert": False,
        "park_zeit": "480",
        "essen": "Standard",
        "to_go": False,
        "icon": "🚚",
        "color": "#10B981"
    },
    "Pendler": {
        "vehicle": "PKW",
        "parkplatz": "ohne Ladesäule",
        "behindert": False,
        "park_zeit": "30",
        "essen": "Standard",
        "to_go": True,
        "icon": "☕",
        "color": "#F59E0B"
    },
    
 
    "Familie": {
        "vehicle": "PKW",
        "parkplatz": "ohne Ladesäule",
        "behindert": False,
        "park_zeit": "120",
        "essen": "Standard",
        "to_go": False,
        "parking_enabled": True,
        "food_enabled": False,
        "hotel_enabled": False,
        "kaffee_enabled": False,
        "haustier_enabled": True,
        "pet_type": "hund",
        "pet_von": "10:00",
        "pet_bis": "11:30",
        "icon": "👨‍👩‍👧",
        "color": "#EC4899"
    },
    "Reisebus": {
        "vehicle": "Bus",
        "parkplatz": "mit Ladesäule",
        "behindert": False,
        "park_zeit": "180",
        "essen": "Standard",
        "to_go": False,
        "icon": "🚌",
        "color": "#8B5CF6"
    },
}


# Agent setup
FAHRER_GUI_PORT = 8003
fahrerAgent = Agent(
    name="FahrerGUI",
    port=FAHRER_GUI_PORT,
    seed="fahrerGuiSeed",
    endpoint=[f"http://100.118.74.109:{FAHRER_GUI_PORT}/submit"],
)

#PARKPLATZ_ADDRESS = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
#ESSENS_ADDRESS = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"
#HOTEL_ADDRESS = "test-agent://agent1q2ar07qp4r8kale8pz2w5paefx90lf8w8z05xuja43rrwc75mw5j2s6e0zj"
#KAFFEE_ADDRESS = "test-agent://agent1q2u5pp8cuq0fdzrh94842mu6scwyfv9ese0amr872t0xmdy9mfdncedjv7l"
#HAUSTIER_ADDRESS = "test-agent://agent1qffjvchcs36qed3ghwng43l9zw4x3pefxck3t8rsdsakkaww9trpwyh9qx0"

# Replace this with the CentralService agent address printed when the CentralService starts.
# Example: set to the value printed by CentralService or the one used by your voice assistant.
CENTRAL_SERVICE_ADDRESS = "test-agent://agent1qdxu32w99hg82pmqvulkxttpvqpctvp2vya4w9d2mnl9rhj03mt464747cc"

last_ctx = None


@fahrerAgent.on_message(model=Message)
async def on_message(ctx: Context, sender: str, msg: Message):
    display_sender = getattr(msg, "sender_name", None) or sender
    message_queue.put(
        (
            display_sender,
            getattr(msg, "message", ""),
            getattr(msg, "reservation_id", None),
        )
    )


@fahrerAgent.on_interval(period=1.0)
async def process_commands(ctx: Context):
    global last_ctx
    last_ctx = ctx
    try:
        while True:
            cmd = command_queue.get_nowait()
            if cmd["action"] == "send_booking":
                data = cmd["data"]

                # Build central message with all selected service messages
                msgs = []
                now_str = datetime.now().strftime("%H:%M")

                # Parking
                if data.get("park"):
                    # generate a reservation id for parking
                    reservation_id = f"res-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    ladestation = "Ladesäule" in (data.get("parkplatz_option") or "") or "Lade" in (data.get("parkplatz_option") or "")
                    park_msg = {
                        "type": "parkplatz",
                        "fahrzeugart": data.get("vehicle", "PKW"),
                        "ladestation": bool(ladestation),
                        "zeit": data.get("park_zeit") or now_str,
                        "reservation_id": reservation_id,
                        "client_sender": fahrerAgent.address,
                    }
                    msgs.append(park_msg)

                # Food (essensservice)
                if data.get("essen"):
                    food = data.get("essen_option", "Standard")
                    essen_msg = {
                        "type": "essensservice",
                        "zeit": data.get("bestell_zeit") or now_str,
                        "standard": 1 if food == "Standard" else 0,
                        "vegetarisch": 1 if food == "Vegetarisch" else 0,
                        "vegan": 1 if food == "Vegan" else 0,
                        "glutenfrei": 1 if food == "Glutenfrei" else 0,
                        "client_sender": fahrerAgent.address,
                    }
                    msgs.append(essen_msg)

                # Hotel
                if data.get("hotel"):
                    hotel_msg = {
                        "type": "hotel",
                        "zimmerart": data.get("hotel_room", "einzel"),
                        "zeit": data.get("hotel_time") or now_str,
                        "naechte": int(data.get("hotel_nights", 1)),
                        "client_sender": fahrerAgent.address,
                    }
                    msgs.append(hotel_msg)

                # Kaffee
                if data.get("kaffee"):
                    kaffee_msg = {
                        "type": "kaffee",
                        "zeit": data.get("kaffee_time") or now_str,
                        "client_sender": fahrerAgent.address,
                    }
                    msgs.append(kaffee_msg)

                # Haustierbetreuung
                if data.get("haustier"):
                    haustier_msg = {
                        "type": "haustierbetreuung",
                        "haustierart": data.get("haustier_type", "hund"),
                        "zeit": now_str,
                        "betreuung_von": data.get("pet_von"),
                        "betreuung_bis": data.get("pet_bis"),
                        "client_sender": fahrerAgent.address,
                    }
                    msgs.append(haustier_msg)

                # Send the combined message to CentralService
                if msgs:
                    try:
                        central_msg = CentralServiceMessage(messages=msgs)
                        await ctx.send(CENTRAL_SERVICE_ADDRESS, central_msg)
                        message_queue.put(("System", f"✓ Anfrage an CentralService gesendet ({len(msgs)} Nachrichten)", None))
                    except Exception as e:
                        message_queue.put(("Error", f"✗ Fehler beim Senden an CentralService: {e}", None))
            elif cmd["action"] == "extend":
                minutes = cmd.get("minutes", 30)
                # Send an extend request via CentralService to keep GUI using only central
                try:
                    # reservation id not known at GUI level here; send empty and let central/parkplatz handle
                    extend_entry = {
                        "type": "parkplatz_extend",
                        "reservation_id": "",
                        "minutes": int(minutes),
                        "client_sender": fahrerAgent.address,
                    }
                    central_msg = CentralServiceMessage(messages=[extend_entry])
                    await ctx.send(CENTRAL_SERVICE_ADDRESS, central_msg)
                    message_queue.put(("System", f"✓ Verlängerungs-Anfrage an CentralService gesendet (+{minutes}min)", None))
                except Exception as e:
                    message_queue.put(("Error", f"✗ Fehler beim Senden der Verlängerung: {e}", None))
            command_queue.task_done()
    except queue.Empty:
        pass


# ========== FUTURISTIC GUI ==========
class FahrerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Futuristic Dark Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("🚗 DRIVER ASSISTANCE SYSTEM")
        # use a smaller default window so it fits smaller screens
        self.geometry("900x650")
        # set a sensible minimum size (width, height)
        self.minsize(800, 550)

        # Custom colors - Automotive HMI inspired
        self.colors = {
            "bg_primary": "#0A0E27",      # Deep space blue
            "bg_secondary": "#141B3D",    # Card background
            "bg_tertiary": "#1E2749",     # Hover state
            "accent_blue": "#00D9FF",     # Cyan glow
            "accent_green": "#00FF88",    # Success green
            "accent_orange": "#FF8C00",   # Warning orange
            "accent_purple": "#B794F6",   # Info purple
            "text_primary": "#FFFFFF",
            "text_secondary": "#8B95B8",
            "glow": "#00D9FF",
        }

        # Configure window
        self.configure(fg_color=self.colors["bg_primary"])

        self.last_reservation_id = None
        self.selected_preset = None
        self.ignore_preset_change = False
        # currently selected driver profile
        self.driver_profile = tk.StringVar(value="Benutzerdefiniert")

        self.create_widgets()
        self.poll_messages()

    def create_widgets(self):
        # Main container with padding
        main = ctk.CTkFrame(self, fg_color="transparent")
        # reduced padding to save vertical space
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # ========== HEADER ==========
        header = ctk.CTkFrame(main, fg_color=self.colors["bg_secondary"], corner_radius=15, height=80)
        header.pack(fill=tk.X, pady=(0, 10))
        header.pack_propagate(False)

        # Title with glow effect
        title = ctk.CTkLabel(
            header,
            text="⚡ DRIVER ASSISTANCE SYSTEM",
            font=("Orbitron", 22, "bold"),
            text_color=self.colors["accent_blue"]
        )
        title.pack(side=tk.LEFT, padx=20)

        # Status indicator
        self.status_label = ctk.CTkLabel(
            header,
            text="● SYSTEM READY",
            font=("Rajdhani", 14),
            text_color=self.colors["accent_green"]
        )
        self.status_label.pack(side=tk.RIGHT, padx=20)

        # ========== PRESET SELECTOR (CARDS) ==========
        preset_frame = ctk.CTkFrame(main, fg_color="transparent")
        preset_frame.pack(fill=tk.X, pady=(0, 15))

        # header with title and a Send button so user can send after selecting a profile
        preset_header = ctk.CTkFrame(preset_frame, fg_color="transparent")
        preset_header.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(
            preset_header,
            text="SELECT DRIVER PROFILE",
            font=("Rajdhani", 16, "bold"),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        # small send button on the right of the header
        # send_profile_button = ctk.CTkButton(
        #     preset_header,
        #     text="Senden",
        #     width=140,
        #     height=34,
        #     fg_color=self.colors["accent_green"],
        #     command=self.send_booking
        # )
        # send_profile_button.pack(side=tk.RIGHT)

        # Preset cards grid
        cards_container = ctk.CTkFrame(preset_frame, fg_color="transparent")
        cards_container.pack(fill=tk.X)

        self.preset_buttons = {}
        for idx, (name, preset) in enumerate(DRIVER_PRESETS.items()):
            card = self.create_preset_card(cards_container, name, preset)
            card.grid(row=0, column=idx, padx=8, sticky="ew")
            cards_container.columnconfigure(idx, weight=1, uniform="preset")

        # ========== CONTROL PANEL (scrollable) ==========
        # Use a Canvas + vertical scrollbar so the whole control area can be scrolled
        # when the window is too small to show everything.
        scroll_container = ctk.CTkFrame(main, fg_color="transparent")
        scroll_container.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling and native tk Scrollbar for visibility
        canvas = tk.Canvas(scroll_container, bg=self.colors["bg_primary"], highlightthickness=0)
        vscroll = tk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame placed inside the canvas
        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        self._canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        # Keep references so they are not garbage collected
        self._main_canvas = canvas

        def _on_inner_config(event):
            # update scrollregion when inner frame changes
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(event):
            # make inner frame width match canvas width
            try:
                canvas.itemconfig(self._canvas_window, width=event.width)
            except Exception:
                pass

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)

        # Mouse wheel support (Windows)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Create the actual control panel inside the scrollable inner frame
        control_panel = ctk.CTkFrame(inner, fg_color="transparent")
        control_panel.pack(fill=tk.BOTH, expand=True)

        # Left side - Controls
        left_panel = ctk.CTkFrame(control_panel, fg_color="transparent")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Vehicle & Parking Card
        self.create_vehicle_card(left_panel)

        # Food Order Card
        self.create_food_card(left_panel)

        # Additional services: Hotel, Kaffee, Haustier
        self.create_hotel_card(left_panel)
        self.create_kaffee_card(left_panel)
        self.create_haustier_card(left_panel)

        # Action Buttons
        self.create_action_buttons(left_panel)

        # Right side - Activity Log
        self.create_activity_log(control_panel)

    def create_preset_card(self, parent, name, preset):
        """Create a futuristic preset card"""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.colors["bg_secondary"],
            corner_radius=12,
            border_width=2,
            border_color=self.colors["bg_tertiary"]
        )

        # Icon
        ctk.CTkLabel(
            card,
            text=preset["icon"],
            font=("Segoe UI Emoji", 32)
        ).pack(pady=(15, 5))

        # Name
        ctk.CTkLabel(
            card,
            text=name,
            font=("Rajdhani", 14, "bold"),
            text_color=self.colors["text_primary"]
        ).pack()

        # Select button
        btn = ctk.CTkButton(
            card,
            text="SELECT",
            width=100,
            height=30,
            corner_radius=8,
            fg_color=preset["color"],
            hover_color=self.lighten_color(preset["color"]),
            font=("Rajdhani", 12, "bold"),
            command=lambda: self.select_preset(name, card)
        )
        btn.pack(pady=(5, 15))

        card.pack_propagate(False)
        card.configure(height=130)

        self.preset_buttons[name] = (card, btn)
        return card

    def create_vehicle_card(self, parent):
        """Vehicle and parking controls"""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], corner_radius=15)
        card.pack(fill=tk.X, pady=(0, 15))

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="🚗 VEHICLE & PARKING",
            font=("Rajdhani", 18, "bold"),
            text_color=self.colors["accent_blue"]
        ).pack(side=tk.LEFT)
        # enable/disable parking service
        self.parking_enabled = tk.BooleanVar(value=True)
        ctk.CTkSwitch(header, text="", variable=self.parking_enabled, command=lambda: self.toggle_parking(self.parking_enabled.get())).pack(side=tk.RIGHT)

        # Content
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill=tk.X, padx=20, pady=(0, 15))

        # Row 1: Vehicle type
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(
            row1,
            text="Vehicle Type",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        self.vehicle_var = tk.StringVar(value="PKW")
        self.vehicle_menu = ctk.CTkOptionMenu(
            row1,
            values=["PKW", "LKW", "Bus"],
            variable=self.vehicle_var,
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.colors["bg_tertiary"],
            button_color=self.colors["accent_blue"],
            button_hover_color=self.lighten_color(self.colors["accent_blue"]),
            font=("Rajdhani", 14, "bold"),
            dropdown_font=("Rajdhani", 12),
            command=lambda x: self.on_manual_change()
        )
        self.vehicle_menu.pack(side=tk.RIGHT)

        # Row 2: Parking option
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(
            row2,
            text="Charging Station",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        self.parkplatz_var = tk.StringVar(value="mit Ladesäule")
        self.parking_menu = ctk.CTkOptionMenu(
            row2,
            values=["mit Ladesäule", "ohne Ladesäule"],
            variable=self.parkplatz_var,
            width=180,
            height=40,
            corner_radius=10,
            fg_color=self.colors["bg_tertiary"],
            button_color=self.colors["accent_green"],
            button_hover_color=self.lighten_color(self.colors["accent_green"]),
            font=("Rajdhani", 14, "bold"),
            dropdown_font=("Rajdhani", 12),
            command=lambda x: self.on_manual_change()
        )
        self.parking_menu.pack(side=tk.RIGHT)

        # Row 3: Duration + Quick buttons
        row3 = ctk.CTkFrame(content, fg_color="transparent")
        row3.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(
            row3,
            text="⏱️ Duration",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        quick_frame = ctk.CTkFrame(row3, fg_color="transparent")
        quick_frame.pack(side=tk.RIGHT)

        self.parkzeit_entry = ctk.CTkEntry(
            quick_frame,
            width=80,
            height=40,
            corner_radius=10,
            font=("Rajdhani", 16, "bold"),
            fg_color=self.colors["bg_tertiary"],
            border_color=self.colors["accent_blue"],
            border_width=2
        )
        self.parkzeit_entry.insert(0, "60")
        self.parkzeit_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.parkzeit_entry.bind("<KeyRelease>", lambda e: self.on_manual_change())

        # Quick time buttons
        for time_text, minutes in [("30m", 30), ("1h", 60), ("2h", 120), ("8h", 480)]:
            ctk.CTkButton(
                quick_frame,
                text=time_text,
                width=50,
                height=40,
                corner_radius=10,
                fg_color=self.colors["bg_tertiary"],
                hover_color=self.colors["accent_blue"],
                font=("Rajdhani", 12, "bold"),
                command=lambda m=minutes: self.set_park_time(m)
            ).pack(side=tk.LEFT, padx=2)

        # Row 4: Disabled parking switch
        row4 = ctk.CTkFrame(content, fg_color="transparent")
        row4.pack(fill=tk.X)

        ctk.CTkLabel(
            row4,
            text="♿ Disabled Parking",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        self.behindert_var = tk.BooleanVar(value=False)
        self.behindert_switch = ctk.CTkSwitch(
            row4,
            text="",
            variable=self.behindert_var,
            width=60,
            height=30,
            progress_color=self.colors["accent_green"],
            button_color=self.colors["text_primary"],
            button_hover_color=self.colors["accent_blue"],
            command=self.on_manual_change
        )
        self.behindert_switch.pack(side=tk.RIGHT)
        # parking widgets list for toggling
        self._parking_widgets = [getattr(self, 'vehicle_menu', None), getattr(self, 'parking_menu', None), getattr(self, 'parkzeit_entry', None), self.behindert_switch]

    def create_food_card(self, parent):
        """Food order controls"""
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], corner_radius=15)
        card.pack(fill=tk.X, pady=(0, 15))

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="🍽️ FOOD SERVICE",
            font=("Rajdhani", 18, "bold"),
            text_color=self.colors["accent_green"]
        ).pack(side=tk.LEFT)

        # Content
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill=tk.X, padx=20, pady=(0, 15))

        # Row 1: Menu
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(0, 10))

        ctk.CTkLabel(
            row1,
            text="Menu Selection",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        self.essen_var = tk.StringVar(value="Standard")
        self.food_menu = ctk.CTkOptionMenu(
            row1,
            values=["Standard", "Vegetarisch", "Vegan", "Glutenfrei"],
            variable=self.essen_var,
            width=180,
            height=40,
            corner_radius=10,
            fg_color=self.colors["bg_tertiary"],
            button_color=self.colors["accent_green"],
            button_hover_color=self.lighten_color(self.colors["accent_green"]),
            font=("Rajdhani", 14, "bold"),
            dropdown_font=("Rajdhani", 12),
            command=lambda x: self.on_manual_change()
        )
        self.food_menu.pack(side=tk.RIGHT)

        # Row 2: To-Go switch
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill=tk.X)

        ctk.CTkLabel(
            row2,
            text="🥤 Take Away",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT)

        self.togo_var = tk.BooleanVar(value=False)
        self.togo_switch = ctk.CTkSwitch(
            row2,
            text="",
            variable=self.togo_var,
            width=60,
            height=30,
            progress_color=self.colors["accent_orange"],
            button_color=self.colors["text_primary"],
            button_hover_color=self.colors["accent_blue"],
            command=self.on_manual_change
        )
        self.togo_switch.pack(side=tk.RIGHT)
        # food enable switch in header
        self.food_enabled = tk.BooleanVar(value=True)
        ctk.CTkSwitch(header, text="", variable=self.food_enabled, command=lambda: self.toggle_food(self.food_enabled.get())).pack(side=tk.RIGHT)
        self._food_widgets = [self.food_menu, self.togo_switch]

    def create_hotel_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], corner_radius=15)
        card.pack(fill=tk.X, pady=(0, 15))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))
        ctk.CTkLabel(header, text="🏨 HOTEL", font=("Rajdhani", 18, "bold"), text_color=self.colors["accent_purple"]).pack(side=tk.LEFT)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill=tk.X, padx=20, pady=(0, 15))

        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(0, 8))
        ctk.CTkLabel(row1, text="Zimmertyp", font=("Rajdhani", 13), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.hotel_type = tk.StringVar(value="familie")
        ctk.CTkOptionMenu(row1, values=["einzel", "doppel", "familie"], variable=self.hotel_type, width=160).pack(side=tk.RIGHT)

        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill=tk.X, pady=(0, 8))
        ctk.CTkLabel(row2, text="Ankunftszeit (HH:MM)", font=("Rajdhani", 13), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.hotel_time = ctk.CTkEntry(row2, width=100)
        self.hotel_time.insert(0, datetime.now().strftime("%H:%M"))
        self.hotel_time.pack(side=tk.RIGHT)

        row3 = ctk.CTkFrame(content, fg_color="transparent")
        row3.pack(fill=tk.X)
        ctk.CTkLabel(row3, text="Nächte", font=("Rajdhani", 13), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.hotel_nights = tk.IntVar(value=1)
        self.hotel_nights_entry = ctk.CTkEntry(row3, width=60, textvariable=self.hotel_nights)
        self.hotel_nights_entry.pack(side=tk.RIGHT)
        # keep references for enable/disable
        self._hotel_widgets = [self.hotel_time, self.hotel_nights_entry]

    def create_kaffee_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], corner_radius=15)
        card.pack(fill=tk.X, pady=(0, 15))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))
        ctk.CTkLabel(header, text="☕ KAFFEE", font=("Rajdhani", 18, "bold"), text_color=self.colors["accent_green"]).pack(side=tk.LEFT)
        self.kaffee_enabled = tk.BooleanVar(value=True)
        ctk.CTkSwitch(header, text="", variable=self.kaffee_enabled, command=lambda: self.toggle_kaffee(self.kaffee_enabled.get())).pack(side=tk.RIGHT)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill=tk.X, padx=20, pady=(0, 15))
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill=tk.X)
        ctk.CTkLabel(row1, text="Abholzeit (HH:MM)", font=("Rajdhani", 13), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.kaffee_time = ctk.CTkEntry(row1, width=100)
        self.kaffee_time.insert(0, (datetime.now() + timedelta(minutes=5)).strftime("%H:%M"))
        self.kaffee_time.pack(side=tk.RIGHT)
        self._kaffee_widgets = [self.kaffee_time]

    def create_haustier_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["bg_secondary"], corner_radius=15)
        card.pack(fill=tk.X, pady=(0, 15))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))
        ctk.CTkLabel(header, text="🐾 HAUSTIERBETREUUNG", font=("Rajdhani", 18, "bold"), text_color=self.colors["accent_green"]).pack(side=tk.LEFT)
        self.haustier_enabled = tk.BooleanVar(value=True)
        ctk.CTkSwitch(header, text="", variable=self.haustier_enabled, command=lambda: self.toggle_haustier(self.haustier_enabled.get())).pack(side=tk.RIGHT)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill=tk.X, padx=20, pady=(0, 15))
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill=tk.X, pady=(0, 8))
        ctk.CTkLabel(row1, text="Tier", font=("Rajdhani", 13), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.pet_type = tk.StringVar(value="hund")
        self.pet_menu = ctk.CTkOptionMenu(row1, values=["hund", "katze"], variable=self.pet_type, width=120)
        self.pet_menu.pack(side=tk.RIGHT)

        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill=tk.X)
        ctk.CTkLabel(row2, text="Betreuung von (HH:MM)", font=("Rajdhani", 12), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT)
        self.pet_von = ctk.CTkEntry(row2, width=100)
        self.pet_von.insert(0, "20:00")
        self.pet_von.pack(side=tk.LEFT, padx=(8,0))
        ctk.CTkLabel(row2, text="bis (HH:MM)", font=("Rajdhani", 12), text_color=self.colors["text_secondary"]).pack(side=tk.LEFT, padx=(12,0))
        self.pet_bis = ctk.CTkEntry(row2, width=100)
        self.pet_bis.insert(0, "07:00")
        self.pet_bis.pack(side=tk.LEFT, padx=(8,0))
        # keep references for enable/disable
        self._haustier_widgets = [self.pet_menu, self.pet_von, self.pet_bis]

    def create_action_buttons(self, parent):
        """Create action buttons"""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        # Main action button (large)
        self.send_btn = ctk.CTkButton(
            btn_frame,
            text="⚡ SEND BOOKING",
            height=60,
            corner_radius=15,
            fg_color=self.colors["accent_blue"],
            hover_color=self.lighten_color(self.colors["accent_blue"]),
            font=("Rajdhani", 18, "bold"),
            command=self.send_booking
        )
        self.send_btn.pack(fill=tk.X, pady=(0, 10))

        # Extension buttons
        ext_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        ext_frame.pack(fill=tk.X)

        ctk.CTkLabel(
            ext_frame,
            text="EXTEND PARKING:",
            font=("Rajdhani", 12),
            text_color=self.colors["text_secondary"]
        ).pack(side=tk.LEFT, padx=(0, 10))

        for time_text, minutes in [("+15min", 15), ("+30min", 30), ("+60min", 60)]:
            ctk.CTkButton(
                ext_frame,
                text=time_text,
                width=100,
                height=40,
                corner_radius=10,
                fg_color=self.colors["accent_orange"],
                hover_color=self.lighten_color(self.colors["accent_orange"]),
                font=("Rajdhani", 13, "bold"),
                command=lambda m=minutes: self.extend(m)
            ).pack(side=tk.LEFT, padx=5)

        # Reservation info
        self.res_label = ctk.CTkLabel(
            parent,
            text="📋 Last Reservation: -",
            font=("Rajdhani", 13),
            text_color=self.colors["text_secondary"]
        )
        self.res_label.pack(anchor="w")

    def create_activity_log(self, parent):
        """Create activity log panel"""
        right_panel = ctk.CTkFrame(
            parent,
            fg_color=self.colors["bg_secondary"],
            corner_radius=15,
              width=280
        )
        # Allow the right panel (activity log) to expand when the window is resized
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        # Allow children to control sizing so the Text widget can grow/shrink
        right_panel.pack_propagate(True)

        # Header
        header = ctk.CTkFrame(right_panel, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="📡 SYSTEM LOG",
            font=("Rajdhani", 18, "bold"),
            text_color=self.colors["accent_purple"]
        ).pack(side=tk.LEFT)

        # Log text
        log_frame = ctk.CTkFrame(right_panel, fg_color=self.colors["bg_primary"], corner_radius=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        self.log = tk.Text(
            log_frame,
            wrap=tk.WORD,
            bg=self.colors["bg_primary"],
            fg=self.colors["text_primary"],
            font=("Consolas", 10),
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.configure(state=tk.DISABLED)

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.configure(yscrollcommand=scrollbar.set)

    # ========== FUNCTIONALITY ==========
    def select_preset(self, name, card):
        """Handle preset selection"""
        if self.ignore_preset_change:
            return

        self.selected_preset = name
        # keep driver_profile in sync with selection
        try:
            self.driver_profile.set(name)
        except Exception:
            pass
        preset = DRIVER_PRESETS[name]

        # Update all cards appearance
        for preset_name, (preset_card, btn) in self.preset_buttons.items():
            if preset_name == name:
                preset_card.configure(border_color=preset["color"], border_width=3)
            else:
                preset_card.configure(border_color=self.colors["bg_tertiary"], border_width=2)

        # Load preset values
        self.ignore_preset_change = True
        self.vehicle_var.set(preset["vehicle"])
        self.parkplatz_var.set(preset["parkplatz"])
        self.behindert_var.set(preset["behindert"])
        self.parkzeit_entry.delete(0, tk.END)
        self.parkzeit_entry.insert(0, preset["park_zeit"])
        self.essen_var.set(preset["essen"])
        self.togo_var.set(preset["to_go"])
        # Apply service enable/disable flags if present in preset
        # Parking
        if "parking_enabled" in preset:
            try:
                self.parking_enabled.set(bool(preset.get("parking_enabled")))
            except Exception:
                pass
            self.toggle_parking(self.parking_enabled.get())

        # Food
        if "food_enabled" in preset:
            try:
                self.food_enabled.set(bool(preset.get("food_enabled")))
            except Exception:
                pass
            self.toggle_food(self.food_enabled.get())

        # Hotel
        if "hotel_enabled" in preset:
            try:
                self.hotel_enabled = getattr(self, 'hotel_enabled', tk.BooleanVar(value=False))
                self.hotel_enabled.set(bool(preset.get("hotel_enabled")))
            except Exception:
                pass
            # ensure widget list toggled
            self.toggle_hotel(getattr(self, 'hotel_enabled', tk.BooleanVar(value=False)).get())

        # Kaffee
        if "kaffee_enabled" in preset:
            try:
                self.kaffee_enabled.set(bool(preset.get("kaffee_enabled")))
            except Exception:
                pass
            self.toggle_kaffee(self.kaffee_enabled.get())

        # Haustier
        if "haustier_enabled" in preset:
            try:
                self.haustier_enabled.set(bool(preset.get("haustier_enabled")))
            except Exception:
                pass
            # If pet times not explicitly defined, match pet times to parking duration
            try:
                park_minutes = int(self.parkzeit_entry.get())
            except Exception:
                park_minutes = None

            if preset.get("pet_von") and preset.get("pet_bis"):
                # use preset provided times
                try:
                    self.pet_von.delete(0, tk.END)
                    self.pet_von.insert(0, preset.get("pet_von"))
                    self.pet_bis.delete(0, tk.END)
                    self.pet_bis.insert(0, preset.get("pet_bis"))
                except Exception:
                    pass
            else:
                # default: set pet_von = now, pet_bis = now + park_minutes
                if park_minutes:
                    now = datetime.now()
                    von = now.strftime("%H:%M")
                    bis = (now + timedelta(minutes=park_minutes)).strftime("%H:%M")
                    try:
                        self.pet_von.delete(0, tk.END)
                        self.pet_von.insert(0, von)
                        self.pet_bis.delete(0, tk.END)
                        self.pet_bis.insert(0, bis)
                    except Exception:
                        pass

            self.toggle_haustier(self.haustier_enabled.get())

        self.ignore_preset_change = False

        self.log_message("System", f"✓ Profile loaded: {name}")

    def on_manual_change(self):
        """Handle manual changes"""
        if not self.ignore_preset_change and self.selected_preset != "Benutzerdefiniert":
            self.select_preset("Benutzerdefiniert", None)

    def set_park_time(self, minutes):
        """Set parking time"""
        self.parkzeit_entry.delete(0, tk.END)
        self.parkzeit_entry.insert(0, str(minutes))
        self.on_manual_change()

    def _set_widgets_enabled(self, widgets, enabled: bool):
        state = "normal" if enabled else "disabled"
        for w in widgets:
            if w is None:
                continue
            try:
                w.configure(state=state)
            except Exception:
                # best-effort: skip widgets that don't support state
                pass

    def toggle_parking(self, enabled: bool):
        self._set_widgets_enabled(getattr(self, '_parking_widgets', []), enabled)
        self.log_message("System", f"Parking service {'enabled' if enabled else 'disabled'}")

    def toggle_food(self, enabled: bool):
        self._set_widgets_enabled(getattr(self, '_food_widgets', []), enabled)
        self.log_message("System", f"Food service {'enabled' if enabled else 'disabled'}")

    def toggle_hotel(self, enabled: bool):
        self._set_widgets_enabled(getattr(self, '_hotel_widgets', []), enabled)
        self.log_message("System", f"Hotel service {'enabled' if enabled else 'disabled'}")

    def toggle_kaffee(self, enabled: bool):
        self._set_widgets_enabled(getattr(self, '_kaffee_widgets', []), enabled)
        self.log_message("System", f"Kaffee service {'enabled' if enabled else 'disabled'}")

    def toggle_haustier(self, enabled: bool):
        self._set_widgets_enabled(getattr(self, '_haustier_widgets', []), enabled)
        self.log_message("System", f"Haustier service {'enabled' if enabled else 'disabled'}")

    def log_message(self, sender, text, reservation_id=None):
        """Add message to log"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state=tk.NORMAL)
        
        # Color coding
        if "Error" in sender or "✗" in text:
            color = "#FF5555"
        elif "✓" in text:
            color = self.colors["accent_green"]
        else:
            color = self.colors["accent_blue"]
            
        self.log.insert(tk.END, f"[{ts}] ", "timestamp")
        self.log.insert(tk.END, f"{sender}: ", "sender")
        self.log.insert(tk.END, f"{text}\n", "message")
        
        self.log.tag_config("timestamp", foreground=self.colors["text_secondary"])
        self.log.tag_config("sender", foreground=color, font=("Consolas", 10, "bold"))
        self.log.tag_config("message", foreground=self.colors["text_primary"])
        
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        
        if reservation_id:
            self.last_reservation_id = reservation_id
            self.res_label.configure(text=f"📋 Last Reservation: {reservation_id}")

    def poll_messages(self):
        """Poll for new messages"""
        try:
            while True:
                sender, text, rid = message_queue.get_nowait()
                self.log_message(sender, text, rid)
        except queue.Empty:
            pass
        self.after(300, self.poll_messages)

    def send_booking(self):
        """Send booking request"""
        # Visual feedback
        self.send_btn.configure(fg_color=self.colors["accent_green"])
        self.after(200, lambda: self.send_btn.configure(fg_color=self.colors["accent_blue"]))
        
        data = {
            "driver_profile": self.driver_profile.get(),
            "park": getattr(self, 'parking_enabled', tk.BooleanVar(value=True)).get(),
            "vehicle": self.vehicle_var.get(),
            "parkplatz_option": self.parkplatz_var.get(),
            "behindert": self.behindert_var.get(),
            "park_zeit": self.parkzeit_entry.get(),
            "essen": getattr(self, 'food_enabled', tk.BooleanVar(value=True)).get(),
            "essen_option": self.essen_var.get(),
            "to_go": self.togo_var.get(),
            "bestell_zeit": None,
            # hotel
            "hotel": getattr(self, 'hotel_enabled', tk.BooleanVar(value=False)).get(),
            "hotel_room": getattr(self, "hotel_type", tk.StringVar(value="familie")).get(),
            "hotel_time": getattr(self, "hotel_time", None).get() if hasattr(self, "hotel_time") else None,
            "hotel_nights": getattr(self, "hotel_nights", tk.IntVar(value=1)).get() if hasattr(self, "hotel_nights") else 1,
            # kaffee
            "kaffee": getattr(self, 'kaffee_enabled', tk.BooleanVar(value=False)).get(),
            "kaffee_time": getattr(self, "kaffee_time", None).get() if hasattr(self, "kaffee_time") else None,
            # haustier
            "haustier": getattr(self, 'haustier_enabled', tk.BooleanVar(value=False)).get(),
            "haustier_type": getattr(self, "pet_type", tk.StringVar(value="hund")).get(),
            "pet_von": getattr(self, "pet_von", None).get() if hasattr(self, "pet_von") else None,
            "pet_bis": getattr(self, "pet_bis", None).get() if hasattr(self, "pet_bis") else None,
        }

        command_queue.put({"action": "send_booking", "data": data})
        self.log_message("System", "⚡ Transmitting booking request...")
        self.status_label.configure(text="● TRANSMITTING...", text_color=self.colors["accent_orange"])
        self.after(2000, lambda: self.status_label.configure(text="● SYSTEM READY", text_color=self.colors["accent_green"]))

    def extend(self, minutes: int):
        """Extend parking"""
        command_queue.put({"action": "extend", "minutes": minutes})
        self.log_message("System", f"⏱️ Extension request: +{minutes} min")

    def lighten_color(self, hex_color):
        """Lighten a hex color"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        lighter = tuple(min(255, int(c * 1.3)) for c in rgb)
        return f"#{lighter[0]:02x}{lighter[1]:02x}{lighter[2]:02x}"


def start_agent_thread():
    t = threading.Thread(target=lambda: fahrerAgent.run(), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    start_agent_thread()
    app = FahrerGUI()
    app.mainloop()