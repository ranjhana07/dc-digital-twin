import argparse
from pathlib import Path

import torch

from twin.ml.checkpoint import LoadedModel, load_checkpoint


def example_input(loaded: LoadedModel, batch: int = 1) -> torch.Tensor:
    return torch.zeros(batch, loaded.window.input_len, len(loaded.task.features))


def export_torchscript(loaded: LoadedModel, out_path: Path) -> Path:
    traced = torch.jit.trace(loaded.model.eval(), example_input(loaded))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    traced.save(str(out_path))
    return out_path


def export_onnx(loaded: LoadedModel, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        loaded.model.eval(),
        (example_input(loaded),),
        str(out_path),
        input_names=["window"],
        output_names=["forecast"],
        dynamic_axes={"window": {0: "batch"}, "forecast": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="twin.ml.export", description="Export a checkpoint to TorchScript and ONNX")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--formats", nargs="+", choices=("torchscript", "onnx"), default=["torchscript", "onnx"])
    args = parser.parse_args()
    loaded = load_checkpoint(args.checkpoint)
    out_dir = args.out_dir or args.checkpoint.parent
    stem = args.checkpoint.stem
    if "torchscript" in args.formats:
        print(export_torchscript(loaded, out_dir / f"{stem}.ts"))
    if "onnx" in args.formats:
        print(export_onnx(loaded, out_dir / f"{stem}.onnx"))


if __name__ == "__main__":
    main()
