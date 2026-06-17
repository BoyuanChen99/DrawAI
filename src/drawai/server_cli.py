from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from .device_profiles import DEFAULT_LOCAL_DEVICE, LOCAL_DEVICE_CHOICES, resolve_local_model_devices


DEFAULT_MODEL_PORT = 18080
DEFAULT_API_PORT = 8890
DEFAULT_FRONTEND_PORT = 5174


def server_cli(argv: Sequence[str]) -> int:
    args = list(argv)
    if not args or args[0] in {"-h", "--help"}:
        print(
            "usage: drawai server {model,api,workbench} ...\n\n"
            "Run DrawAI servers.\n\n"
            "commands:\n"
            "  model      Run SAM3, OCR, and RMBG model runtime services.\n"
            "  api        Run the Workbench API and pipeline backend.\n"
            "  workbench  Alias for server api.\n"
        )
        return 0
    command, remaining = args[0], args[1:]
    if command == "model":
        from .local_services import main as local_services_main

        return local_services_main(remaining)
    if command in {"api", "workbench"}:
        return _server_api_cli(remaining)
    print(f"unknown drawai server command: {command}", file=sys.stderr)
    return 2


def workbench_cli(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the DrawAI Workbench frontend or full local workbench stack.")
    parser.add_argument("--api", "--workbench-api", dest="api_url", default="", help="Existing Workbench API URL.")
    parser.add_argument("--host", default=os.environ.get("DRAWAI_WORKBENCH_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DRAWAI_WORKBENCH_FRONTEND_PORT", str(DEFAULT_FRONTEND_PORT))))
    parser.add_argument("--model-api", default="", help="Model runtime base URL used by the self-hosted stack.")
    parser.add_argument(
        "--device",
        choices=LOCAL_DEVICE_CHOICES,
        default=os.environ.get("DRAWAI_DEVICE", DEFAULT_LOCAL_DEVICE),
        help="Local model device profile when the self-hosted stack starts model services.",
    )
    args = parser.parse_args(list(argv))
    if args.api_url:
        return _run_frontend_only(api_url=args.api_url, host=args.host, port=args.port)
    env = os.environ.copy()
    if args.model_api:
        env["DRAWAI_MODEL_API"] = args.model_api.rstrip("/")
    env["DRAWAI_DEVICE"] = args.device
    env["DRAWAI_WORKBENCH_HOST"] = args.host
    env["DRAWAI_WORKBENCH_FRONTEND_PORT"] = str(args.port)
    script = _repo_root() / "scripts" / "start_drawai_workbench_local.sh"
    return subprocess.call([str(script)], cwd=_repo_root(), env=env)


