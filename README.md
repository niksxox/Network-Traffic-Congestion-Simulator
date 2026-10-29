# Network Congestion Traffic Light Simulator Using Computer Networks Concepts

An interactive, visual, educational simulator demonstrating how network traffic congestion develops, how router buffers behave, why packet loss occurs during overload, and how traffic reduction enables network recovery.

---

## 1. Project Title
**Network Congestion Traffic Light Simulator Using Computer Networks Concepts**

---

## 2. Project Overview
In a road traffic network, vehicles travel along streets. When the number of vehicles is small, traffic flows smoothly. As volume increases, vehicles queue behind bottlenecks and intersections. If too many vehicles arrive at once, gridlock occurs.

A computer network functions analogously:
- **Vehicles** are analogous to **Data Packets**.
- **Road bottlenecks / intersections** are analogous to **Routers / Switches**.
- **Waiting lanes** are analogous to **Router Memory Buffers (Queues)**.

This simulator maps router congestion directly to an intuitive 3-aspect **Traffic Light**:
- 🟢 **GREEN (Low Congestion):** Offered traffic is well within router capacity ($\rho < 0.70$). Packets are processed with negligible queuing delay.
- 🟡 **YELLOW (Moderate Congestion):** Offered traffic approaches router capacity ($0.70 \le \rho < 1.00$) or buffer occupancy increases. Queuing delay rises.
- 🔴 **RED (High Congestion):** Offered traffic meets or exceeds capacity ($\rho \ge 1.00$) or buffer fills ($\ge 85\%$). The router queue saturates, resulting in **Tail Drop Packet Loss**.

---

## 3. Problem Statement
Understanding network congestion and queuing dynamics from textbook formulas alone (such as Kleinrock’s queuing equations or TCP congestion avoidance) is often challenging for computer science and engineering undergraduates. Many students struggle to connect theoretical terms like *Offered Load*, *Service Rate*, *Bufferbloat*, *Tail Drop*, and *Congestion Collapse* with physical intuition. 

Existing industrial network tools (like Wireshark, NS-3, or Mininet) have steep learning curves and produce complex trace logs. There is a need for a lightweight, interactive, visual simulator that:
1. Runs out-of-the-box on a laptop without complex dependencies.
2. Provides immediate visual and intuitive feedback using a traffic light.
3. Allows students to dynamically control traffic rates, trigger congestion, and observe recovery in real time during viva presentations.

---

## 4. Main Objectives
1. **Visualize Congestion Transitions:** Show students how changing the packet arrival rate shifts the network from Green $\to$ Yellow $\to$ Red.
2. **Demonstrate Queuing Behavior:** Illustrate how router queues absorb brief bursts but grow unstably when arrival rate permanently exceeds processing capacity.
3. **Illustrate Packet Discard (Tail Drop):** Prove that once the finite memory buffer fills up, all subsequent arriving packets are dropped.
4. **Demonstrate Congestion Recovery:** Show how throttling incoming traffic drains the queue, eliminates packet loss, and restores the Green status.
5. **Relate Key Metrics:** Interactively link Offered Load, Processing Capacity, Current Queue Length, Effective Throughput, and Packet Loss Rate.

---

## 5. Computer Networks Concepts Used

| Concept | Networking Definition | Simulator Implementation |
| :--- | :--- | :--- |
| **Offered Load ($\lambda$)** | The rate of incoming packets attempting to enter the router. | Controlled via **Incoming Traffic Rate** slider ($0 - 150\text{ pkts/s}$). |
| **Service Capacity ($\mu$)** | The maximum rate at which the router can forward packets. | Controlled via **Router Processing Capacity** slider ($5 - 120\text{ pkts/s}$). |
| **Utilization ($\rho = \lambda / \mu$)** | Ratio of arrival rate to service capacity. | Displayed in dashboard; drives the traffic light state transitions. |
| **Router Buffer (Queue)** | FIFO memory buffer storing packets awaiting forwarding. | Finite queue with configurable size ($10 - 200\text{ packets}$). |
| **Tail Drop (Packet Loss)** | Discarding incoming packets when the buffer is $100\%$ full. | Tracked by **Total Dropped Packets** and **Packet Loss Rate (%)**. |
| **Effective Throughput** | The realized rate of packets successfully processed and sent. | Instantaneous rate: $\min(\text{Arrival Rate}, \text{Service Capacity})$ in steady-state. |
| **Congestion Recovery** | Buffer draining achieved by throttling arrival rates. | Simulated via the **Reduce Traffic** button and dynamic slider decrease. |

---

## 6. Technologies Used
- **Programming Language:** Python 3 (Version 3.8 to 3.13+)
- **Graphical User Interface (GUI):** `tkinter` (Python Standard Library)
- **Real-time Telemetry Plotting:** `matplotlib` (`FigureCanvasTkAgg` embedded directly in Tkinter)
- **Data Persistence & Reporting:** `csv` (Python Standard Library)
- **Supported Operating Systems:** Windows 10/11, macOS, Linux

No databases, paid APIs, web servers, or cloud accounts are required.

---

## 7. Application Features

