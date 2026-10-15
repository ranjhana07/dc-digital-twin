import argparse
import logging
import signal
import threading
import time
from pathlib import Path

from twin.common.config import get_settings
from twin.ml.inference import InferenceService, bundle_from_checkpoint
from twin.ml.store import PostgresForecastStore
from twin.ml.tasks import TASKS

log = logging.getLogger("twin.inference")


def load_bundles(checkpoint_dir: Path) -> dict:
    bundles = {}
    for name in TASKS:
        path = checkpoint_dir / f"{name}.pt"
        if path.exists():
            bundles[name] = bundle_from_checkpoint(path)
            log.info("loaded %s checkpoint %s", name, bundles[name].version)
    return bundles


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="twin.ml", description="Run the real-time inference loop")
    parser.add_argument("--checkpoints", type=Path, default=Path(settings.checkpoint_dir))
    parser.add_argument("--interval", type=float, default=settings.inference_interval_s)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    store = PostgresForecastStore(settings.psycopg_dsn)
    bundles: dict = {}
    while not stop.is_set():
        if not bundles:
            bundles = load_bundles(args.checkpoints)
            if not bundles:
                log.warning("no checkpoints in %s, waiting", args.checkpoints)
        if bundles:
            started = time.perf_counter()
            try:
                summary = InferenceService(bundles, store).run_once()
                log.info("cycle done in %.2fs: %s", time.perf_counter() - started, summary)
            except Exception:
                log.exception("inference cycle failed")
        if args.once:
            break
        stop.wait(args.interval)


if __name__ == "__main__":
    main()
