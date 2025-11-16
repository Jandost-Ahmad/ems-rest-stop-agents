import threading
import queue
import tkinter as tk
from tkinter import scrolledtext

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from uagents import Agent, Context, Model
from datetime import datetime

# Shared queues
command_queue = queue.Queue()
message_queue = queue.Queue()


# ---------- Nachricht Modell ----------
class Message(Model):
    message: str
    zeit: str = None
    reservation_id: str = None
    sender_name: str = None


# Agent setup (will run in background thread)
FAHRER_GUI_PORT = 8003
fahrerAgent = Agent(
    name="FahrerGUI",
    port=FAHRER_GUI_PORT,
    seed="fahrerGuiSeed",
    endpoint=[f"http://localhost:{FAHRER_GUI_PORT}/submit"],
)

# Addresses (adapt if needed)
PARKPLATZ_ADDRESS = "test-agent://agent1qtctwqx03uw8d4fy86c4c6jp4g4d60ujcuqfd2hhkm3s8jmza0phu7t0hn9"
ESSENS_ADDRESS = "test-agent://agent1q0wfya9wt63ef7xuan3dp7ax7ycpdpn4ud72k9ljcd7u94phnm07cy8qek5"

last_ctx = None


@fahrerAgent.on_message(model=Message)
async def on_message(ctx: Context, sender: str, msg: Message):
    # forward to UI thread via message_queue
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
    # process commands from GUI
    global last_ctx
    last_ctx = ctx
    try:
        while True:
            cmd = command_queue.get_nowait()
            if cmd["action"] == "send_booking":
                data = cmd["data"]
                if data.get("park"):
                    txt = f"Ich suche einen {data['vehicle']}-Parkplatz {data['parkplatz_option']}"
                    if data.get("behindert"):
                        txt += " (Behindert)"
                    txt += "."
                    try:
                        await ctx.send(
                            PARKPLATZ_ADDRESS,
                            Message(message=txt, zeit=data.get("park_zeit")),
                        )
                        message_queue.put(("Local", f"Gesendet an Parkplatz: {txt}", None))
                    except Exception as e:
                        message_queue.put(
                            ("Error", f"Senden an Parkplatz fehlgeschlagen: {e}", None)
                        )
                if data.get("essen"):
                    txt = f"Ich möchte {data['essen_option']}-Essen bestellen."
                    if data.get("to_go"):
                        txt += " (To-Go)"
                    try:
                        await ctx.send(
                            ESSENS_ADDRESS,
                            Message(message=txt, zeit=data.get("bestell_zeit")),
                        )
                        message_queue.put(
                            ("Local", f"Gesendet an Essensservice: {txt}", None)
                        )
                    except Exception as e:
                        message_queue.put(
                            ("Error", f"Senden an Essensservice fehlgeschlagen: {e}", None)
                        )
            elif cmd["action"] == "extend":
                minutes = cmd.get("minutes", 30)
                try:
                    await ctx.send(
                        PARKPLATZ_ADDRESS,
                        Message(message=f"verlängern {minutes}min"),
                    )
                    message_queue.put(
                        ("Local", f"Verlängerung um {minutes}min angefordert", None)
                    )
                except Exception as e:
                    message_queue.put(
                        ("Error", f"Verlängerungsanfrage fehlgeschlagen: {e}", None)
                    )
            command_queue.task_done()
    except queue.Empty:
        pass


