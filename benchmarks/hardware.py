import json
import os
import platform
import subprocess
from pathlib import Path


def cpu_model() -> str:
    if platform.system() == "Windows":
        command = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"]
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=20).stdout.strip() or platform.processor()
        except (OSError, subprocess.SubprocessError):
            return platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def describe() -> dict:
    info = {
        "cpu": cpu_model(),
        "logical_cores": os.cpu_count(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": platform.python_version(),
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["torch_threads"] = torch.get_num_threads()
    except ImportError:
        info["torch"] = None
    return info


def write(path: Path) -> dict:
    info = describe()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2) + "\n")
    return info


if __name__ == "__main__":
    print(json.dumps(write(Path("results/hardware.json")), indent=2))
