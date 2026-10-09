class EarlyStopping:
    def __init__(self, patience: int = 8, min_delta: float = 1e-4) -> None:
        self.patience = patience
        self.min_delta = min_delta
        self.best = float("inf")
        self.best_epoch = -1
        self.stale = 0

    def update(self, value: float, epoch: int) -> bool:
        if value < self.best - self.min_delta:
            self.best = value
            self.best_epoch = epoch
            self.stale = 0
            return True
        self.stale += 1
        return False

    @property
    def should_stop(self) -> bool:
        return self.stale >= self.patience
