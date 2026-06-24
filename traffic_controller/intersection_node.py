import os
import sys
import traci
import requests

from traffic_collector import TrafficCollector
from signal_controller import SignalController
from data_logger import TrafficDataLogger

# Add project root and ml directory to sys.path to resolve CongestionPredictor import
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
ml_path = os.path.join(project_root, "ml")
if ml_path not in sys.path:
    sys.path.append(ml_path)

try:
    from predictor import CongestionPredictor
    PREDICTOR_AVAILABLE = True
except ImportError:
    PREDICTOR_AVAILABLE = False

class IntersectionNode:
    def __init__(self, intersection_id, save_data=False, use_predictor=True):
        """
        Orchestrates localized metrics collection, CSV data logging, ML inference, and signal control.
        
        :param intersection_id: The ID of the intersection (e.g. 'node_0_0')
        :param save_data: Boolean, if True enables local dataset logging
        :param use_predictor: Boolean, if True attempts to load the local ML model
        """
        self.intersection_id = intersection_id
        self.save_data = save_data
        
        # Mapping of intersections to Rust server ports
        port_map = {
            "node_0_0": 5000,
            "node_0_1": 5001,
            "node_1_0": 5002,
            "node_1_1": 5003
        }
        self.port = port_map[intersection_id]
        
        # Localized data collection
        self.collector = TrafficCollector(intersection_id)
        
        # Localized signal control
        self.signal_controller = SignalController(intersection_id)
        
        # Localized data logger
        self.logger = TrafficDataLogger(filename=f"{intersection_id}.csv") if save_data else None
        
        # Tracker for connection errors (prints warning once to avoid console spam)
        self.rust_offline_logged = False
        
        # Localized predictor loading
        self.predictor = None
        if use_predictor and PREDICTOR_AVAILABLE:
            model_filename = f"model_{intersection_id}.pkl"
            model_path = os.path.join(project_root, "ml", "models", model_filename)
            
            if os.path.exists(model_path):
                try:
                    self.predictor = CongestionPredictor(model_filename=model_filename)
                    print(f"[{intersection_id}] Loaded local prediction model: {model_filename}")
                except Exception as e:
                    print(f"[{intersection_id}] Warning: Failed to load local model {model_filename} ({e}). Falling back to rule-only control.")
            else:
                print(f"[{intersection_id}] Warning: No local model file found at {model_path}. Operating in rule-only control.")
        else:
            if use_predictor:
                print(f"[{intersection_id}] Warning: ML Predictor modules not imported. Operating in rule-only control.")

        # Cache variables
        self.metrics = None
        self.predicted_congestion = None
        self.congestion_labels_map = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}

    def step_collection(self, step):
        """
        Collects metrics, performs local prediction, and logs to local CSV files.
        Should be called at every simulation step before updating signals.
        
        :param step: Current simulation step index (int)
        :return: Dict containing live metrics
        """
        self.metrics = self.collector.collect_metrics()
        
        if self.predictor:
            try:
                self.predicted_congestion = self.predictor.predict(
                    self.metrics["vehicle_count"],
                    self.metrics["queue_length"],
                    self.metrics["waiting_time"],
                    self.metrics["average_speed"]
                )
            except Exception as e:
                print(f"[{self.intersection_id}] Prediction error: {e}")
                self.predicted_congestion = None
        else:
            self.predicted_congestion = None
            
        if self.logger:
            self.logger.log_step(step, self.intersection_id, self.metrics)
            
        return self.metrics

    def send_updates_to_rust(self, step):
        """
        Asynchronously POSTs local updates (congestion and priority requests) to the local Rust node.
        """
        if self.metrics is None:
            return

        url_congestion = f"http://127.0.0.1:{self.port}/congestion"
        url_priority = f"http://127.0.0.1:{self.port}/priority"
        
        # Translate numerical prediction (default to LOW if no predictor is active)
        level_label = self.congestion_labels_map.get(self.predicted_congestion, "LOW")
        
        # Check if there are priority vehicles on approaching lanes
        has_ambulance = False
        has_bus = False
        for lane_id in self.collector.lanes:
            veh_ids = traci.lane.getLastStepVehicleIDs(lane_id)
            for veh_id in veh_ids:
                vtype = traci.vehicle.getTypeID(veh_id)
                if vtype == "ambulance":
                    has_ambulance = True
                elif vtype == "bus":
                    has_bus = True

        try:
            # 1. Send congestion update
            requests.post(
                url_congestion, 
                json={"intersection": self.intersection_id, "level": level_label},
                timeout=0.1 # Small timeout to prevent simulation steps from blocking
            )
            
            # 2. Send priority requests if emergency or transit is present
            if has_ambulance:
                requests.post(
                    url_priority, 
                    json={"vehicle_type": "ambulance", "direction": "unknown"},
                    timeout=0.1
                )
            elif has_bus:
                requests.post(
                    url_priority, 
                    json={"vehicle_type": "bus", "direction": "unknown"},
                    timeout=0.1
                )
                
            self.rust_offline_logged = False # Reset if connection succeeds
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if not self.rust_offline_logged:
                print(f"[{self.intersection_id}] Warning: Rust server on port {self.port} is offline. "
                      f"Skipping inter-node message propagation.")
                self.rust_offline_logged = True

    def fetch_neighbor_warnings(self):
        """
        GETs neighbor warning logs from the local Rust server.
        
        :return: List of warning strings
        """
        url_warnings = f"http://127.0.0.1:{self.port}/warnings"
        try:
            response = requests.get(url_warnings, timeout=0.1)
            if response.status_code == 200:
                return response.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        return []

    def step_control(self, warnings=None):
        """
        Triggers local signal control adjustments, accounting for neighbor warnings.
        
        :param warnings: List of warning strings (from adjacent intersections)
        """
        if self.metrics is None:
            raise ValueError(f"[{self.intersection_id}] Error: Cannot execute control step before collection step.")
            
        # Log received warnings
        if warnings:
            for warning in warnings:
                print(f"   >>> [{self.intersection_id}] Neighbor alert received: {warning}")
                
        # Forward metrics, predictions, and neighbor alerts to the traffic signal controller
        self.signal_controller.update_signals(self.metrics, self.predicted_congestion, warnings)