# -------- Modern GUI with ttkbootstrap --------
class FahrerGUI(tb.Window):
    def __init__(self):
        # choose a theme: flatly, superhero, darkly, cosmo, etc.
        super().__init__(themename="flatly")

        self.title("Fahrer GUI")
        self.geometry("800x520")
        self.minsize(720, 480)

        # slightly larger default font for tablet / touch
        self.option_add("*Font", ("Segoe UI", 10))

        self.last_reservation_id = None

        self.create_widgets()
        self.poll_messages()

    def create_widgets(self):
        # outer padding
        main = tb.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # ---- Top card: Booking controls ----
        booking_frame = tb.Labelframe(
            main, text="Buchung", padding=(12, 8), bootstyle="secondary"
        )
        booking_frame.pack(fill=tk.X, pady=(0, 8))

        # row 0: vehicle + parking + behindert
        tb.Label(booking_frame, text="Fahrzeug:").grid(
            row=0, column=0, sticky=W, padx=(0, 6), pady=4
        )
        self.vehicle_var = tk.StringVar(value="LKW")
        tb.Combobox(
            booking_frame,
            textvariable=self.vehicle_var,
            values=["PKW", "LKW"],
            width=10,
            state="readonly",
        ).grid(row=0, column=1, sticky=W, pady=4)

        tb.Label(booking_frame, text="Parkplatz:").grid(
            row=0, column=2, sticky=W, padx=(12, 6), pady=4
        )
        self.parkplatz_var = tk.StringVar(value="mit Ladesäule")
        tb.Combobox(
            booking_frame,
            textvariable=self.parkplatz_var,
            values=["mit Ladesäule", "ohne Ladesäule"],
            width=18,
            state="readonly",
        ).grid(row=0, column=3, sticky=W, pady=4)

        self.behindert_var = tk.BooleanVar(value=False)
        tb.Checkbutton(
            booking_frame,
            text="Behindert",
            variable=self.behindert_var,
            bootstyle="success",
        ).grid(row=0, column=4, sticky=W, padx=(12, 0), pady=4)

        # row 1: time + food + to-go
        tb.Label(booking_frame, text="Park bis (HH:MM oder min):").grid(
            row=1, column=0, sticky=W, padx=(0, 6), pady=4
        )
        self.parkzeit_entry = tb.Entry(booking_frame, width=10)
        self.parkzeit_entry.insert(0, "60")
        self.parkzeit_entry.grid(row=1, column=1, sticky=W, pady=4)

        tb.Label(booking_frame, text="Essen:").grid(
            row=1, column=2, sticky=W, padx=(12, 6), pady=4
        )
        self.essen_var = tk.StringVar(value="Standard")
        tb.Combobox(
            booking_frame,
            textvariable=self.essen_var,
            values=["Standard", "Vegetarisch", "Vegan", "Glutenfrei"],
            width=16,
            state="readonly",
        ).grid(row=1, column=3, sticky=W, pady=4)

        self.togo_var = tk.BooleanVar(value=False)
        tb.Checkbutton(
            booking_frame,
            text="To-Go",
            variable=self.togo_var,
            bootstyle="info",
        ).grid(row=1, column=4, sticky=W, padx=(12, 0), pady=4)

        # make columns stretch nicely
        booking_frame.columnconfigure(3, weight=1)

        # ---- Buttons ----
        btn_row = tb.Frame(main)
        btn_row.pack(fill=tk.X, pady=(0, 8))

        tb.Button(
            btn_row,
            text="Senden",
            bootstyle="success",
            command=self.send_booking,
            width=16,
        ).pack(side=tk.LEFT)

        tb.Button(
            btn_row,
            text="Verlängern +30min",
            bootstyle="secondary-outline",
            command=lambda: self.extend(30),
        ).pack(side=tk.LEFT, padx=6)

        tb.Button(
            btn_row,
            text="Verlängern +15min",
            bootstyle="secondary-outline",
            command=lambda: self.extend(15),
        ).pack(side=tk.LEFT, padx=6)

        # latest reservation label
        self.res_label = tb.Label(
            main, text="Letzte Reservierung: -", bootstyle="secondary"
        )
        self.res_label.pack(fill=tk.X, pady=(0, 4))

        # ---- Log card ----
        log_frame = tb.Labelframe(
            main, text="Aktivität", padding=(8, 6), bootstyle="secondary"
        )
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame,
            height=18,
            wrap=tk.WORD,
            relief="flat",
            borderwidth=1,
        )
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.configure(state=tk.DISABLED)

    # ------------- Behavior -------------
    def log_message(self, sender, text, reservation_id=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{ts}] {sender}: {text}\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        if reservation_id:
            self.last_reservation_id = reservation_id
            self.res_label.config(text=f"Letzte Reservierung: {reservation_id}")

    def poll_messages(self):
        try:
            while True:
                sender, text, rid = message_queue.get_nowait()
                self.log_message(sender, text, rid)
        except queue.Empty:
            pass
        self.after(300, self.poll_messages)

    def send_booking(self):
        data = {
            "park": True,
            "vehicle": self.vehicle_var.get(),
            "parkplatz_option": self.parkplatz_var.get(),
            "behindert": self.behindert_var.get(),
            "park_zeit": self.parkzeit_entry.get(),
            "essen": False,
            "essen_option": None,
            "to_go": False,
            "bestell_zeit": None,
        }
        # if user also selected Essen, set fields
        if self.essen_var.get():
            data["essen"] = True
            data["essen_option"] = self.essen_var.get()
            data["bestell_zeit"] = None
            data["to_go"] = self.togo_var.get()

        command_queue.put({"action": "send_booking", "data": data})
        self.log_message("Local", "Sende Buchungsanfrage...")

    def extend(self, minutes: int):
        command_queue.put({"action": "extend", "minutes": minutes})
        self.log_message("Local", f"Verlängerung um {minutes} Minuten angefordert")


def start_agent_thread():
    t = threading.Thread(target=lambda: fahrerAgent.run(), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    start_agent_thread()
    app = FahrerGUI()
    app.mainloop()
