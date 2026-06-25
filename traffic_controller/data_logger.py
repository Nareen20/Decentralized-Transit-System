import os
import csv

class TrafficDataLogger:
    def __init__(self, filename="traffic_data.csv", output_dir="data/raw"):
        """
        Handles saving traffic metrics into CSV files for ML training.
        
        :param filename: Name of the output CSV file
        :param output_dir: Directory where the CSV will be stored (relative to project root)
        """
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_path = os.path.join(self.project_root, output_dir)
        
        # Ensure directories exist
        os.makedirs(self.output_path, exist_ok=True)
        self.filepath = os.path.join(self.output_path, filename)
        
        # Headers matching features and label schema
        self.headers = [
            "step",
            "intersection_id",
            "vehicle_count",
            "queue_length",
            "waiting_time",
            "average_speed",
            "congestion_level"
        ]
        
        # Initialize file and write headers if new
        self._initialize_csv()

    def _initialize_csv(self):
        """Creates the CSV file and writes the header row if it doesn't exist."""
        file_exists = os.path.exists(self.filepath)
        if not file_exists:
            with open(self.filepath, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
            print(f"Created new dataset CSV file at: {self.filepath}")
        else:
            print(f"Appending to existing dataset CSV file at: {self.filepath}")

    def classify_congestion(self, vehicle_count, queue_length, waiting_time, average_speed):
        """
        Classifies the traffic state into low, medium, or high congestion levels.
        
        - 0 (LOW): Free flowing, minimal queues and delays.
        - 2 (HIGH): Heavy gridlock, long queue lines or massive cumulative delay.
        - 1 (MEDIUM): Active traffic, moderate queues/slowing.
        
        :return: Int (0, 1, or 2)
        """
        if queue_length > 8 or waiting_time > 80.0:
            return 2  # HIGH
        elif queue_length <= 2 and waiting_time <= 15.0:
            return 0  # LOW
        else:
            return 1  # MEDIUM

    def log_step(self, step, intersection_id, metrics):
        """
        Logs a single intersection's metrics for a simulation step to the CSV.
        
        :param step: Current simulation step index (int)
        :param intersection_id: The ID of the intersection (string)
        :param metrics: Dict containing count, queue, waiting time, and speed
        """
        count = metrics["vehicle_count"]
        queue = metrics["queue_length"]
        wait = metrics["waiting_time"]
        speed = metrics["average_speed"]
        
        # Calculate ground truth label
        congestion_label = self.classify_congestion(count, queue, wait, speed)
        
        # Append row to CSV
        with open(self.filepath, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                step,
                intersection_id,
                count,
                queue,
                wait,
                speed,
                congestion_label
            ])