def _server_api_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the DrawAI Workbench API and pipeline backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--workspace", default=os.environ.get("DRAWAI_WORKBENCH_WORKSPACE", ".local/workbench"))
    parser.add_argument("--config", default=os.environ.get("DRAWAI_WORKBENCH_DEFAULT_CONFIG", "configs/drawai/config.yaml"))
    parser.add_argument("--model-api", default=os.environ.get("DRAWAI_MODEL_API", ""), help="Base URL for SAM3, OCR, and RMBG.")
    parser.add_argument("--sam3-api", default=os.environ.get("DRAWAI_SAM3_BASE_URL", ""))
    parser.add_argument("--ocr-api", default=os.environ.get("DRAWAI_OCR_BASE_URL", ""))
    parser.add_argument("--rmbg-api", default=os.environ.get("DRAWAI_RMBG_BASE_URL", ""))
    parser.add_argument(
        "--ocr-timeout-seconds",
        type=float,
        default=_optional_float(os.environ.get("DRAWAI_WORKBENCH_OCR_TIMEOUT_SECONDS")),
        help="Override remote PaddleOCR timeout written into Workbench case configs.",
    )
    parser.add_argument("--no-start-model", action="store_true", help="Do not start a local model runtime subprocess.")
    parser.add_argument("--model-host", default=os.environ.get("DRAWAI_MODEL_HOST", "127.0.0.1"))
    parser.add_argument("--model-port", type=int, default=int(os.environ.get("DRAWAI_MODEL_PORT", str(DEFAULT_MODEL_PORT))))
    parser.add_argument("--runtime-root", default=os.environ.get("DRAWAI_LOCAL_RUNTIME_ROOT", ".local/drawai_runtime"))
    parser.add_argument(
        "--device",
        choices=LOCAL_DEVICE_CHOICES,
        default=os.environ.get("DRAWAI_DEVICE", DEFAULT_LOCAL_DEVICE),
        help="Local model device profile when this API process starts missing model services.",
    )
    parser.add_argument("--sam3-device", default=os.environ.get("DRAWAI_SAM3_DEVICE", ""))
    parser.add_argument("--rmbg-device", default=os.environ.get("DRAWAI_RMBG_DEVICE", ""))
    parser.add_argument("--paddle-device", default=os.environ.get("DRAWAI_PADDLE_DEVICE", ""))
    parser.add_argument("--ocr-det-limit-side-len", type=int, default=int(os.environ.get("DRAWAI_OCR_DET_LIMIT_SIDE_LEN", "1280")))
    args = parser.parse_args(argv)
    devices = resolve_local_model_devices(
        args.device,
        sam3_device=args.sam3_device,
        rmbg_device=args.rmbg_device,
        paddle_device=args.paddle_device,
    )
    args.sam3_device = devices.sam3_device
    args.rmbg_device = devices.rmbg_device
    args.paddle_device = devices.paddle_device

    model_base = (args.model_api or f"http://{args.model_host}:{args.model_port}").rstrip("/")
    sam3_api = (args.sam3_api or model_base).rstrip("/")
    ocr_api = (args.ocr_api or model_base).rstrip("/")
    rmbg_api = (args.rmbg_api or model_base).rstrip("/")
    env = os.environ.copy()
    env["DRAWAI_WORKBENCH_WORKSPACE"] = args.workspace
    env["DRAWAI_WORKBENCH_DEFAULT_CONFIG"] = args.config
    env["DRAWAI_SAM3_BASE_URL"] = sam3_api
    env["DRAWAI_OCR_BASE_URL"] = ocr_api
    env["DRAWAI_RMBG_BASE_URL"] = rmbg_api
    if args.ocr_timeout_seconds is not None:
        if args.ocr_timeout_seconds <= 0:
            raise ValueError("--ocr-timeout-seconds must be positive")
        env["DRAWAI_WORKBENCH_OCR_TIMEOUT_SECONDS"] = str(args.ocr_timeout_seconds)

    model_process = None
    models_to_start = _models_to_start(args)
    if not args.no_start_model and models_to_start:
        model_process = _start_model_server(args, models_to_start)
        time.sleep(0.75)
        if model_process.poll() is not None:
            return int(model_process.returncode or 1)
    try:
        from .workbench.api import create_app, settings_from_env

        os.environ.update(env)
        import uvicorn

        uvicorn.run(create_app(settings_from_env()), host=args.host, port=args.port)
        return 0
    finally:
        if model_process is not None:
            model_process.terminate()
            model_process.wait(timeout=10)


def _models_to_start(args: argparse.Namespace) -> tuple[str, ...]:
    if args.model_api:
        return ()
    selected = []
    if not args.sam3_api:
        selected.append("sam3")
    if not args.ocr_api:
        selected.append("ocr")
    if not args.rmbg_api:
        selected.append("rmbg")
    return tuple(selected)


def _start_model_server(args: argparse.Namespace, models: Sequence[str]) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "drawai.local_services",
        *models,
        "--host",
        args.model_host,
        "--runtime-root",
        args.runtime_root,
        "--sam-port",
        str(args.model_port),
        "--ocr-port",
        str(args.model_port),
        "--sam3-device",
        args.sam3_device,
        "--rmbg-device",
        args.rmbg_device,
        "--paddle-device",
        args.paddle_device,
        "--ocr-det-limit-side-len",
        str(args.ocr_det_limit_side_len),
    ]
    return subprocess.Popen(command, cwd=_repo_root(), text=True)


def _run_frontend_only(*, api_url: str, host: str, port: int) -> int:
    env = os.environ.copy()
    env["DRAWAI_WORKBENCH_API_URL"] = api_url.rstrip("/")
    env["DRAWAI_WORKBENCH_HOST"] = host
    env["DRAWAI_WORKBENCH_FRONTEND_PORT"] = str(port)
    return subprocess.call([str(_script("run_drawai_workbench_frontend.sh"))], cwd=_repo_root(), env=env)


def _ensure_workbench_frontend_deps(app_dir: Path) -> None:
    if (app_dir / "node_modules" / ".bin" / "vite").is_file():
        return
    subprocess.run(_workbench_frontend_install_command(app_dir), cwd=app_dir, check=True)


def _workbench_frontend_install_command(app_dir: Path) -> list[str]:
    if (app_dir / "package-lock.json").is_file():
        return ["npm", "ci"]
    return ["npm", "install"]


def _optional_float(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    return float(raw)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script(name: str) -> Path:
    script = _repo_root() / "scripts" / name
    if not script.exists():
        raise FileNotFoundError(f"DrawAI source-checkout script not found: {script}")
    return script
