# import argparse
# from traci_handler import TraCISimulator
# from intersection_node import IntersectionNode

# def main():
#     parser = argparse.ArgumentParser(description="Decentralized Transit Priority System - Phase 9")
#     parser.add_argument(
#         "--scenario",
#         type=str,
#         default="normal",
#         choices=["normal", "congestion", "emergency", "bus_priority"],
#         help="Select traffic scenario to run (default: normal)"
#     )
#     parser.add_argument(
#         "--gui",
#         action="store_true",
#         help="Run simulation with SUMO graphical interface (SUMO GUI)"
#     )
#     parser.add_argument(
#         "--steps",
#         type=int,
#         default=100,
#         help="Number of simulation steps to execute (default: 100)"
#     )
#     parser.add_argument(
#         "--save-data",
#         action="store_true",
#         help="Save local intersection traffic metrics to CSV for ML training"
#     )
#     parser.add_argument(
#         "--no-ml",
#         action="store_true",
#         help="Disable local machine learning predictions in the control loop"
#     )
#     args = parser.parse_args()

#     # Define intersections in the 2x2 grid
#     intersections = ["node_0_0", "node_0_1", "node_1_0", "node_1_1"]

#     try:
#         # Initialize the simulator
#         simulator = TraCISimulator(scenario=args.scenario, use_gui=args.gui)
        
#         # Initialize isolated decentralized nodes
#         print("\nInitializing decentralized intersection nodes...")
#         nodes = {}
#         for j_id in intersections:
#             nodes[j_id] = IntersectionNode(
#                 intersection_id=j_id,
#                 save_data=args.save_data,
#                 use_predictor=not args.no_ml
#             )
        
#         # Start the simulation
#         simulator.start()
        
#         print("\n" + "="*95)
#         print(f"Running Decentralized & Cooperative Simulation: Scenario={args.scenario.upper()} | Steps={args.steps}")
#         print("="*95 + "\n")
        
#         for step in range(1, args.steps + 1):
#             # Advance simulation by 1 second in SUMO
#             simulator.step()
            
#             # Print step index
#             print(f"Step {step:03d} | ", end="")
#             junction_summaries = []
            
#             # Phase 1: Local metrics collection and ML predictions
#             for j_id in intersections:
#                 node = nodes[j_id]
#                 node.step_collection(step)
                
#             # Phase 2: Inter-process Python-Rust synchronization (POST updates to local Rust node)
#             for j_id in intersections:
#                 node = nodes[j_id]
#                 node.send_updates_to_rust(step)
                
#             # Phase 3: Cooperative warnings retrieval and signal execution
#             for j_id in intersections:
#                 node = nodes[j_id]
                
#                 # A. GET neighbor warning alerts from local Rust node
#                 warnings = node.fetch_neighbor_warnings()
                
#                 # B. Execute local signal controller utilizing priority, ML, and cooperative rules
#                 node.step_control(warnings)
                
#                 # C. Build console visualization text
#                 metrics = node.metrics
#                 pred_label = node.predicted_congestion if node.predicted_congestion is not None else "N/A"
#                 summary = (f"{j_id}: Veh={metrics['vehicle_count']:2d} | "
#                            f"Q={metrics['queue_length']:2d} | "
#                            f"Wait={metrics['waiting_time']:5.1f}s | "
#                            f"Pred={pred_label}")
#                 junction_summaries.append(summary)
            
#             # Join the junction summaries and print the console dashboard line
#             print("  [  " + "  ]  [  ".join(junction_summaries) + "  ]")
            
#         print("\n" + "="*95)
#         print("Cooperative decentralized simulation execution completed successfully.")
#         print("="*95 + "\n")
        
#     except KeyboardInterrupt:
#         print("\nSimulation interrupted by user.")
#     except Exception as e:
#         print(f"\nAn error occurred: {e}")
#     finally:
#         # Guarantee cleanup and process shutdown
#         try:
#             simulator.close()
#         except Exception:
#             pass

# if __name__ == "__main__":
#     main()




import argparse
from traci_handler import TraCISimulator
from intersection_node import IntersectionNode

def main():
    parser = argparse.ArgumentParser(description="Decentralized Transit Priority System - Phase 9")

    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        choices=["normal", "congestion", "emergency", "bus_priority","mixed"],
        help="Select traffic scenario to run (default: normal)"
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run simulation with SUMO graphical interface (SUMO GUI)"
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=100,
        help="Number of simulation steps to execute (default: 100)"
    )

    parser.add_argument(
        "--save-data",
        action="store_true",
        help="Save local intersection traffic metrics to CSV for ML training"
    )

    parser.add_argument(
        "--no-ml",
        action="store_true",
        help="Disable local machine learning predictions in the control loop"
    )

    args = parser.parse_args()

    print("\n========== Simulation Configuration ==========")
    print(f"Scenario : {args.scenario}")
    print(f"Steps    : {args.steps}")
    print(f"GUI Mode : {args.gui}")
    print("==============================================\n")

    intersections = ["node_0_0", "node_0_1", "node_1_0", "node_1_1"]

    try:
        simulator = TraCISimulator(
            scenario=args.scenario,
            use_gui=args.gui
        )

        print("\nInitializing decentralized intersection nodes...")

        nodes = {}

        for j_id in intersections:
            nodes[j_id] = IntersectionNode(
                intersection_id=j_id,
                save_data=args.save_data,
                use_predictor=not args.no_ml
            )

        simulator.start()

        print("\n" + "=" * 95)
        print(f"Running Decentralized & Cooperative Simulation: Scenario={args.scenario.upper()} | Steps={args.steps}")
        print("=" * 95 + "\n")

        for step in range(1, args.steps + 1):

            simulator.step()

            print(f"Step {step:03d} | ", end="")
            junction_summaries = []

            for j_id in intersections:
                nodes[j_id].step_collection(step)

            for j_id in intersections:
                nodes[j_id].send_updates_to_rust(step)

            for j_id in intersections:

                node = nodes[j_id]

                warnings = node.fetch_neighbor_warnings()

                node.step_control(warnings)

                metrics = node.metrics
                pred_label = (
                    node.predicted_congestion
                    if node.predicted_congestion is not None
                    else "N/A"
                )

                summary = (
                    f"{j_id}: Veh={metrics['vehicle_count']:2d} | "
                    f"Q={metrics['queue_length']:2d} | "
                    f"Wait={metrics['waiting_time']:5.1f}s | "
                    f"Pred={pred_label}"
                )

                junction_summaries.append(summary)

            print("  [  " + "  ]  [  ".join(junction_summaries) + "  ]")

        print("\n" + "=" * 95)
        print("Cooperative decentralized simulation execution completed successfully.")
        print("=" * 95 + "\n")

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        try:
            simulator.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()