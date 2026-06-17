import os
import sys
import argparse

if 'SUMO_HOME' in os.environ:
    sumo_tools_path = os.path.join(os.environ['SUMO_HOME'], 'tools')

    if sumo_tools_path not in sys.path:
        sys.path.append(sumo_tools_path)
else:
    sys.exit(
        "Error: Please declare environment variable 'SUMO_HOME' pointing to your SUMO installation."
    )

import traci


class TraCISimulator:

    def __init__(self, scenario="normal", use_gui=False):

        self.scenario = scenario
        self.use_gui = use_gui

        self.project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        self.cfg_path = os.path.join(
            self.project_root,
            "sumo",
            "network",
            "simulation.sumocfg"
        )

        self.scenario_path = os.path.join(
            self.project_root,
            "sumo",
            "scenarios",
            f"{scenario}.xml"
        )

        if not os.path.exists(self.cfg_path):
            raise FileNotFoundError(
                f"SUMO config file not found at: {self.cfg_path}"
            )

        if not os.path.exists(self.scenario_path):
            raise FileNotFoundError(
                f"Scenario route file not found at: {self.scenario_path}"
            )

    def start(self):

        sumo_binary = "sumo-gui" if self.use_gui else "sumo"

        print("\n========== SUMO Launch ==========")
        print(f"GUI Enabled : {self.use_gui}")
        print(f"SUMO Binary : {sumo_binary}")
        print(f"Config File : {self.cfg_path}")
        print(f"Route File  : {self.scenario_path}")
        print("=================================\n")

        sumo_cmd = [
            sumo_binary,
            "-c",
            self.cfg_path,
            "-r",
            self.scenario_path
        ]

        print(f"Starting {sumo_binary} simulation with scenario '{self.scenario}'...")

        traci.start(sumo_cmd)

        print("TraCI simulation started successfully.")

    def step(self):
        traci.simulationStep()

    def close(self):
        traci.close()
        print("TraCI simulation closed.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scenario",
        type=str,
        default="normal"
    )

    parser.add_argument(
        "--gui",
        action="store_true"
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=20
    )

    args = parser.parse_args()

    try:

        sim = TraCISimulator(
            scenario=args.scenario,
            use_gui=args.gui
        )

        sim.start()

        for s in range(args.steps):

            sim.step()

            print(
                f"Step {s+1}/{args.steps} completed. "
                f"Active vehicles: {traci.simulation.getMinExpectedNumber()}"
            )

        sim.close()

    except Exception as e:
        print(f"Error occurred during simulator run: {e}")