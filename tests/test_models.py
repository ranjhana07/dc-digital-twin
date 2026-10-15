import pytest

torch = pytest.importorskip("torch")

from twin.ml.models import GRUForecaster


def test_forward_shape():
    model = GRUForecaster(n_features=5, target_index=[0, 1], horizon=12, hidden_size=16)
    out = model(torch.randn(7, 30, 5))
    assert out.shape == (7, 12, 2)


def test_zero_head_repeats_last_value():
    model = GRUForecaster(n_features=4, target_index=[1, 3], horizon=6, hidden_size=8)
    for parameter in model.head.parameters():
        torch.nn.init.zeros_(parameter)
    window = torch.randn(3, 10, 4)
    out = model(window)
    expected = window[:, -1][:, [1, 3]].unsqueeze(1).expand(-1, 6, -1)
    assert torch.allclose(out, expected)


def test_gradients_flow_to_gru():
    model = GRUForecaster(n_features=3, target_index=[0], horizon=4, hidden_size=8)
    loss = model(torch.randn(2, 10, 3)).pow(2).mean()
    loss.backward()
    assert all(parameter.grad is not None for parameter in model.gru.parameters())
