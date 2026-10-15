import argparse
import copy
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from twin.ml.checkpoint import save_checkpoint
from twin.ml.dataset import TaskData, build_task_data, device_frames, load_csv, load_postgres
from twin.ml.early_stopping import EarlyStopping
from twin.ml.evaluate import per_horizon_metrics, persistence_forecast, predict, residual_std, summarize
from twin.ml.models import GRUForecaster
from twin.ml.tasks import TASKS, WindowConfig

log = logging.getLogger("twin.train")


@dataclass
class TrainConfig:
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.1
    learning_rate: float = 2e-3
    weight_decay: float = 1e-4
    batch_size: int = 256
    max_epochs: int = 40
    patience: int = 6
    seed: int = 13


def make_loader(x: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool) -> torch.utils.data.DataLoader:
    dataset = torch.utils.data.TensorDataset(torch.from_numpy(x).float(), torch.from_numpy(y).float())
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def run_epoch(model: nn.Module, loader, loss_fn, optimizer=None) -> float:
    training = optimizer is not None
    model.train(training)
    total, count = 0.0, 0
    with torch.set_grad_enabled(training):
        for inputs, targets in loader:
            loss = loss_fn(model(inputs), targets)
            if training:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total += loss.item() * len(inputs)
            count += len(inputs)
    return total / max(count, 1)


def fit(data: TaskData, config: TrainConfig) -> tuple[GRUForecaster, list[dict]]:
    torch.manual_seed(config.seed)
    task = data.task
    model = GRUForecaster(
        len(task.features), task.target_index, data.window.horizon, config.hidden_size, config.num_layers, config.dropout
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=2)
    loss_fn = nn.SmoothL1Loss(beta=0.5)
    train_loader = make_loader(data.x_train, data.y_train, config.batch_size, shuffle=True)
    val_loader = make_loader(data.x_val, data.y_val, config.batch_size, shuffle=False)
    stopper = EarlyStopping(config.patience)
    best_state = copy.deepcopy(model.state_dict())
    history: list[dict] = []
    for epoch in range(config.max_epochs):
        started = time.perf_counter()
        train_loss = run_epoch(model, train_loader, loss_fn, optimizer)
        val_loss = run_epoch(model, val_loader, loss_fn)
        scheduler.step(val_loss)
        if stopper.update(val_loss, epoch):
            best_state = copy.deepcopy(model.state_dict())
        history.append(
            {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "seconds": time.perf_counter() - started}
        )
        log.info("%s epoch %d train=%.4f val=%.4f", task.name, epoch, train_loss, val_loss)
        if stopper.should_stop:
            break
    model.load_state_dict(best_state)
    return model, history


def evaluate_model(model: GRUForecaster, data: TaskData) -> dict:
    task = data.task
    index = task.target_index
    truth = data.scaler.inverse_targets(data.y_test, index)
    model_pred = data.scaler.inverse_targets(predict(model, data.x_test), index)
    baseline_pred = data.scaler.inverse_targets(persistence_forecast(data.x_test, index, data.window.horizon), index)
    gru = per_horizon_metrics(truth, model_pred, task.targets)
    persistence = per_horizon_metrics(truth, baseline_pred, task.targets)
    return {
        "gru": gru,
        "persistence": persistence,
        "gru_summary": summarize(gru),
        "persistence_summary": summarize(persistence),
        "test_windows": int(len(data.x_test)),
    }


def train_task(data: TaskData, config: TrainConfig, out_dir: Path) -> Path:
    model, history = fit(data, config)
    task = data.task
    index = task.target_index
    val_truth = data.scaler.inverse_targets(data.y_val, index)
    val_pred = data.scaler.inverse_targets(predict(model, data.x_val), index)
    metrics = evaluate_model(model, data)
    metrics["epochs_run"] = len(history)
    metrics["history"] = history
    path = out_dir / f"{task.name}.pt"
    save_checkpoint(
        path,
        model,
        task,
        data.window,
        data.scaler,
        residual_std(val_truth, val_pred),
        metrics,
        {"hidden_size": config.hidden_size, "num_layers": config.num_layers, "dropout": config.dropout},
        version=time.strftime("%Y%m%d%H%M%S"),
    )
    path.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="twin.ml.train", description="Train GRU forecasters")
    parser.add_argument("--task", default="all", choices=["all", *TASKS])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--dsn")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--out", type=Path, default=Path("checkpoints"))
    parser.add_argument("--input-len", type=int, default=WindowConfig.input_len)
    parser.add_argument("--horizon", type=int, default=WindowConfig.horizon)
    parser.add_argument("--step", type=int, default=WindowConfig.step_s)
    parser.add_argument("--stride", type=int, default=WindowConfig.stride)
    parser.add_argument("--epochs", type=int, default=TrainConfig.max_epochs)
    parser.add_argument("--patience", type=int, default=TrainConfig.patience)
    parser.add_argument("--hidden", type=int, default=TrainConfig.hidden_size)
    parser.add_argument("--layers", type=int, default=TrainConfig.num_layers)
    parser.add_argument("--lr", type=float, default=TrainConfig.learning_rate)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = parse_args()
    long_frame = load_csv(args.csv) if args.csv else load_postgres(args.dsn, args.since, args.until)
    window = WindowConfig(args.input_len, args.horizon, args.step, args.stride)
    config = TrainConfig(
        hidden_size=args.hidden,
        num_layers=args.layers,
        learning_rate=args.lr,
        max_epochs=args.epochs,
        patience=args.patience,
        seed=args.seed,
    )
    names = list(TASKS) if args.task == "all" else [args.task]
    for name in names:
        task = TASKS[name]
        data = build_task_data(device_frames(long_frame, task, window.step_s), task, window)
        log.info("%s: %d train / %d val / %d test windows", name, len(data.x_train), len(data.x_val), len(data.x_test))
        path = train_task(data, config, args.out)
        log.info("saved %s", path)
        print(json.dumps({name: asdict(config) | {"checkpoint": str(path)}}))


if __name__ == "__main__":
    main()
