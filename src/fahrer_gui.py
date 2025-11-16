import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext
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
    message_queue.put((display_sender, getattr(msg, "message", ""), getattr(msg, "reservation_id", None)))

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
                        await ctx.send(PARKPLATZ_ADDRESS, Message(message=txt, zeit=data.get("park_zeit")))
                        message_queue.put(("Local", f"Gesendet an Parkplatz: {txt}", None))
                    except Exception as e:
                        message_queue.put(("Error", f"Senden an Parkplatz fehlgeschlagen: {e}", None))
                if data.get("essen"):
                    txt = f"Ich möchte {data['essen_option']}-Essen bestellen."
                    if data.get("to_go"):
                        txt += " (To-Go)"
                    try:
                        await ctx.send(ESSENS_ADDRESS, Message(message=txt, zeit=data.get("bestell_zeit")))
                        message_queue.put(("Local", f"Gesendet an Essensservice: {txt}", None))
                    except Exception as e:
                        message_queue.put(("Error", f"Senden an Essensservice fehlgeschlagen: {e}", None))
            elif cmd["action"] == "extend":
                minutes = cmd.get("minutes", 30)
                # send extend command as text to Parkplatz
                try:
                    await ctx.send(PARKPLATZ_ADDRESS, Message(message=f"verlängern {minutes}min"))
                    message_queue.put(("Local", f"Verlängerung um {minutes}min angefordert", None))
                except Exception as e:
                    message_queue.put(("Error", f"Verlängerungsanfrage fehlgeschlagen: {e}", None))
            command_queue.task_done()
    except queue.Empty:
        pass

# GUI
class FahrerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fahrer GUI")
        self.geometry("700x500")
        self.create_widgets()
        self.poll_messages()
        self.last_reservation_id = None

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top: options
        top = ttk.Frame(frm)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Fahrzeug:").grid(column=0, row=0, sticky=tk.W)
        self.vehicle_var = tk.StringVar(value="PKW")
        ttk.Combobox(top, textvariable=self.vehicle_var, values=["PKW", "LKW"], width=8).grid(column=1, row=0)

        ttk.Label(top, text="Parkplatz:").grid(column=2, row=0, sticky=tk.W, padx=(10,0))
        self.parkplatz_var = tk.StringVar(value="ohne Ladesäule")
        ttk.Combobox(top, textvariable=self.parkplatz_var, values=["mit Ladesäule", "ohne Ladesäule"], width=16).grid(column=3, row=0)

        self.behindert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Behindert", variable=self.behindert_var).grid(column=4, row=0, padx=(10,0))

        ttk.Label(top, text="Park bis (HH:MM oder min):").grid(column=0, row=1, sticky=tk.W, pady=(6,0))
        self.parkzeit_entry = ttk.Entry(top)
        self.parkzeit_entry.insert(0, "60")
        self.parkzeit_entry.grid(column=1, row=1, sticky=tk.W)

        ttk.Label(top, text="Essen:").grid(column=2, row=1, sticky=tk.W, padx=(10,0))
        self.essen_var = tk.StringVar(value="Standard")
        ttk.Combobox(top, textvariable=self.essen_var, values=["Standard","Vegetarisch","Vegan","Glutenfrei"], width=12).grid(column=3, row=1)

        self.togo_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="To-Go", variable=self.togo_var).grid(column=4, row=1, padx=(10,0))

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=(10,0))
        send_btn = ttk.Button(btn_frame, text="Senden", command=self.send_booking)
        send_btn.pack(side=tk.LEFT)
        extend_btn = ttk.Button(btn_frame, text="Verlängern +30min", command=lambda: self.extend(30))
        extend_btn.pack(side=tk.LEFT, padx=(6,0))
        extend15_btn = ttk.Button(btn_frame, text="Verlängern +15min", command=lambda: self.extend(15))
        extend15_btn.pack(side=tk.LEFT, padx=(6,0))

        # Reservation id label
        self.res_label = ttk.Label(frm, text="Letzte Reservierung: -")
        self.res_label.pack(fill=tk.X, pady=(6,0))

        # Message log
        self.log = scrolledtext.ScrolledText(frm, height=18)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(6,0))
        self.log.configure(state=tk.DISABLED)

    def log_message(self, sender, text, reservation_id=None):
        ts = datetime.now().strftime('%H:%M:%S')
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


if __name__ == '__main__':
    start_agent_thread()
    app = FahrerGUI()
    app.mainloop()
