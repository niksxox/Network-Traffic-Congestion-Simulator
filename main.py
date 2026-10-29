"""
Network Congestion Traffic Light Simulator Using Computer Networks Concepts
=============================================================================
An interactive educational simulator demonstrating how network traffic congestion,
queuing behavior, packet drop, and recovery occur in computer networks.
"""

import os
import sys
import time
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker


# ============================================================================
# SIMULATION ENGINE
# ============================================================================

class NetworkSimulationEngine:
    """
    Simulates a network router receiving, queuing, and forwarding packets.
    Uses continuous elapsed time integration to maintain deterministic,
    physics-accurate packet flow independent of GUI render lag.
    """

    def __init__(self, arrival_rate=30.0, service_rate=50.0, max_queue=100):
        # Configurable parameters
        self.arrival_rate = float(arrival_rate)       # Packets per second (Offered Load)
        self.service_rate = float(service_rate)       # Router processing capacity (Packets/sec)
        self.max_queue = int(max_queue)               # Maximum buffer capacity (Packets)

        # State variables
        self.queue_length = 0                         # Current packets in waiting buffer
        self.total_incoming = 0                       # Cumulative arrived packets
        self.total_processed = 0                      # Cumulative serviced packets
        self.total_dropped = 0                        # Cumulative discarded packets (Tail drop)

        # Instantaneous measurement trackers
        self.recent_processed_count = 0
        self.effective_throughput = 0.0

        # Fractional accumulators for discrete packet integration
        self._incoming_accumulator = 0.0
        self._service_accumulator = 0.0

        # Timing and execution state
        self.is_running = False
        self.is_paused = False
        self.simulation_time = 0.0                    # Total active simulated seconds
        self._last_tick_timestamp = None
        self._throughput_window_start = 0.0

        # Historical time-series data for graphs
        self.history_time = []
        self.history_arrival_rate = []
        self.history_service_rate = []
        self.history_queue_length = []
        self.history_throughput = []
        self.history_dropped = []
        self.history_state = []

        # Event callback hook
        self.event_callback = None

    def set_event_callback(self, cb):
        self.event_callback = cb

    def log_event(self, message, level="INFO"):
        if self.event_callback:
            self.event_callback(self.simulation_time, message, level)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.is_paused = False
            self._last_tick_timestamp = time.perf_counter()
            self._throughput_window_start = self.simulation_time
            self.log_event("Simulation started.", "INFO")
        elif self.is_paused:
            self.resume()

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.log_event("Simulation paused.", "WARNING")

    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._last_tick_timestamp = time.perf_counter()
            self.log_event("Simulation resumed.", "INFO")

    def reset(self):
        self.is_running = False
        self.is_paused = False
        self.simulation_time = 0.0
        self._last_tick_timestamp = None

        self.queue_length = 0
        self.total_incoming = 0
        self.total_processed = 0
        self.total_dropped = 0

        self.recent_processed_count = 0
        self.effective_throughput = 0.0
        self._incoming_accumulator = 0.0
        self._service_accumulator = 0.0

        self.history_time.clear()
        self.history_arrival_rate.clear()
        self.history_service_rate.clear()
        self.history_queue_length.clear()
        self.history_throughput.clear()
        self.history_dropped.clear()
        self.history_state.clear()

        self.log_event("Simulation reset to initial state.", "INFO")

    def update_parameters(self, arrival_rate=None, service_rate=None, max_queue=None):
        """Allows dynamic adjustment of traffic parameters during runtime."""
        if arrival_rate is not None:
            old_arr = self.arrival_rate
            self.arrival_rate = max(0.0, float(arrival_rate))
            if abs(old_arr - self.arrival_rate) > 0.01:
                self.log_event(f"Incoming traffic changed: {old_arr:.0f} -> {self.arrival_rate:.0f} pkts/s", "INFO")

        if service_rate is not None:
            old_srv = self.service_rate
            self.service_rate = max(0.0, float(service_rate))
            if abs(old_srv - self.service_rate) > 0.01:
                self.log_event(f"Router capacity changed: {old_srv:.0f} -> {self.service_rate:.0f} pkts/s", "INFO")

        if max_queue is not None:
            self.max_queue = max(1, int(max_queue))
            # If queue size was reduced below current occupancy, excess packets drop
            if self.queue_length > self.max_queue:
                overflow = self.queue_length - self.max_queue
                self.queue_length = self.max_queue
                self.total_dropped += overflow
                self.log_event(f"Buffer resized: {overflow} queued packets dropped due to smaller queue limit.", "ALERT")

    @property
    def offered_load(self):
        """Offered Load Ratio: Incoming Rate / Router Processing Capacity"""
        if self.service_rate <= 0:
            return float('inf') if self.arrival_rate > 0 else 0.0
        return self.arrival_rate / self.service_rate

    @property
    def network_utilization_percent(self):
        """Offered load in percentage."""
        return self.offered_load * 100.0

    @property
    def queue_occupancy_ratio(self):
        if self.max_queue <= 0:
            return 1.0
        return self.queue_length / self.max_queue

    @property
    def packet_loss_rate_percent(self):
        if self.total_incoming == 0:
            return 0.0
        return (self.total_dropped / self.total_incoming) * 100.0

    def get_congestion_state(self):
        """
        Determines the network congestion level based on:
        1. Offered Load ratio (Incoming / Capacity)
        2. Buffer occupancy ratio (Queue / MaxQueue)

        Rules:
        - RED: Offered Load >= 1.00 OR Queue Occupancy >= 0.85 (Overloaded / Full Congestion)
        - YELLOW: (0.70 <= Offered Load < 1.00) OR (0.50 <= Queue Occupancy < 0.85) (Moderate Congestion)
        - GREEN: Offered Load < 0.70 AND Queue Occupancy < 0.50 (Low Congestion / Smooth Flow)
        """
        load = self.offered_load
        q_ratio = self.queue_occupancy_ratio

        if load >= 1.00 or q_ratio >= 0.85:
            return "RED", "High Congestion (Network Overloaded)"
        elif load >= 0.70 or q_ratio >= 0.50:
            return "YELLOW", "Moderate Congestion (Traffic Approaching Capacity)"
        else:
            return "GREEN", "Low Congestion (Traffic Flowing Smoothly)"

    def tick(self):
        """
        Executes one discrete simulation step using actual wall-clock dt.
        Returns the updated state dictionary.
        """
        if not self.is_running or self.is_paused:
            return None

        now = time.perf_counter()
        if self._last_tick_timestamp is None:
            self._last_tick_timestamp = now
            return None

        dt = now - self._last_tick_timestamp
        self._last_tick_timestamp = now

        # Clamp dt to avoid huge jumps if OS freezes or window is moved
        if dt > 0.5:
            dt = 0.5
        if dt <= 0:
            return None

        self.simulation_time += dt

        # ----------------------------------------------------
        # 1. Packet Arrivals (Offered Traffic)
        # ----------------------------------------------------
        self._incoming_accumulator += self.arrival_rate * dt
        arrived_packets = int(self._incoming_accumulator)
        self._incoming_accumulator -= arrived_packets

        newly_dropped = 0
        if arrived_packets > 0:
            self.total_incoming += arrived_packets
            available_space = self.max_queue - self.queue_length

            if arrived_packets <= available_space:
                self.queue_length += arrived_packets
            else:
                admitted = max(0, available_space)
                newly_dropped = arrived_packets - admitted
                self.queue_length = self.max_queue
                self.total_dropped += newly_dropped
                self.log_event(
                    f"Buffer Overflow! Discarded {newly_dropped} packet(s) (Queue Full: {self.max_queue}/{self.max_queue}).",
                    "ALERT"
                )

        # ----------------------------------------------------
        # 2. Packet Servicing (Router Processing)
        # ----------------------------------------------------
        self._service_accumulator += self.service_rate * dt
        capacity_packets = int(self._service_accumulator)
        self._service_accumulator -= capacity_packets

        serviced_packets = 0
        if capacity_packets > 0 and self.queue_length > 0:
            serviced_packets = min(self.queue_length, capacity_packets)
            self.queue_length -= serviced_packets
            self.total_processed += serviced_packets
            self.recent_processed_count += serviced_packets

        # ----------------------------------------------------
        # 3. Throughput Calculation (Sliding window)
        # ----------------------------------------------------
        elapsed_throughput_window = self.simulation_time - self._throughput_window_start
        if elapsed_throughput_window >= 0.5:
            self.effective_throughput = self.recent_processed_count / elapsed_throughput_window
            self.recent_processed_count = 0
            self._throughput_window_start = self.simulation_time

        # ----------------------------------------------------
        # 4. History Logging for Live Charts
        # ----------------------------------------------------
        state_color, state_desc = self.get_congestion_state()

        # Record at most 10 points per second
        if not self.history_time or (self.simulation_time - self.history_time[-1] >= 0.1):
            self.history_time.append(self.simulation_time)
            self.history_arrival_rate.append(self.arrival_rate)
            self.history_service_rate.append(self.service_rate)
            self.history_queue_length.append(self.queue_length)
            self.history_throughput.append(self.effective_throughput)
            self.history_dropped.append(self.total_dropped)
            self.history_state.append(state_color)

            # Keep sliding history window to maintain smooth performance
            MAX_POINTS = 600  # 60 seconds of history at 10 Hz
            if len(self.history_time) > MAX_POINTS:
                self.history_time.pop(0)
                self.history_arrival_rate.pop(0)
                self.history_service_rate.pop(0)
                self.history_queue_length.pop(0)
                self.history_throughput.pop(0)
                self.history_dropped.pop(0)
                self.history_state.pop(0)

        return {
            "time": self.simulation_time,
            "arrival_rate": self.arrival_rate,
            "service_rate": self.service_rate,
            "max_queue": self.max_queue,
            "queue_length": self.queue_length,
            "total_incoming": self.total_incoming,
            "total_processed": self.total_processed,
            "total_dropped": self.total_dropped,
            "effective_throughput": self.effective_throughput,
            "offered_load": self.offered_load,
            "utilization": self.network_utilization_percent,
            "loss_rate": self.packet_loss_rate_percent,
            "state_color": state_color,
            "state_desc": state_desc
        }


