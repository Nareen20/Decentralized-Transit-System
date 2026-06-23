import traci

class SignalController:
    def __init__(self, intersection_id, max_green_time=90.0, yellow_duration=3.0):
        """
        Rule-Based, ML-Adaptive, and Cooperative Traffic Signal Controller for a single intersection.
        
        :param intersection_id: The ID of the intersection (e.g. 'node_0_0')
        :param max_green_time: Maximum allowed duration for a green phase to prevent starvation (seconds)
        :param yellow_duration: Duration of yellow transition phases (seconds)
        """
        self.intersection_id = intersection_id
        self.max_green_time = max_green_time
        self.yellow_duration = yellow_duration
        
        # Mapping of directional lanes for this intersection.
        # SUMO Link checks show Phase 2 is Green for EW, and Phase 0 is Green for NS.
        intersection_directions_map = {
            "node_0_0": {
                "EW": ["E_west0_to_n00_0", "E_west0_to_n00_1", "E_n10_to_n00_0", "E_n10_to_n00_1"],
                "NS": ["E_south0_to_n00_0", "E_south0_to_n00_1", "E_n01_to_n00_0", "E_n01_to_n00_1"]
            },
            "node_0_1": {
                "EW": ["E_west1_to_n01_0", "E_west1_to_n01_1", "E_n11_to_n01_0", "E_n11_to_n01_1"],
                "NS": ["E_n00_to_n01_0", "E_n00_to_n01_1", "E_north0_to_n01_0", "E_north0_to_n01_1"]
            },
            "node_1_0": {
                "EW": ["E_n00_to_n10_0", "E_n00_to_n10_1", "E_east0_to_n10_0", "E_east0_to_n10_1"],
                "NS": ["E_south1_to_n10_0", "E_south1_to_n10_1", "E_n11_to_n10_0", "E_n11_to_n10_1"]
            },
            "node_1_1": {
                "EW": ["E_n01_to_n11_0", "E_n01_to_n11_1", "E_east1_to_n11_0", "E_east1_to_n11_1"],
                "NS": ["E_n10_to_n11_0", "E_n10_to_n11_1", "E_north1_to_n11_0", "E_north1_to_n11_1"]
            }
        }
        
        if intersection_id not in intersection_directions_map:
            raise ValueError(f"Unknown intersection ID: {intersection_id}")
            
        self.directions = intersection_directions_map[intersection_id]
        
        # State tracking to prevent green phase starvation
        self.last_phase = 0
        self.green_start_time = 0.0
        
        # State tracking to detect when emergency vehicles have just passed
        self.had_emerg_ew = False
        self.had_emerg_ns = False
        
        # State tracking for congestion extensions (starvation/stagnation prevention)
        self.consecutive_congestion_extensions = 0
        self.last_extension_queue = 0
        
    def _check_priority_vehicles(self, lanes):
        """Scans specified lanes for emergency and bus vehicle types."""
        has_emergency = False
        has_bus = False
        
        for lane_id in lanes:
            veh_ids = traci.lane.getLastStepVehicleIDs(lane_id)
            for veh_id in veh_ids:
                try:
                    vtype = traci.vehicle.getTypeID(veh_id)
                except Exception:
                    vtype = ""
                try:
                    vclass = traci.vehicle.getVehicleClass(veh_id)
                except Exception:
                    vclass = ""
                
                # Check for emergency vehicles (ambulance, fire truck, police, or vClass=emergency)
                if vclass == "emergency" or vtype in ["ambulance", "fire_truck", "police"] or any(x in vtype for x in ["emergency", "fire", "police"]):
                    has_emergency = True
                # Check for buses
                elif vclass == "bus" or vtype == "bus" or "bus" in vtype:
                    has_bus = True
                    
        return has_emergency, has_bus

    def _get_queue_length(self, lanes):
        """Sums halting vehicles on specified lanes to compute queue length."""
        return sum(traci.lane.getLastStepHaltingNumber(lane_id) for lane_id in lanes)

    def update_signals(self, metrics, predicted_congestion=None, warnings=None):
        """
        Evaluates and applies signal control, accounting for neighbor warnings.
        
        :param metrics: Current live metrics dict (from TrafficCollector)
        :param predicted_congestion: Congestion level predicted by ML model (0, 1, or 2)
        :param warnings: List of warning strings from adjacent intersections (polled from Rust)
        """
        current_time = traci.simulation.getTime()
        
        # 1. Retrieve current traffic light state
        current_phase = traci.trafficlight.getPhase(self.intersection_id)
        next_switch = traci.trafficlight.getNextSwitch(self.intersection_id)
        remaining_time = next_switch - current_time
        
        # Detect phase switches to reset green timer and extension counts
        if current_phase != self.last_phase:
            if current_phase in [0, 2]:  # Transitioned into a Green phase
                self.green_start_time = current_time
                self.consecutive_congestion_extensions = 0
                self.last_extension_queue = 0
            self.last_phase = current_phase
            
        # 2. Check for priority vehicles
        has_emerg_ew, has_bus_ew = self._check_priority_vehicles(self.directions["EW"])
        has_emerg_ns, has_bus_ns = self._check_priority_vehicles(self.directions["NS"])
        
        action_taken = None
        
        # --- Check if emergency vehicle has just passed ---
        if not has_emerg_ew and not has_emerg_ns:
            if self.had_emerg_ew:
                # Emergency vehicle on EW has passed. Transition immediately to NS Green (Phase 0) via EW Yellow (Phase 3).
                traci.trafficlight.setPhase(self.intersection_id, 3)
                traci.trafficlight.setPhaseDuration(self.intersection_id, self.yellow_duration)
                action_taken = "Emergency EW: Passed. Transitioning to NS Green"
                print(f"[{self.intersection_id}] Emergency cleared - Returning to normal control")
            elif self.had_emerg_ns:
                # Emergency vehicle on NS has passed. Transition immediately to EW Green (Phase 2) via NS Yellow (Phase 1).
                traci.trafficlight.setPhase(self.intersection_id, 1)
                traci.trafficlight.setPhaseDuration(self.intersection_id, self.yellow_duration)
                action_taken = "Emergency NS: Passed. Transitioning to EW Green"
                print(f"[{self.intersection_id}] Emergency cleared - Returning to normal control")
            
            # Reset state
            self.had_emerg_ew = False
            self.had_emerg_ns = False
            
            if action_taken:
                print(f"   >>> [TL CONTROL] {self.intersection_id} at {current_time:.1f}s | {action_taken}")
                self.last_phase = traci.trafficlight.getPhase(self.intersection_id)
                return
        
        # --- RULE 1: EMERGENCY VEHICLE PRIORITY (Highest Priority) ---
        # Emergency vehicles require immediate green, overriding yellow transition phases if needed
        if has_emerg_ew or has_emerg_ns:
            if has_emerg_ew and has_emerg_ns:
                # Conflict: emergency vehicles approaching from both directions.
                # Keep or set to green on the current phase direction to avoid unnecessary transitions.
                if current_phase in [2, 3]:  # EW Green or EW Yellow
                    if current_phase != 2:
                        traci.trafficlight.setPhase(self.intersection_id, 2)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    action_taken = "EMERGENCY CONFLICT: Extended/Set EW Green"
                else:  # NS Green or NS Yellow
                    if current_phase != 0:
                        traci.trafficlight.setPhase(self.intersection_id, 0)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    action_taken = "EMERGENCY CONFLICT: Extended/Set NS Green"
            elif has_emerg_ew:
                if current_phase != 2:  # If not EW Green (Phase 2), switch immediately
                    traci.trafficlight.setPhase(self.intersection_id, 2)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    action_taken = "Emergency EW: Switch to Immediate EW Green"
                else:
                    if remaining_time < 10.0:
                        traci.trafficlight.setPhase(self.intersection_id, 2)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                        action_taken = "Emergency EW: Extended EW Green"
            elif has_emerg_ns:
                if current_phase != 0:  # If not NS Green (Phase 0), switch immediately
                    traci.trafficlight.setPhase(self.intersection_id, 0)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    action_taken = "Emergency NS: Switch to Immediate NS Green"
                else:
                    if remaining_time < 10.0:
                        traci.trafficlight.setPhase(self.intersection_id, 0)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                        action_taken = "Emergency NS: Extended NS Green"
                        
            # Apply action if taken for emergency vehicle
            if action_taken:
                # Store the state so we know it was active in this step
                self.had_emerg_ew = has_emerg_ew
                self.had_emerg_ns = has_emerg_ns
                # Reset green start time since we forced/extended a green phase
                new_phase = traci.trafficlight.getPhase(self.intersection_id)
                if new_phase != current_phase:
                    self.green_start_time = current_time
                    self.last_phase = new_phase
                print(f"[{self.intersection_id}] Emergency detected - Granting GREEN")
                print(f"   >>> [TL CONTROL] {self.intersection_id} at {current_time:.1f}s | {action_taken} | "
                      f"Spent Green={current_time - self.green_start_time:.1f}s (Max={self.max_green_time}s)")
                return

        # If currently in a yellow transition phase and no emergency vehicle is present, let it complete safely
        if current_phase in [1, 3]:
            return
            
        # 3. Retrieve directional queues
        queue_ew = self._get_queue_length(self.directions["EW"])
        queue_ns = self._get_queue_length(self.directions["NS"])
        
        # Compute total time spent in current green phase
        time_spent_green = current_time - self.green_start_time
        is_starved = time_spent_green >= self.max_green_time
        
        # --- RULE 2: BUS PRIORITY (Medium Priority - Unconditional) ---
        if (has_bus_ew or has_bus_ns) and not is_starved:
            if has_bus_ew and has_bus_ns:
                if current_phase in [2, 3]:  # EW Green or EW Yellow
                    if remaining_time < 8.0:
                        traci.trafficlight.setPhase(self.intersection_id, 2)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 8.0)
                        action_taken = "BUS CONFLICT: Extended EW Green"
                else:  # NS Green or NS Yellow
                    if remaining_time < 8.0:
                        traci.trafficlight.setPhase(self.intersection_id, 0)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 8.0)
                        action_taken = "BUS CONFLICT: Extended NS Green"
            elif has_bus_ew:
                if current_phase == 2:  # EW Green (Phase 2)
                    if remaining_time < 8.0:
                        traci.trafficlight.setPhase(self.intersection_id, 2)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 8.0)
                        action_taken = "Bus EW: Extended EW Green"
                elif current_phase == 0:  # NS Green (Phase 0)
                    traci.trafficlight.setPhase(self.intersection_id, 1)  # Transition to EW Green via NS Yellow
                    traci.trafficlight.setPhaseDuration(self.intersection_id, self.yellow_duration)
                    action_taken = "Bus EW: Triggered Transition to EW Green"
            elif has_bus_ns:
                if current_phase == 0:  # NS Green (Phase 0)
                    if remaining_time < 8.0:
                        traci.trafficlight.setPhase(self.intersection_id, 0)
                        traci.trafficlight.setPhaseDuration(self.intersection_id, 8.0)
                        action_taken = "Bus NS: Extended NS Green"
                elif current_phase == 2:  # EW Green (Phase 2)
                    traci.trafficlight.setPhase(self.intersection_id, 3)  # Transition to NS Green via EW Yellow
                    traci.trafficlight.setPhaseDuration(self.intersection_id, self.yellow_duration)
                    action_taken = "Bus NS: Triggered Transition to NS Green"
                    
        # --- RULE 3: CONGESTION-BASED ADAPTIVE EXTENSION (Lowest Priority - Rule/ML/Cooperative Combined) ---
        elif remaining_time <= 2.0 and not is_starved:
            # Check conditions
            ml_high_congestion = (predicted_congestion == 2)
            rule_ew_congested = (current_phase == 2 and queue_ew >= 4 and queue_ns < queue_ew)
            rule_ns_congested = (current_phase == 0 and queue_ns >= 4 and queue_ew < queue_ns)
            has_neighbor_warning = (warnings is not None) and (len(warnings) > 0)
            
            # Determine current queue size on the active green approach
            current_queue = queue_ew if current_phase == 2 else queue_ns
            
            # Prevention of starvation and queue stagnation
            allow_extension = True
            if self.consecutive_congestion_extensions >= 3:
                allow_extension = False
            elif self.consecutive_congestion_extensions > 0 and current_queue >= self.last_extension_queue:
                allow_extension = False
                
            if allow_extension:
                if current_phase == 2 and (ml_high_congestion or rule_ew_congested or has_neighbor_warning):
                    traci.trafficlight.setPhase(self.intersection_id, 2)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    
                    if has_neighbor_warning:
                        source = "Cooperative Alert"
                    elif ml_high_congestion:
                        source = "ML"
                    else:
                        source = "Rule"
                    action_taken = f"Congestion ({source}): Extended EW Green (+10s)"
                    
                    # Update extension tracking state
                    self.last_extension_queue = current_queue
                    self.consecutive_congestion_extensions += 1
                    
                elif current_phase == 0 and (ml_high_congestion or rule_ns_congested or has_neighbor_warning):
                    traci.trafficlight.setPhase(self.intersection_id, 0)
                    traci.trafficlight.setPhaseDuration(self.intersection_id, 10.0)
                    
                    if has_neighbor_warning:
                        source = "Cooperative Alert"
                    elif ml_high_congestion:
                        source = "ML"
                    else:
                        source = "Rule"
                    action_taken = f"Congestion ({source}): Extended NS Green (+10s)"
                    
                    # Update extension tracking state
                    self.last_extension_queue = current_queue
                    self.consecutive_congestion_extensions += 1
        
        # Print trigger log if action was taken
        if action_taken:
            if "Bus" in action_taken or "BUS" in action_taken:
                print(f"[{self.intersection_id}] Bus detected - Granting Priority")
            print(f"   >>> [TL CONTROL] {self.intersection_id} at {current_time:.1f}s | {action_taken} | "
                  f"Spent Green={current_time - self.green_start_time:.1f}s (Max={self.max_green_time}s)")
