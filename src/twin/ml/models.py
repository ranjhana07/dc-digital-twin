import torch
from torch import nn


class GRUForecaster(nn.Module):
    def __init__(
        self,
        n_features: int,
        target_index: list[int],
        horizon: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.n_features = n_features
        self.horizon = horizon
        self.n_targets = len(target_index)
        self.register_buffer("target_index", torch.tensor(target_index, dtype=torch.long))
        self.gru = nn.GRU(
            n_features,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, horizon * self.n_targets),
        )

    def forward(self, window: torch.Tensor) -> torch.Tensor:
        encoded, _ = self.gru(window)
        delta = self.head(encoded[:, -1]).view(-1, self.horizon, self.n_targets)
        last_targets = window[:, -1].index_select(1, self.target_index)
        return delta + last_targets.unsqueeze(1)