# ============================================================================
# TRAFFIC LIGHT CANVAS WIDGET
# ============================================================================

class TrafficLightWidget(tk.Canvas):
    """
    Renders an authentic, high-visibility 3-aspect traffic light.
    Features dark housing, curved lens hoods, and bright glowing active lamps.
    """

    COLOR_PALETTE = {
        "RED": {
            "on": "#FF2B2B",
            "glow": "#FF8585",
            "off": "#381010",
            "rim": "#5A1A1A"
        },
        "YELLOW": {
            "on": "#FFC400",
            "glow": "#FFE277",
            "off": "#382D06",
            "rim": "#5C4A0A"
        },
        "GREEN": {
            "on": "#00E676",
            "glow": "#80FFBA",
            "off": "#0A2E19",
            "rim": "#134B2A"
        }
    }

    def __init__(self, parent, width=120, height=270, bg="#181825", **kwargs):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.current_state = "GREEN"
        self.draw_traffic_light()

    def set_state(self, state):
        if state in ("RED", "YELLOW", "GREEN") and state != self.current_state:
            self.current_state = state
            self.draw_traffic_light()

    def draw_traffic_light(self):
        self.delete("all")
        w, h = self.width, self.height

        # Casing dimensions
        box_x1 = 15
        box_y1 = 12
        box_x2 = w - 15
        box_y2 = h - 12
        corner_r = 16

        # Draw outer housing with rounded corners
        self.create_rounded_rect(box_x1, box_y1, box_x2, box_y2, corner_r, fill="#11111B", outline="#313244", width=3)
        self.create_rounded_rect(box_x1 + 4, box_y1 + 4, box_x2 - 4, box_y2 - 4, corner_r - 2, fill="#181825", outline="#1E1E2E", width=1)

        # Signal lamp centers
        center_x = w // 2
        spacing = (box_y2 - box_y1) / 3
        r = 28  # lamp radius

        lamps = [
            ("RED", box_y1 + spacing * 0.5),
            ("YELLOW", box_y1 + spacing * 1.5),
            ("GREEN", box_y1 + spacing * 2.5)
        ]

        for color_name, cy in lamps:
            is_active = (self.current_state == color_name)
            pal = self.COLOR_PALETTE[color_name]

            # Hood visor arc above each light
            self.create_arc(
                center_x - r - 4, cy - r - 6,
                center_x + r + 4, cy + r + 2,
                start=20, extent=140,
                style=tk.ARC, outline="#45475A", width=3
            )

            # Outer rim bezel
            self.create_oval(
                center_x - r - 2, cy - r - 2,
                center_x + r + 2, cy + r + 2,
                fill=pal["rim"], outline="#11111B", width=1
            )

            if is_active:
                # Radial glow simulation
                self.create_oval(
                    center_x - r - 6, cy - r - 6,
                    center_x + r + 6, cy + r + 6,
                    outline=pal["glow"], width=2
                )
                # Active lamp
                self.create_oval(
                    center_x - r, cy - r,
                    center_x + r, cy + r,
                    fill=pal["on"], outline="#FFFFFF", width=2
                )
                # Glass reflection highlight
                self.create_oval(
                    center_x - r * 0.45, cy - r * 0.65,
                    center_x + r * 0.25, cy - r * 0.15,
                    fill="#FFFFFF", outline=""
                )
            else:
                # Inactive lamp
                self.create_oval(
                    center_x - r, cy - r,
                    center_x + r, cy + r,
                    fill=pal["off"], outline="#222230", width=1.5
                )

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)


# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class NetworkCongestionApp:
    """
    Main Application Window: Coordinates GUI controls, live telemetry,
    real-time Matplotlib charts, and student-friendly demonstrations.
    """

    THEME = {
        "bg_main": "#11111B",          # Deep slate background
        "bg_card": "#181825",          # Surface cards
        "bg_card_border": "#313244",   # Border highlight
        "text_primary": "#CDD6F4",     # Primary high contrast text
        "text_secondary": "#A6ADC8",   # Muted descriptions
        "accent_cyan": "#89DCEB",      # Offered traffic / rates
        "accent_purple": "#CBA6F7",    # Queue indicator
        "accent_green": "#A6E3A1",     # Normal / low load
        "accent_yellow": "#F9E2AF",    # Warning / moderate load
        "accent_red": "#F38BA8",       # Alert / heavy load
        "font_family": "Segoe UI"
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Network Congestion Traffic Light Simulator")
        self.root.geometry("1340x860")
        self.root.minsize(1150, 750)
        self.root.configure(bg=self.THEME["bg_main"])

        # Simulation core
        self.engine = NetworkSimulationEngine(arrival_rate=30, service_rate=50, max_queue=100)
        self.engine.set_event_callback(self.on_simulation_event)

        # Style configuration
        self.setup_styles()

        # Build UI layout
        self.build_header()
        self.build_main_layout()
        self.build_status_bar()

        # Initialize live charts
        self.init_charts()

        # Animation loop configuration
        self.timer_delay_ms = 100
        self.is_animating = True
        self.root.after(self.timer_delay_ms, self.simulation_loop)

        # Log initial greeting
        self.engine.log_event("Simulator ready. Click 'Start Simulation' or pick a Preset Scenario.", "SUCCESS")

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=self.THEME["bg_main"])
        style.configure("Card.TFrame", background=self.THEME["bg_card"], relief="flat")
        style.configure("TLabel", background=self.THEME["bg_card"], foreground=self.THEME["text_primary"])
        style.configure("Horizontal.TScale", background=self.THEME["bg_card"])

    # ------------------------------------------------------------------------
    # HEADER SECTION
    # ------------------------------------------------------------------------
    def build_header(self):
        header_frame = tk.Frame(self.root, bg="#181825", bd=0, highlightbackground="#313244", highlightthickness=1)
        header_frame.pack(fill=tk.X, padx=16, pady=(12, 8))

        top_row = tk.Frame(header_frame, bg="#181825")
        top_row.pack(fill=tk.X, padx=16, pady=10)

        # Icon / Badge & Title
        title_box = tk.Frame(top_row, bg="#181825")
        title_box.pack(side=tk.LEFT)

        title_lbl = tk.Label(
            title_box,
            text="🚦 Network Congestion Traffic Light Simulator",
            font=(self.THEME["font_family"], 17, "bold"),
            bg="#181825",
            fg=self.THEME["text_primary"]
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            title_box,
            text="Visualize how increasing network traffic affects congestion, packet queues, throughput, and packet loss.",
            font=(self.THEME["font_family"], 9, "italic"),
            bg="#181825",
            fg=self.THEME["text_secondary"]
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Action buttons on header right
        btn_box = tk.Frame(top_row, bg="#181825")
        btn_box.pack(side=tk.RIGHT)

        export_btn = tk.Button(
            btn_box,
            text="💾 Export CSV Report",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#313244",
            fg="#CDD6F4",
            activebackground="#45475A",
            activeforeground="#FFFFFF",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.export_csv_report
        )
        export_btn.pack(side=tk.LEFT, padx=6)

        help_btn = tk.Button(
            btn_box,
            text="📖 Help & Viva Guide",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#45475A",
            fg="#CDD6F4",
            activebackground="#585B70",
            activeforeground="#FFFFFF",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=self.open_help_dialog
        )
        help_btn.pack(side=tk.LEFT)

    # ------------------------------------------------------------------------
    # MAIN SPLIT LAYOUT (LEFT: CONTROLS & LIGHT, RIGHT: DASHBOARD & GRAPHS)
    # ------------------------------------------------------------------------
    def build_main_layout(self):
        container = tk.Frame(self.root, bg=self.THEME["bg_main"])
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Left Column (Light + Controls + Presets + Event Log)
        left_col = tk.Frame(container, bg=self.THEME["bg_main"], width=460)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_col.pack_propagate(False)

        # Right Column (Metrics Dashboard + Live Matplotlib Charts)
        right_col = tk.Frame(container, bg=self.THEME["bg_main"])
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.build_left_panel(left_col)
        self.build_right_panel(right_col)

    # ------------------------------------------------------------------------
    # LEFT PANEL: TRAFFIC LIGHT, CONTROLS, PRESETS, LOGS
    # ------------------------------------------------------------------------
    def build_left_panel(self, parent):
        canvas_scroll = tk.Canvas(parent, bg=self.THEME["bg_main"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas_scroll.yview)
        scrollable_frame = tk.Frame(canvas_scroll, bg=self.THEME["bg_main"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        )

        canvas_scroll.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)

        canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 1. Traffic Light and Status Card
        self.build_traffic_light_card(scrollable_frame)

        # 2. Traffic Flow Controls (Sliders)
        self.build_controls_card(scrollable_frame)

        # 3. Demonstration Presets & Rapid Testing
        self.build_presets_card(scrollable_frame)

        # 4. Event Log
        self.build_event_log_card(scrollable_frame)

    def build_traffic_light_card(self, parent):
        card = tk.Frame(parent, bg=self.THEME["bg_card"], bd=0, highlightbackground=self.THEME["bg_card_border"], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        card_title = tk.Label(
            card,
            text="TRAFFIC LIGHT CONGESTION INDICATOR",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["accent_cyan"]
        )
        card_title.pack(anchor="w", padx=14, pady=(10, 4))

        content_box = tk.Frame(card, bg=self.THEME["bg_card"])
        content_box.pack(fill=tk.X, padx=12, pady=6)

        # Authentic Traffic Light Signal Canvas
        self.traffic_light = TrafficLightWidget(content_box, width=105, height=225, bg=self.THEME["bg_card"])
        self.traffic_light.pack(side=tk.LEFT, padx=(4, 12))

        # Status & Educational Explanation
        info_col = tk.Frame(content_box, bg=self.THEME["bg_card"])
        info_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.light_status_badge = tk.Label(
            info_col,
            text="● GREEN — Low Congestion",
            font=(self.THEME["font_family"], 11, "bold"),
            bg="#1E3A2F",
            fg=self.THEME["accent_green"],
            padx=8,
            pady=4,
            relief="flat"
        )
        self.light_status_badge.pack(fill=tk.X, pady=(4, 6))

        self.explanation_text = tk.Label(
            info_col,
            text="Traffic flows smoothly. Offered load is below router capacity. Packets are serviced without sustained queuing.",
            font=(self.THEME["font_family"], 9),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_secondary"],
            wraplength=270,
            justify=tk.LEFT
        )
        self.explanation_text.pack(anchor="w", pady=(0, 6))

        # Decision Rule Hint
        rule_box = tk.Frame(info_col, bg="#1E1E2E", padx=8, pady=6)
        rule_box.pack(fill=tk.X, pady=(2, 4))

        rule_title = tk.Label(
            rule_box,
            text="DECISION RULE THRESHOLDS:",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#1E1E2E",
            fg="#BAC2DE"
        )
        rule_title.pack(anchor="w")

        rule_desc = tk.Label(
            rule_box,
            text="• GREEN: Load < 70% and Queue < 50%\n• YELLOW: Load 70-99% or Queue 50-84%\n• RED: Load ≥ 100% or Queue ≥ 85%",
            font=(self.THEME["font_family"], 8),
            bg="#1E1E2E",
            fg="#A6ADC8",
            justify=tk.LEFT
        )
        rule_desc.pack(anchor="w")

    def build_controls_card(self, parent):
        card = tk.Frame(parent, bg=self.THEME["bg_card"], bd=0, highlightbackground=self.THEME["bg_card_border"], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        title = tk.Label(
            card,
            text="NETWORK TRAFFIC CONTROLS",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["accent_cyan"]
        )
        title.pack(anchor="w", padx=14, pady=(10, 4))

        # Sliders container
        sliders_box = tk.Frame(card, bg=self.THEME["bg_card"])
        sliders_box.pack(fill=tk.X, padx=14, pady=6)

        # 1. Incoming Traffic Rate Slider
        self.arrival_val_lbl = tk.Label(
            sliders_box,
            text="Incoming Traffic Rate: 30 packets/s",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"]
        )
        self.arrival_val_lbl.pack(anchor="w")

        self.arrival_scale = tk.Scale(
            sliders_box,
            from_=0,
            to=150,
            orient=tk.HORIZONTAL,
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"],
            troughcolor="#313244",
            activebackground=self.THEME["accent_cyan"],
            highlightthickness=0,
            showvalue=False,
            command=self.on_arrival_scale_change
        )
        self.arrival_scale.set(30)
        self.arrival_scale.pack(fill=tk.X, pady=(2, 8))

        # 2. Router Processing Capacity Slider
        self.service_val_lbl = tk.Label(
            sliders_box,
            text="Router Processing Capacity: 50 packets/s",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"]
        )
        self.service_val_lbl.pack(anchor="w")

        self.service_scale = tk.Scale(
            sliders_box,
            from_=5,
            to=120,
            orient=tk.HORIZONTAL,
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"],
            troughcolor="#313244",
            activebackground=self.THEME["accent_cyan"],
            highlightthickness=0,
            showvalue=False,
            command=self.on_service_scale_change
        )
        self.service_scale.set(50)
        self.service_scale.pack(fill=tk.X, pady=(2, 8))

        # 3. Maximum Queue Capacity Slider
        self.queue_val_lbl = tk.Label(
            sliders_box,
            text="Maximum Queue Capacity: 100 packets",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"]
        )
        self.queue_val_lbl.pack(anchor="w")

        self.queue_scale = tk.Scale(
            sliders_box,
            from_=10,
            to=200,
            orient=tk.HORIZONTAL,
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_primary"],
            troughcolor="#313244",
            activebackground=self.THEME["accent_cyan"],
            highlightthickness=0,
            showvalue=False,
            command=self.on_queue_scale_change
        )
        self.queue_scale.set(100)
        self.queue_scale.pack(fill=tk.X, pady=(2, 12))

        # Playback Control Buttons (Start / Pause / Resume / Reset)
        btn_grid = tk.Frame(card, bg=self.THEME["bg_card"])
        btn_grid.pack(fill=tk.X, padx=14, pady=(0, 12))

        self.btn_start = tk.Button(
            btn_grid,
            text="▶ Start",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#2E7D32",
            fg="#FFFFFF",
            activebackground="#388E3C",
            activeforeground="#FFFFFF",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self.on_click_start
        )
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.btn_pause = tk.Button(
            btn_grid,
            text="⏸ Pause",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#F57F17",
            fg="#FFFFFF",
            activebackground="#FBC02D",
            activeforeground="#FFFFFF",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self.on_click_pause
        )
        self.btn_pause.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        self.btn_resume = tk.Button(
            btn_grid,
            text="⏯ Resume",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#0288D1",
            fg="#FFFFFF",
            activebackground="#039BE5",
            activeforeground="#FFFFFF",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self.on_click_resume
        )
        self.btn_resume.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        self.btn_reset = tk.Button(
            btn_grid,
            text="🔄 Reset",
            font=(self.THEME["font_family"], 9, "bold"),
            bg="#D32F2F",
            fg="#FFFFFF",
            activebackground="#E53935",
            activeforeground="#FFFFFF",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self.on_click_reset
        )
        self.btn_reset.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        # Congestion Injection / Quick Recovery actions
        quick_grid = tk.Frame(card, bg=self.THEME["bg_card"])
        quick_grid.pack(fill=tk.X, padx=14, pady=(0, 12))

        self.btn_heavy_traffic = tk.Button(
            quick_grid,
            text="⚡ Generate Heavy Traffic (80 pkts/s)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#6C1E2D",
            fg="#FFD1DC",
            activebackground="#842637",
            activeforeground="#FFFFFF",
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.on_click_generate_heavy
        )
        self.btn_heavy_traffic.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.btn_reduce_traffic = tk.Button(
            quick_grid,
            text="💧 Reduce Traffic (20 pkts/s)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#184D35",
            fg="#B9F6CA",
            activebackground="#206143",
            activeforeground="#FFFFFF",
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.on_click_reduce_traffic
        )
        self.btn_reduce_traffic.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

    def build_presets_card(self, parent):
        card = tk.Frame(parent, bg=self.THEME["bg_card"], bd=0, highlightbackground=self.THEME["bg_card_border"], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        title = tk.Label(
            card,
            text="PRESET DEMONSTRATION SCENARIOS",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["accent_cyan"]
        )
        title.pack(anchor="w", padx=14, pady=(10, 4))

        desc = tk.Label(
            card,
            text="Select reproducible test situations for classroom demonstration:",
            font=(self.THEME["font_family"], 8, "italic"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_secondary"]
        )
        desc.pack(anchor="w", padx=14, pady=(0, 8))

        scenarios_box = tk.Frame(card, bg=self.THEME["bg_card"])
        scenarios_box.pack(fill=tk.X, padx=14, pady=(0, 12))

        btn_s1 = tk.Button(
            scenarios_box,
            text="🟢 Scenario 1: Normal Traffic (20 in / 50 cap)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#213B31",
            fg="#A6E3A1",
            activebackground="#2D4F42",
            bd=0,
            pady=5,
            anchor="w",
            padx=10,
            cursor="hand2",
            command=lambda: self.apply_preset(20, 50, 100, "Scenario 1: Normal Traffic loaded.")
        )
        btn_s1.pack(fill=tk.X, pady=2)

        btn_s2 = tk.Button(
            scenarios_box,
            text="🟡 Scenario 2: Increasing Traffic (40 in / 50 cap)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#45381D",
            fg="#F9E2AF",
            activebackground="#5A4A28",
            bd=0,
            pady=5,
            anchor="w",
            padx=10,
            cursor="hand2",
            command=lambda: self.apply_preset(40, 50, 100, "Scenario 2: Increasing Traffic loaded.")
        )
        btn_s2.pack(fill=tk.X, pady=2)

        btn_s3 = tk.Button(
            scenarios_box,
            text="🔴 Scenario 3: Heavy Traffic (80 in / 50 cap)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#4A1E29",
            fg="#F38BA8",
            activebackground="#5E2734",
            bd=0,
            pady=5,
            anchor="w",
            padx=10,
            cursor="hand2",
            command=lambda: self.apply_preset(80, 50, 100, "Scenario 3: Heavy Congestion loaded.")
        )
        btn_s3.pack(fill=tk.X, pady=2)

    def build_event_log_card(self, parent):
        card = tk.Frame(parent, bg=self.THEME["bg_card"], bd=0, highlightbackground=self.THEME["bg_card_border"], highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        head_box = tk.Frame(card, bg=self.THEME["bg_card"])
        head_box.pack(fill=tk.X, padx=14, pady=(10, 4))

        title = tk.Label(
            head_box,
            text="SIMULATION EVENT LOG",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["accent_cyan"]
        )
        title.pack(side=tk.LEFT)

        clear_btn = tk.Button(
            head_box,
            text="Clear Log",
            font=(self.THEME["font_family"], 7),
            bg="#313244",
            fg="#BAC2DE",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.clear_event_log
        )
        clear_btn.pack(side=tk.RIGHT)

        log_container = tk.Frame(card, bg="#11111B", padx=6, pady=6)
        log_container.pack(fill=tk.BOTH, padx=14, pady=(0, 12))

        self.log_text = tk.Text(
            log_container,
            height=7,
            bg="#11111B",
            fg="#CDD6F4",
            bd=0,
            font=("Consolas", 8),
            wrap=tk.WORD
        )
        log_scroll = ttk.Scrollbar(log_container, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Style tags
        self.log_text.tag_config("INFO", foreground="#89DCEB")
        self.log_text.tag_config("WARNING", foreground="#F9E2AF")
        self.log_text.tag_config("ALERT", foreground="#F38BA8")
        self.log_text.tag_config("SUCCESS", foreground="#A6E3A1")

    # ------------------------------------------------------------------------
    # RIGHT PANEL: METRICS DASHBOARD & LIVE CHARTS
    # ------------------------------------------------------------------------
    def build_right_panel(self, parent):
        # 1. Dashboard Metrics Grid (8 Cards)
        self.build_metrics_dashboard(parent)

        # 2. Live Graphs (Traffic Rates & Queue Length)
        self.build_graphs_container(parent)

    def build_metrics_dashboard(self, parent):
        dash_frame = tk.Frame(parent, bg=self.THEME["bg_main"])
        dash_frame.pack(fill=tk.X, pady=(0, 8))

        # 8 Metric Cards arranged in 2 rows of 4
        self.metric_widgets = {}

        metrics_meta = [
            # Row 1
            ("incoming", "Incoming Packets", "0", "Total Arrived", self.THEME["accent_cyan"]),
            ("processed", "Processed Packets", "0", "Forwarded Out", self.THEME["accent_green"]),
            ("dropped", "Dropped Packets", "0", "Tail Drops", self.THEME["accent_red"]),
            ("queue", "Current Queue Length", "0 / 100", "Buffer In-flight", self.THEME["accent_purple"]),
            # Row 2
            ("utilization", "Network Utilization", "0.0 %", "Offered Load", self.THEME["accent_cyan"]),
            ("throughput", "Effective Throughput", "0.0 pkts/s", "Realized Rate", self.THEME["accent_green"]),
            ("loss_rate", "Packet Loss Rate", "0.0 %", "Cumulative Loss", self.THEME["accent_red"]),
            ("sim_time", "Simulation Time", "00:00.0", "Active Duration", "#BAC2DE")
        ]

        for i, (key, title, init_val, subtext, color) in enumerate(metrics_meta):
            row = i // 4
            col = i % 4

            card = tk.Frame(
                dash_frame,
                bg=self.THEME["bg_card"],
                bd=0,
                highlightbackground=self.THEME["bg_card_border"],
                highlightthickness=1
            )
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            dash_frame.columnconfigure(col, weight=1)

            t_lbl = tk.Label(
                card,
                text=title,
                font=(self.THEME["font_family"], 8, "bold"),
                bg=self.THEME["bg_card"],
                fg=self.THEME["text_secondary"]
            )
            t_lbl.pack(anchor="w", padx=10, pady=(6, 1))

            v_lbl = tk.Label(
                card,
                text=init_val,
                font=(self.THEME["font_family"], 14, "bold"),
                bg=self.THEME["bg_card"],
                fg=color
            )
            v_lbl.pack(anchor="w", padx=10, pady=(0, 1))

            s_lbl = tk.Label(
                card,
                text=subtext,
                font=(self.THEME["font_family"], 7),
                bg=self.THEME["bg_card"],
                fg="#6C7086"
            )
            s_lbl.pack(anchor="w", padx=10, pady=(0, 6))

            self.metric_widgets[key] = {
                "val": v_lbl,
                "sub": s_lbl,
                "card": card
            }

    def build_graphs_container(self, parent):
        chart_card = tk.Frame(
            parent,
            bg=self.THEME["bg_card"],
            bd=0,
            highlightbackground=self.THEME["bg_card_border"],
            highlightthickness=1
        )
        chart_card.pack(fill=tk.BOTH, expand=True)

        chart_head = tk.Frame(chart_card, bg=self.THEME["bg_card"])
        chart_head.pack(fill=tk.X, padx=12, pady=(8, 4))

        chart_title = tk.Label(
            chart_head,
            text="LIVE NETWORK TELEMETRY (RATES & QUEUE EVOLUTION)",
            font=(self.THEME["font_family"], 9, "bold"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["accent_cyan"]
        )
        chart_title.pack(side=tk.LEFT)

        chart_sub = tk.Label(
            chart_head,
            text="Real-time offered load vs router capacity and buffer occupancy",
            font=(self.THEME["font_family"], 8, "italic"),
            bg=self.THEME["bg_card"],
            fg=self.THEME["text_secondary"]
        )
        chart_sub.pack(side=tk.RIGHT)

        # Matplotlib embedded canvas
        self.fig = Figure(figsize=(8, 5.2), dpi=100, facecolor="#181825")
        self.fig.subplots_adjust(left=0.08, right=0.96, top=0.92, bottom=0.10, hspace=0.35)

        # Subplot 1: Rates (Arrival vs Capacity)
        self.ax_rates = self.fig.add_subplot(2, 1, 1, facecolor="#11111B")
        # Subplot 2: Queue Length
        self.ax_queue = self.fig.add_subplot(2, 1, 2, facecolor="#11111B")

        self.canvas_chart = FigureCanvasTkAgg(self.fig, master=chart_card)
        self.canvas_widget = self.canvas_chart.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def init_charts(self):
        # Configure Rates Axis
        self.ax_rates.set_title("Network Traffic Over Time (Packets / Second)", fontsize=9, color="#CDD6F4", weight="bold", pad=6)
        self.ax_rates.set_ylabel("Packet Rate (pkts/s)", fontsize=8, color="#A6ADC8")
        self.ax_rates.tick_params(colors="#A6ADC8", labelsize=8)
        self.ax_rates.grid(True, linestyle="--", alpha=0.2, color="#6C7086")
        for spine in self.ax_rates.spines.values():
            spine.set_color("#313244")

        # Configure Queue Axis
        self.ax_queue.set_title("Router Queue Length Over Time (Packets)", fontsize=9, color="#CDD6F4", weight="bold", pad=6)
        self.ax_queue.set_xlabel("Simulation Time (seconds)", fontsize=8, color="#A6ADC8")
        self.ax_queue.set_ylabel("Queue Length", fontsize=8, color="#A6ADC8")
        self.ax_queue.tick_params(colors="#A6ADC8", labelsize=8)
        self.ax_queue.grid(True, linestyle="--", alpha=0.2, color="#6C7086")
        for spine in self.ax_queue.spines.values():
            spine.set_color("#313244")

        # Initial plot lines
        self.line_arrival, = self.ax_rates.plot([], [], label="Incoming Rate", color="#89DCEB", linewidth=2.0)
        self.line_capacity, = self.ax_rates.plot([], [], label="Router Capacity", color="#F38BA8", linewidth=1.8, linestyle="--")
        self.line_throughput, = self.ax_rates.plot([], [], label="Throughput", color="#A6E3A1", linewidth=1.5, alpha=0.8)
        self.ax_rates.legend(loc="upper right", facecolor="#181825", edgecolor="#313244", fontsize=7, labelcolor="#CDD6F4")

        self.line_queue, = self.ax_queue.plot([], [], label="Queue Occupancy", color="#CBA6F7", linewidth=2.0)
        self.line_max_queue = self.ax_queue.axhline(100, color="#F38BA8", linestyle=":", linewidth=1.5, label="Max Queue Limit")
        self.ax_queue.legend(loc="upper right", facecolor="#181825", edgecolor="#313244", fontsize=7, labelcolor="#CDD6F4")

        self.canvas_chart.draw()

    # ------------------------------------------------------------------------
    # STATUS BAR
    # ------------------------------------------------------------------------
    def build_status_bar(self):
        status_bar = tk.Frame(self.root, bg="#11111B", height=24)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(0, 6))

        self.status_state_lbl = tk.Label(
            status_bar,
            text="STATUS: Idle (Press Start)",
            font=(self.THEME["font_family"], 8, "bold"),
            bg="#11111B",
            fg="#89DCEB"
        )
        self.status_state_lbl.pack(side=tk.LEFT)

        author_lbl = tk.Label(
            status_bar,
            text="Computer Networks Laboratory Project • Visualizing Congestion, Queuing & Recovery",
            font=(self.THEME["font_family"], 8),
            bg="#11111B",
            fg="#6C7086"
        )
        author_lbl.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------------
    # CONTROL EVENT HANDLERS
    # ------------------------------------------------------------------------
    def on_arrival_scale_change(self, val):
        val_f = float(val)
        self.arrival_val_lbl.config(text=f"Incoming Traffic Rate: {val_f:.0f} packets/s")
        self.engine.update_parameters(arrival_rate=val_f)

    def on_service_scale_change(self, val):
        val_f = float(val)
        self.service_val_lbl.config(text=f"Router Processing Capacity: {val_f:.0f} packets/s")
        self.engine.update_parameters(service_rate=val_f)

    def on_queue_scale_change(self, val):
        val_i = int(val)
        self.queue_val_lbl.config(text=f"Maximum Queue Capacity: {val_i} packets")
        self.engine.update_parameters(max_queue=val_i)
        self.line_max_queue.set_ydata([val_i, val_i])

    def on_click_start(self):
        self.engine.start()
        self.status_state_lbl.config(text="STATUS: Running", fg=self.THEME["accent_green"])

    def on_click_pause(self):
        self.engine.pause()
        self.status_state_lbl.config(text="STATUS: Paused", fg=self.THEME["accent_yellow"])

    def on_click_resume(self):
        self.engine.resume()
        self.status_state_lbl.config(text="STATUS: Running", fg=self.THEME["accent_green"])

    def on_click_reset(self):
        self.engine.reset()
        self.status_state_lbl.config(text="STATUS: Idle (Reset)", fg="#89DCEB")
        self.update_ui_state({
            "time": 0.0,
            "arrival_rate": self.engine.arrival_rate,
            "service_rate": self.engine.service_rate,
            "max_queue": self.engine.max_queue,
            "queue_length": 0,
            "total_incoming": 0,
            "total_processed": 0,
            "total_dropped": 0,
            "effective_throughput": 0.0,
            "offered_load": self.engine.offered_load,
            "utilization": self.engine.network_utilization_percent,
            "loss_rate": 0.0,
            "state_color": "GREEN",
            "state_desc": "Low Congestion (Traffic Flowing Smoothly)"
        })
        self.update_charts_reset()

    def on_click_generate_heavy(self):
        """Immediately bumps arrival rate to 80 to demonstrate congestion build up."""
        self.arrival_scale.set(80)
        self.on_arrival_scale_change(80)
        if not self.engine.is_running or self.engine.is_paused:
            self.engine.start()
            self.status_state_lbl.config(text="STATUS: Running (Heavy Traffic)", fg=self.THEME["accent_red"])

    def on_click_reduce_traffic(self):
        """Reduces incoming traffic to 20 to demonstrate queue draining & recovery."""
        self.arrival_scale.set(20)
        self.on_arrival_scale_change(20)

    def apply_preset(self, arrival, service, max_queue, log_msg):
        self.arrival_scale.set(arrival)
        self.service_scale.set(service)
        self.queue_scale.set(max_queue)
        self.engine.update_parameters(arrival_rate=arrival, service_rate=service, max_queue=max_queue)
        self.engine.log_event(log_msg, "INFO")
        if not self.engine.is_running:
            self.engine.start()
            self.status_state_lbl.config(text="STATUS: Running (Preset)", fg=self.THEME["accent_green"])

    # ------------------------------------------------------------------------
    # EVENT LOGGING
    # ------------------------------------------------------------------------
    def on_simulation_event(self, sim_time, message, level):
        timestamp = f"[{sim_time:05.1f}s]"
        formatted = f"{timestamp} {message}\n"
        self.log_text.insert(tk.END, formatted, level)
        self.log_text.see(tk.END)

    def clear_event_log(self):
        self.log_text.delete("1.0", tk.END)

    # ------------------------------------------------------------------------
    # SIMULATION LOOP & RENDERING
    # ------------------------------------------------------------------------
    def simulation_loop(self):
        if self.is_animating:
            state = self.engine.tick()
            if state:
                self.update_ui_state(state)
                self.update_charts()

        self.root.after(self.timer_delay_ms, self.simulation_loop)

    def update_ui_state(self, state):
        # 1. Update Traffic Light
        color = state["state_color"]
        self.traffic_light.set_state(color)

        # 2. Update Badge & Explanations
        if color == "GREEN":
            self.light_status_badge.config(
                text="● GREEN — Low Congestion",
                bg="#1E3A2F",
                fg=self.THEME["accent_green"]
            )
            self.explanation_text.config(
                text="The router can process incoming packets at the current rate. Traffic flows smoothly under a low offered load."
            )
        elif color == "YELLOW":
            self.light_status_badge.config(
                text="● YELLOW — Moderate Congestion",
                bg="#3E341C",
                fg=self.THEME["accent_yellow"]
            )
            self.explanation_text.config(
                text="Incoming traffic is approaching router capacity. Packets wait in buffer queue. Monitor for queue overflow."
            )
        else: # RED
            self.light_status_badge.config(
                text="● RED — High Congestion",
                bg="#421922",
                fg=self.THEME["accent_red"]
            )
            self.explanation_text.config(
                text="Incoming traffic equals or exceeds router capacity. Buffer queue is saturated; tail drop packet loss occurs."
            )

        # 3. Update Metrics Dashboard Cards
        m = self.metric_widgets
        m["incoming"]["val"].config(text=f"{state['total_incoming']:,}")
        m["processed"]["val"].config(text=f"{state['total_processed']:,}")

        # Dropped packets highlight
        dropped_count = state["total_dropped"]
        m["dropped"]["val"].config(
            text=f"{dropped_count:,}",
            fg=self.THEME["accent_red"] if dropped_count > 0 else "#BAC2DE"
        )

        # Current Queue
        q_len = state["queue_length"]
        m_q = state["max_queue"]
        q_pct = (q_len / m_q) * 100.0 if m_q > 0 else 0
        m["queue"]["val"].config(text=f"{q_len} / {m_q}")
        m["queue"]["sub"].config(text=f"Buffer Fullness: {q_pct:.0f}%")

        # Network Utilization
        util = state["utilization"]
        m["utilization"]["val"].config(text=f"{util:.1f} %")
        if util > 100.0:
            m["utilization"]["sub"].config(text=f"Overloaded (+{util-100:.0f}% excess)")
        else:
            m["utilization"]["sub"].config(text="Offered Load Ratio")

        # Effective Throughput
        tp = state["effective_throughput"]
        m["throughput"]["val"].config(text=f"{tp:.1f} pkts/s")

        # Packet Loss Rate
        loss = state["loss_rate"]
        m["loss_rate"]["val"].config(
            text=f"{loss:.1f} %",
            fg=self.THEME["accent_red"] if loss > 0 else self.THEME["accent_green"]
        )

        # Simulation Time
        sec = state["time"]
        mins = int(sec // 60)
        remaining_sec = sec % 60
        m["sim_time"]["val"].config(text=f"{mins:02d}:{remaining_sec:04.1f}")

    def update_charts(self):
        times = self.engine.history_time
        if not times or len(times) < 2:
            return

        t_min = max(0.0, times[-1] - 45.0)
        t_max = max(times[-1], 10.0)

        # Update Rates Subplot
        self.line_arrival.set_data(times, self.engine.history_arrival_rate)
        self.line_capacity.set_data(times, self.engine.history_service_rate)
        self.line_throughput.set_data(times, self.engine.history_throughput)

        self.ax_rates.set_xlim(t_min, t_max)
        max_rate = max(
            max(self.engine.history_arrival_rate),
            max(self.engine.history_service_rate),
            60.0
        )
        self.ax_rates.set_ylim(0, max_rate * 1.15)

        # Update Queue Subplot
        self.line_queue.set_data(times, self.engine.history_queue_length)
        self.line_max_queue.set_ydata([self.engine.max_queue, self.engine.max_queue])

        self.ax_queue.set_xlim(t_min, t_max)
        max_q_val = max(self.engine.max_queue, max(self.engine.history_queue_length) if self.engine.history_queue_length else 10)
        self.ax_queue.set_ylim(0, max_q_val * 1.18)

        self.canvas_chart.draw_idle()

    def update_charts_reset(self):
        self.line_arrival.set_data([], [])
        self.line_capacity.set_data([], [])
        self.line_throughput.set_data([], [])
        self.line_queue.set_data([], [])

        self.ax_rates.set_xlim(0, 10)
        self.ax_rates.set_ylim(0, 100)
        self.ax_queue.set_xlim(0, 10)
        self.ax_queue.set_ylim(0, self.engine.max_queue * 1.2)

        self.canvas_chart.draw_idle()

    # ------------------------------------------------------------------------
    # REPORT EXPORT (CSV)
    # ------------------------------------------------------------------------
    def export_csv_report(self):
        if not self.engine.history_time:
            messagebox.showinfo("Export Notice", "No simulation data available yet to export. Run the simulation first.")
            return

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"network_congestion_report_{timestamp_str}.csv"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=default_filename,
            title="Save Simulation CSV Report"
        )

        if not file_path:
            return

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Metadata Header
                writer.writerow(["=== NETWORK CONGESTION SIMULATOR REPORT ==="])
                writer.writerow(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Total Simulation Duration (s)", f"{self.engine.simulation_time:.2f}"])
                writer.writerow(["Configured Arrival Rate (pkts/s)", f"{self.engine.arrival_rate:.1f}"])
                writer.writerow(["Configured Service Capacity (pkts/s)", f"{self.engine.service_rate:.1f}"])
                writer.writerow(["Configured Max Queue Size", self.engine.max_queue])
                writer.writerow(["Total Incoming Packets", self.engine.total_incoming])
                writer.writerow(["Total Processed Packets", self.engine.total_processed])
                writer.writerow(["Total Dropped Packets", self.engine.total_dropped])
                writer.writerow(["Final Packet Loss Rate (%)", f"{self.engine.packet_loss_rate_percent:.2f}"])
                writer.writerow(["Final Queue Length", self.engine.queue_length])
                state_c, state_d = self.engine.get_congestion_state()
                writer.writerow(["Final Congestion Light", state_c])
                writer.writerow(["Final Congestion Description", state_d])
                writer.writerow([])

                # Time Series Data Header
                writer.writerow([
                    "Time (s)",
                    "Arrival Rate (pkts/s)",
                    "Router Capacity (pkts/s)",
                    "Throughput (pkts/s)",
                    "Queue Length",
                    "Cumulative Dropped",
                    "Congestion State"
                ])

                for t, arr, srv, tp, q, drp, st in zip(
                    self.engine.history_time,
                    self.engine.history_arrival_rate,
                    self.engine.history_service_rate,
                    self.engine.history_throughput,
                    self.engine.history_queue_length,
                    self.engine.history_dropped,
                    self.engine.history_state
                ):
                    writer.writerow([
                        f"{t:.2f}",
                        f"{arr:.1f}",
                        f"{srv:.1f}",
                        f"{tp:.1f}",
                        q,
                        drp,
                        st
                    ])

            self.engine.log_event(f"Report exported to: {os.path.basename(file_path)}", "SUCCESS")
            messagebox.showinfo("Export Successful", f"Simulation report saved successfully to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to save CSV file:\n{str(e)}")

    # ------------------------------------------------------------------------
    # HELP & VIVA GUIDE DIALOG
    # ------------------------------------------------------------------------
    def open_help_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Computer Networks Concept Guide & Viva Reference")
        dialog.geometry("780x620")
        dialog.configure(bg=self.THEME["bg_main"])
        dialog.transient(self.root)

        header = tk.Frame(dialog, bg="#181825", padx=16, pady=12)
        header.pack(fill=tk.X)

        h_title = tk.Label(
            header,
            text="📚 Computer Networks Educational Concepts & Viva Guide",
            font=(self.THEME["font_family"], 13, "bold"),
            bg="#181825",
            fg="#CDD6F4"
        )
        h_title.pack(anchor="w")

        h_sub = tk.Label(
            header,
            text="Essential terms, queuing theory, and explanations for presenting to professors.",
            font=(self.THEME["font_family"], 9, "italic"),
            bg="#181825",
            fg="#A6ADC8"
        )
        h_sub.pack(anchor="w")

        text_frame = tk.Frame(dialog, bg=self.THEME["bg_main"], padx=14, pady=10)
        text_frame.pack(fill=tk.BOTH, expand=True)

        help_text = tk.Text(
            text_frame,
            bg="#181825",
            fg="#CDD6F4",
            bd=0,
            font=("Consolas", 9),
            padx=12,
            pady=12,
            wrap=tk.WORD
        )
        scroll = ttk.Scrollbar(text_frame, command=help_text.yview)
        help_text.configure(yscrollcommand=scroll.set)

        help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        guide_content = """1. WHAT IS NETWORK CONGESTION?
----------------------------------------------------------------------
Network congestion occurs when the aggregate demand for transmission
(offered load) exceeds the processing or transmission capacity of a network node
(such as a router or switch).

2. KEY COMPUTER NETWORKS CONCEPTS DEMONSTRATED:
----------------------------------------------------------------------
A. Offered Load (λ):
   The rate at which packets arrive at the network node (packets per second).
   In this simulator, adjustable via "Incoming Traffic Rate".

B. Service Rate (μ):
   The maximum rate at which the router can process and transmit packets.
   In this simulator, adjustable via "Router Processing Capacity".

C. Network Utilization (ρ = λ / μ):
   The ratio of arrival rate to service capacity:
   - ρ < 0.70  : Low load, stable queue, negligible delay (GREEN).
   - 0.70 <= ρ < 1.00 : Moderate load, growing queue, higher queuing delay (YELLOW).
   - ρ >= 1.00 : Overloaded, queue grows towards infinity/capacity (RED).

D. Router Buffer / Queue:
   Routers maintain memory buffers to store packets during temporary traffic
   bursts. When arrivals exceed capacity temporarily, the buffer prevents
   immediate loss.

E. Tail Drop (Packet Discard):
   When the queue reaches Maximum Queue Capacity (100% full), newly arriving
   packets cannot be stored and are immediately dropped.

F. Effective Throughput:
   The actual rate of successfully forwarded packets. Even if offered load is
   150 packets/s, the throughput cannot exceed the router's processing capacity.

G. Congestion Recovery:
   When incoming traffic is reduced (e.g., via TCP Congestion Control or clicking
   'Reduce Traffic'), the router continues processing the queued packets until
   the buffer drains back to zero, returning the traffic light to GREEN.

3. VIVA QUESTIONS & ANSWERS FOR STUDENTS:
----------------------------------------------------------------------
Q1: Why does a router need a queue/buffer?
A1: To absorb temporary bursts in traffic. Without a buffer, any instant where
    incoming rate exceeds capacity would immediately cause packet loss.

Q2: Can we solve congestion simply by making the queue infinite?
A2: No! This causes "Bufferbloat". Packets sit in huge queues for seconds, causing
    massive latency (queuing delay) and causing transport protocols like TCP to
    time out and retransmit duplicate packets, worsening congestion.

Q3: What determines the Traffic Light color?
A3: • GREEN: Low Congestion (Offered load < 70% and Queue occupancy < 50%)
    • YELLOW: Moderate Congestion (Offered load 70-99% or Queue 50-84%)
    • RED: High Congestion (Offered load >= 100% or Queue >= 85%)

Q4: How does the network recover from congestion in the real world?
A4: Protocols like TCP detect packet loss or delay signals (ECN) and cut
    their transmission rate (e.g., AIMD - Additive Increase / Multiplicative
    Decrease), reducing offered traffic so queues drain.
"""
        help_text.insert(tk.END, guide_content)
        help_text.configure(state=tk.DISABLED)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    root = tk.Tk()
    app = NetworkCongestionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
