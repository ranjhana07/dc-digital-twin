import numpy as np
import pytest

torch = pytest.importorskip("torch")

from twin.ml.checkpoint import LoadedModel
from twin.ml.export import export_onnx, export_torchscript
from twin.ml.models import GRUForecaster
from twin.ml.tasks import TASKS, WindowConfig
from twin.ml.windows import StandardScaler


@pytest.fixture
def loaded():
    task = TASKS["power"]
    model = GRUForecaster(len(task.features), task.target_index, horizon=5, hidden_size=8, num_layers=1)
    scaler = StandardScaler(np.zeros(3), np.ones(3))
    return LoadedModel(model, task, WindowConfig(input_len=12, horizon=5), scaler, np.ones((5, 2)), {}, "t")


def test_torchscript_matches_eager(tmp_path, loaded):
    path = export_torchscript(loaded, tmp_path / "power.ts")
    scripted = torch.jit.load(str(path))
    sample = torch.randn(3, 12, 3)
    assert torch.allclose(scripted(sample), loaded.model(sample), atol=1e-5)
    assert scripted(torch.randn(5, 12, 3)).shape == (5, 5, 2)


def test_onnx_export_writes_file(tmp_path, loaded):
    pytest.importorskip("onnx")
    path = export_onnx(loaded, tmp_path / "power.onnx")
    assert path.stat().st_size > 0
