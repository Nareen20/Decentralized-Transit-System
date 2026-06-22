import traci

class TrafficCollector:
    def __init__(self, intersection_id):
        """
        Collects traffic metrics for a single intersection.
        
        :param intersection_id: The ID of the intersection (e.g. 'node_0_0')
        """
        self.intersection_id = intersection_id
        
        # Mapping of intersections to their incoming lane IDs.
        intersection_lanes_map = {
            "node_0_0": [
                "E_west0_to_n00_0", "E_west0_to_n00_1",
                "E_south0_to_n00_0", "E_south0_to_n00_1",
                "E_n10_to_n00_0", "E_n10_to_n00_1",
                "E_n01_to_n00_0", "E_n01_to_n00_1"
            ],
            "node_0_1": [
                "E_west1_to_n01_0", "E_west1_to_n01_1",
                "E_n00_to_n01_0", "E_n00_to_n01_1",
                "E_n11_to_n01_0", "E_n11_to_n01_1",
                "E_north0_to_n01_0", "E_north0_to_n01_1"
            ],
            "node_1_0": [
                "E_n00_to_n10_0", "E_n00_to_n10_1",
                "E_south1_to_n10_0", "E_south1_to_n10_1",
                "E_east0_to_n10_0", "E_east0_to_n10_1",
                "E_n11_to_n10_0", "E_n11_to_n10_1"
            ],
            "node_1_1": [
                "E_n01_to_n11_0", "E_n01_to_n11_1",
                "E_n10_to_n11_0", "E_n10_to_n11_1",
                "E_east1_to_n11_0", "E_east1_to_n11_1",
                "E_north1_to_n11_0", "E_north1_to_n11_1"
            ]
        }
        
        if intersection_id not in intersection_lanes_map:
            raise ValueError(f"Unknown intersection ID: {intersection_id}")
            
        self.lanes = intersection_lanes_map[intersection_id]

    def collect_metrics(self):
        """
        Collects aggregated traffic metrics for this intersection.
        
        :return: Dict containing vehicle_count, waiting_time, queue_length, average_speed
        """
        total_vehicles = 0
        total_waiting_time = 0.0
        total_queue_length = 0  # Number of halting vehicles
        weighted_speed_sum = 0.0
        
        for lane_id in self.lanes:
            veh_num = traci.lane.getLastStepVehicleNumber(lane_id)
            total_vehicles += veh_num
            total_waiting_time += traci.lane.getWaitingTime(lane_id)
            total_queue_length += traci.lane.getLastStepHaltingNumber(lane_id)
            
            mean_speed = traci.lane.getLastStepMeanSpeed(lane_id)
            weighted_speed_sum += mean_speed * veh_num

        if total_vehicles > 0:
            avg_speed = weighted_speed_sum / total_vehicles
        else:
            avg_speed = traci.lane.getMaxSpeed(self.lanes[0])

        return {
            "vehicle_count": total_vehicles,
            "waiting_time": round(total_waiting_time, 2),
            "queue_length": total_queue_length,
            "average_speed": round(avg_speed, 2)
        }