### A. Authentic 3-Aspect Traffic Light
- Rendered on a dark housing canvas with curved hood visors and radial lighting glow.
- Only the currently active state (Red, Yellow, or Green) is illuminated; inactive lamps stay realistically dim.
- Includes a prominent status badge and dynamic pedagogical explanation describing the current networking state.

### B. Interactive Traffic Flow Controls
- **Incoming Traffic Rate Slider:** $0$ to $150\text{ packets/s}$ (Default: $30$).
- **Router Processing Capacity Slider:** $5$ to $120\text{ packets/s}$ (Default: $50$).
- **Maximum Queue Capacity Slider:** $10$ to $200\text{ packets}$ (Default: $100$).
- **Simulation Lifecycle Controls:** Start, Pause, Resume, and Reset buttons.
- **Congestion Injection Button (⚡ Heavy Traffic):** Instantly sets input traffic to $80\text{ pkts/s}$ to induce buffer buildup.
- **Recovery Demonstration Button (💧 Reduce Traffic):** Throttles traffic to $20\text{ pkts/s}$ to demonstrate buffer draining.

### C. Live Telemetry Dashboard (8 Metric Cards)
1. **Total Incoming Packets:** Cumulative count of packets arrived at the router.
2. **Total Processed Packets:** Cumulative count of packets successfully forwarded.
3. **Total Dropped Packets:** Cumulative count of packets discarded due to buffer overflow.
4. **Current Queue Length:** Displays `Current / Max` packets and percentage fullness.
5. **Network Utilization (%):** Offered load ratio; values over $100\%$ highlight severe overload.
6. **Effective Throughput:** Realized packets transmitted per second.
7. **Packet Loss Rate (%):** $( \text{Dropped} / \text{Incoming} ) \times 100\%$, with division-by-zero protection.
8. **Simulation Time:** Real-time clock in `MM:SS.s` format.

### D. Live Dual Matplotlib Graphs
- **Graph 1 (Rates vs. Time):** Shows Offered Rate (Cyan) vs. Router Processing Capacity (Red dashed) vs. Effective Throughput (Green).
- **Graph 2 (Queue Evolution):** Shows Buffer Occupancy (Purple) with a reference line for Maximum Queue Capacity.
- Graphs use smooth, downsampled sliding time windows ($45\text{ seconds}$) for zero GUI stutter.

### E. One-Click Demonstration Presets
- **Scenario 1 (Normal Traffic):** $20\text{ in} / 50\text{ cap}$ $\to$ Green light, no loss.
- **Scenario 2 (Increasing Traffic):** $40\text{ in} / 50\text{ cap}$ $\to$ Yellow light, approaching capacity.
- **Scenario 3 (Heavy Congestion):** $80\text{ in} / 50\text{ cap}$ $\to$ Red light, buffer overflow, packet loss.

### F. CSV Report Export
- Exports a complete session summary and detailed time-series telemetry to CSV for report submission.

### G. In-App Viva & Concept Guide
- Interactive modal window with definitions, queuing theory notes, and anticipated professor viva questions.

---

## 8. Installation Instructions (Beginner-Friendly for Windows & VS Code)

