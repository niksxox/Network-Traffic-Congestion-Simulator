"""
Automated Test Suite for Network Congestion Traffic Light Simulator
Validates core simulation engine accuracy, queuing discipline, tail drop,
recovery, and metrics calculation.
"""

import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from main import NetworkSimulationEngine

def run_tests():
    print("==================================================")
    print("RUNNING NETWORK SIMULATION ACCURACY TEST SUITE")
    print("==================================================")

    # Test 1: Initialization defaults
    engine = NetworkSimulationEngine(arrival_rate=30, service_rate=50, max_queue=100)
    assert engine.arrival_rate == 30.0
    assert engine.service_rate == 50.0
    assert engine.max_queue == 100
    assert engine.queue_length == 0
    assert engine.total_incoming == 0
    assert engine.total_processed == 0
    assert engine.total_dropped == 0
    assert engine.offered_load == 0.6
    state_col, _ = engine.get_congestion_state()
    assert state_col == "GREEN", f"Expected GREEN, got {state_col}"
    print("[PASS] Test 1: Initialization & Default State (GREEN)")

    # Test 2: Normal Traffic (Scenario 1)
    engine.start()
    # Simulate 2 seconds of traffic at 20 pkts/s arrival and 50 pkts/s service
    engine.update_parameters(arrival_rate=20, service_rate=50, max_queue=100)
    for _ in range(20):
        time.sleep(0.05)
        engine.tick()

    assert engine.total_incoming > 0
    assert engine.total_processed <= engine.total_incoming
    assert engine.total_dropped == 0
    assert engine.queue_length < 10
    state_col, _ = engine.get_congestion_state()
    assert state_col == "GREEN"
    print(f"[PASS] Test 2: Normal Traffic Scenario (Arrived: {engine.total_incoming}, Processed: {engine.total_processed}, Dropped: {engine.total_dropped}, Light: {state_col})")

    # Test 3: Increasing Traffic (Scenario 2 - Yellow)
    engine.update_parameters(arrival_rate=40, service_rate=50)
    for _ in range(15):
        time.sleep(0.05)
        engine.tick()

    state_col, _ = engine.get_congestion_state()
    assert state_col == "YELLOW", f"Expected YELLOW, got {state_col}"
    print(f"[PASS] Test 3: Increasing Traffic Scenario (Offered load: {engine.offered_load:.2f}, Light: {state_col})")

    # Test 4: Heavy Traffic and Buffer Overflow (Scenario 3 - Red & Tail Drop)
    engine.update_parameters(arrival_rate=120, service_rate=40, max_queue=30)
    # Run long enough to saturate queue (capacity 30) and force drops
    for _ in range(40):
        time.sleep(0.05)
        engine.tick()

    assert engine.total_dropped > 0, "Packets must be dropped when queue is full"
    assert engine.queue_length >= engine.max_queue - 5, f"Queue {engine.queue_length} should be near max {engine.max_queue}"
    assert engine.packet_loss_rate_percent > 0.0
    state_col, _ = engine.get_congestion_state()
    assert state_col == "RED", f"Expected RED, got {state_col}"
    print(f"[PASS] Test 4: Heavy Traffic & Tail Drop (Queue: {engine.queue_length}/{engine.max_queue}, Dropped: {engine.total_dropped}, Loss Rate: {engine.packet_loss_rate_percent:.1f}%, Light: {state_col})")

    # Test 5: Congestion Recovery
    # Reduce arrival rate to 10 pkts/s with service rate 60 pkts/s -> queue must drain to 0
    engine.update_parameters(arrival_rate=10, service_rate=60)
    for _ in range(50):
        time.sleep(0.05)
        engine.tick()

    assert engine.queue_length == 0, f"Expected queue to drain to 0, got {engine.queue_length}"
    state_col, _ = engine.get_congestion_state()
    assert state_col == "GREEN", f"Expected GREEN after drain, got {state_col}"
    print(f"[PASS] Test 5: Congestion Recovery (Queue drained to: {engine.queue_length}, Light returned to: {state_col})")

    # Test 6: Pause and Resume
    engine.pause()
    assert engine.is_paused is True
    time.sleep(0.1)
    state_before = engine.total_incoming
    engine.tick()
    assert engine.total_incoming == state_before, "No progress during pause"
    engine.resume()
    assert engine.is_paused is False
    print("[PASS] Test 6: Pause and Resume integrity")

    # Test 7: Reset functionality
    engine.reset()
    assert engine.total_incoming == 0
    assert engine.total_processed == 0
    assert engine.total_dropped == 0
    assert engine.queue_length == 0
    assert engine.simulation_time == 0.0
    assert len(engine.history_time) == 0
    print("[PASS] Test 7: Reset functionality completely clears all state")

    print("\nALL 7 TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
