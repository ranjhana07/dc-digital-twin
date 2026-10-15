import numpy as np

MAPE_FLOOR = 1e-6


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.abs(y_true - y_pred).mean(axis=0)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.sqrt(((y_true - y_pred) ** 2).mean(axis=0))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return 100.0 * (np.abs(y_true - y_pred) / np.maximum(np.abs(y_true), MAPE_FLOOR)).mean(axis=0)


def per_horizon_metrics(y_true: np.ndarray, y_pred: np.ndarray, targets: tuple[str, ...]) -> dict[str, dict[str, list[float]]]:
    if y_true.shape != y_pred.shape:
        raise ValueError(f"shape mismatch {y_true.shape} vs {y_pred.shape}")
    scores = {"mae": mae(y_true, y_pred), "rmse": rmse(y_true, y_pred), "mape": mape(y_true, y_pred)}
    return {
        target: {name: values[:, index].tolist() for name, values in scores.items()}
        for index, target in enumerate(targets)
    }


def summarize(per_horizon: dict[str, dict[str, list[float]]]) -> dict[str, dict[str, float]]:
    return {
        target: {name: float(np.mean(values)) for name, values in metrics.items()}
        for target, metrics in per_horizon.items()
    }


def persistence_forecast(x_scaled: np.ndarray, target_index: list[int], horizon: int) -> np.ndarray:
    last = x_scaled[:, -1, :][:, target_index]
    return np.repeat(last[:, None, :], horizon, axis=1)


def residual_std(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.maximum((y_true - y_pred).std(axis=0), 1e-6)


def predict(model, x_scaled: np.ndarray, batch_size: int = 512) -> np.ndarray:
    import torch

    model.eval()
    outputs = []
    with torch.no_grad():
        for start in range(0, len(x_scaled), batch_size):
            batch = torch.from_numpy(x_scaled[start : start + batch_size]).float()
            outputs.append(model(batch).numpy())
    return np.concatenate(outputs) if outputs else np.empty((0,))
