import argparse
import logging
import time

from twin.common.config import get_settings
from twin.common.topology import build_topology
from twin.simulator.engine import Simulation
from twin.simulator.faults import FaultSchedule, random_schedule
from twin.simulator.publisher import MqttPublisher, Pacer

log = logging.getLogger("twin.simulator")


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="twin.simulator", description="Publish simulated data center telemetry over MQTT")
    parser.add_argument("--host", default=settings.mqtt_host)
    parser.add_argument("--port", type=int, default=settings.mqtt_port)
    parser.add_argument("--qos", type=int, choices=(0, 1), default=settings.mqtt_qos)
    parser.add_argument("--sites", type=int, default=settings.topo_sites)
    parser.add_argument("--halls", type=int, default=settings.topo_halls)
    parser.add_argument("--racks", type=int, default=settings.topo_racks_per_hall, help="racks per hall")
    parser.add_argument("--servers", type=int, default=settings.topo_servers_per_rack, help="servers per rack")
    parser.add_argument("--tick", type=float, default=5.0, help="simulated seconds advanced per tick")
    parser.add_argument("--speed", type=float, default=1.0, help="simulated seconds per wall second divided by tick")
    parser.add_argument("--rate", type=float, default=0.0, help="target messages per second, 0 paces by tick")
    parser.add_argument("--duration", type=float, default=0.0, help="stop after this many wall seconds, 0 runs forever")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--faults", type=int, default=4, help="number of faults to schedule")
    parser.add_argument("--fault-horizon-min", type=float, default=240.0)
    parser.add_argument("--fault-lead-min", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = parse_args()
    topology = build_topology(
        sites=args.sites, halls=args.halls, racks_per_hall=args.racks, servers_per_rack=args.servers
    )
    sim_time = time.time()
    schedule = FaultSchedule()
    if args.faults:
        schedule = random_schedule(
            topology,
            seed=args.seed,
            start_s=sim_time + args.fault_lead_min * 60.0,
            horizon_s=args.fault_horizon_min * 60.0,
            count=args.faults,
        )
        for spec in schedule.specs:
            log.info("scheduled %s on %s at +%.0f min", spec.kind, spec.target, (spec.start_s - sim_time) / 60.0)
    simulation = Simulation(topology, schedule, seed=args.seed)
    settings = get_settings()
    publisher = MqttPublisher(args.host, args.port, settings.mqtt_username, settings.mqtt_password, args.qos)
    publisher.connect()
    pacer = Pacer(args.rate, args.tick, args.speed)
    started_wall = time.monotonic()
    report_at = started_wall + 10.0
    try:
        while True:
            tick_started = time.monotonic()
            readings = simulation.step(sim_time, args.tick)
            count = publisher.publish(readings)
            sim_time += args.tick
            pacer.wait(count, tick_started)
            now = time.monotonic()
            if now >= report_at:
                log.info("published %d messages, %.0f msg/s", publisher.published, publisher.published / (now - started_wall))
                report_at = now + 10.0
            if args.duration and now - started_wall >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