### Prerequisites
- **Python 3.8 or higher** installed. (Download from [python.org](https://www.python.org/) if needed, ensuring **"Add Python to PATH"** is checked during setup).
- **Visual Studio Code** installed.

### Step-by-Step Setup
1. **Open the Project in VS Code:**
   - Launch VS Code.
   - Click **File > Open Folder...** and select the `network-congestion-simulator` folder.

2. **Open the Integrated Terminal:**
   - Press ``Ctrl + ` `` (Ctrl + Backtick) or navigate to **Terminal > New Terminal**.

3. **Install Dependencies:**
   Run the following command in the terminal:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Matplotlib is the only external package required; `tkinter`, `csv`, and `time` come built into Python).*

---

## 9. Commands to Run and Test

### Run the Application:
```bash
python main.py
```

### Run the Automated Accuracy Test Suite:
```bash
python test_simulation.py
```

---

## 10. Explanation of the Simulation Algorithm

The simulation operates using a continuous elapsed-time integration loop ($10\text{ updates/second}$, $\Delta t \approx 0.1\text{s}$):

```
                   Incoming Traffic (λ pkts/s)
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Router Checkpoint   │
                  └──────────┬───────────┘
                             │
                    Is Queue Full?
                    (q == MaxQueue)
                    /              \
                 YES                NO
                 /                    \
     ┌──────────────────────┐   ┌──────────────────────┐
     │ Discard Packet       │   │ Admitted into FIFO   │
     │ (Total Dropped += 1) │   │ Buffer Queue (q++)   │
     └──────────────────────┘   └──────────┬───────────┘
                                           │
                                 Service Capacity (μ)
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │ Process & Forward    │
                                │ (Total Processed +=1)│
                                └──────────────────────┘
```

### Mathematical Decision Rules for the Traffic Light
Let $\rho = \frac{\lambda}{\mu}$ be the **Offered Load Ratio** and $Q_{ratio} = \frac{Q_{current}}{Q_{max}}$ be the **Queue Occupancy Ratio**:

$$\text{Congestion Level} = \max(\rho, Q_{ratio})$$

1. 🟢 **GREEN (Low Congestion):**
   $$\rho < 0.70 \quad \text{AND} \quad Q_{ratio} < 0.50$$
   *Condition:* The router is operating well below capacity and buffer backlog is minimal.

2. 🟡 **YELLOW (Moderate Congestion):**
   $$(0.70 \le \rho < 1.00) \quad \text{OR} \quad (0.50 \le Q_{ratio} < 0.85)$$
   *Condition:* Traffic is nearing processing capacity or the queue is moderately full.

3. 🔴 **RED (High Congestion):**
   $$\rho \ge 1.00 \quad \text{OR} \quad Q_{ratio} \ge 0.85$$
   *Condition:* Incoming rate meets/exceeds service rate or the queue is nearing maximum capacity ($85\%+$). Tail drop discards occur when $Q_{ratio} = 1.00$.

---

## 11. Sample Results & Visualizations

### Scenario 1: Normal Traffic (Smooth Flow)
- **Settings:** Arrival = $20\text{ pkts/s}$, Capacity = $50\text{ pkts/s}$, Queue = $100$
- **Result:** Offered load is $40\%$. The traffic light illuminates **GREEN**. Queue length fluctuates near $0-2$ packets. Zero packets dropped.

---

### Scenario 2: Increasing Traffic (Approaching Capacity)
- **Settings:** Arrival = $40\text{ pkts/s}$, Capacity = $50\text{ pkts/s}$, Queue = $100$
- **Result:** Offered load is $80\%$. The traffic light illuminates **YELLOW**. Small queue builds up. Zero packets dropped, but headroom is reduced.

---

### Scenario 3: Heavy Congestion (Buffer Overflow & Tail Drop)
- **Settings:** Arrival = $80\text{ pkts/s}$, Capacity = $50\text{ pkts/s}$, Queue = $100$
- **Result:** Offered load is $160\%$. The traffic light illuminates **RED**. Queue fills to $100/100$ packets. Subsequent arrivals are discarded. Packet loss rate continuously increases.


---

### Scenario 4: Congestion Recovery Demonstration
- **Action:** Click **"💧 Reduce Traffic (20 pkts/s)"**.
- **Result:** Arrival rate drops below processing capacity. The router continues forwarding queued packets at $50\text{ pkts/s}$. The queue drains steadily to $0$. Once the queue is clear, the traffic light transitions back to **GREEN**.

---

## 12. Classroom Demonstration Script (For Viva & Presentation)

When demonstrating this project to a professor, follow this 4-step sequence:

1. **Step 1: Baseline Demonstration (Normal State)**
   - Click **Scenario 1: Normal Traffic**.
   - Explain: *"Here, the arrival rate is 20 pkts/s and router capacity is 50 pkts/s. Utilization is 40%, the queue remains empty, and the traffic light is GREEN."*

2. **Step 2: Moderate Load (Transition State)**
   - Click **Scenario 2: Increasing Traffic**.
   - Explain: *"Incoming traffic is increased to 40 pkts/s (80% utilization). The traffic light changes to YELLOW to warn that traffic is approaching capacity."*

3. **Step 3: Inducing Congestion & Tail Drop**
   - Click **⚡ Generate Heavy Traffic (80 pkts/s)**.
   - Explain: *"Since arrival rate (80 pkts/s) exceeds service rate (50 pkts/s), the queue fills linearly. Once the buffer hits 100 packets, the router can no longer store packets, resulting in Tail Drop. Notice the RED traffic light and increasing Packet Loss Rate."*

4. **Step 4: Demonstrating Congestion Recovery**
   - Click **💧 Reduce Traffic (20 pkts/s)**.
   - Explain: *"This simulates TCP backing off. Arrival rate is lowered to 20 pkts/s. The router processes 50 pkts/s, draining 30 packets per second from the backlog. Once drained, the light returns to GREEN."*

5. **Step 5: Exporting Data**
   - Click **💾 Export CSV Report** to show the saved data log.

---

## 13. Limitations & Future Enhancements

### Current Limitations:
- The queue uses **FIFO (First-In, First-Out)** with **Tail Drop**. Complex Active Queue Management (AQM) algorithms like RED (Random Early Detection) are not simulated.
- Simulation runs deterministically on a single router node rather than a multi-hop mesh network topology.

### Future Enhancements:
1. **Multi-Hop Topologies:** Simulate multiple connected routers with varying link bandwidths and bottleneck links.
2. **TCP vs. UDP Flow Simulation:** Implement adaptive TCP flow control (AIMD / Reno) side-by-side with unresponsive UDP traffic.
3. **Advanced Queuing Disciplines:** Add toggles for Priority Queuing (PQ), Weighted Fair Queuing (WFQ), and Random Early Detection (RED).
4. **Packet Delay / Jitter Graph:** Add a real-time latency plot tracking queuing delay in milliseconds.

---

## 14. License & Credits
Developed as an educational computer networks laboratory project. Clean, well-commented, and free to modify for academic demonstrations and coursework.
