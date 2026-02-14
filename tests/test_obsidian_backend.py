"""Unit tests for Obsidian backend integration."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from gateway.gateway_config import GatewayConfig, ProviderConfig
from gateway.models import BackendType
from gateway.backends.obsidian_backend import ObsidianBackend


def _backend() -> ObsidianBackend:
    config = ProviderConfig(
        name="obsidian",
        backend_type=BackendType.CLI_EXEC,
        cli_command="/Applications/Obsidian.app/Contents/MacOS/Obsidian",
        cli_args=[],
        timeout_s=30.0,
    )
    return ObsidianBackend(config)


def test_gateway_default_config_contains_obsidian_provider() -> None:
    cfg = GatewayConfig.load()
    provider = cfg.providers.get("obsidian")

    assert provider is not None
    assert provider.backend_type == BackendType.CLI_EXEC
    assert provider.timeout_s == 30.0
    assert provider.cli_command == "/Applications/Obsidian.app/Contents/MacOS/Obsidian"


def test_obsidian_backend_builds_direct_command() -> None:
    backend = _backend()
    cmd = backend._build_command("[OBSIDIAN_CMD] files total")

    assert cmd[0].endswith("Obsidian")
    assert cmd[1:] == ["files", "total"]


def test_obsidian_backend_translates_nl_list_files() -> None:
    backend = _backend()
    cmd = backend._build_command("[OBSIDIAN_NL] 列出所有文件")

    assert cmd[1:] == ["files"]


def test_obsidian_backend_translates_nl_create_note() -> None:
    backend = _backend()
    cmd = backend._build_command("[OBSIDIAN_NL] 创建笔记《工作日志》 内容: 今天完成了阶段一")

    assert cmd[1] == "create"
    assert any(part.startswith("name=") and "工作日志" in part for part in cmd[2:])
    assert any(part.startswith("content=") and "今天完成了阶段一" in part for part in cmd[2:])


def test_obsidian_backend_blocks_gui_command_daily() -> None:
    backend = _backend()

    with pytest.raises(ValueError, match="blocked"):
        backend._build_command("[OBSIDIAN_CMD] daily")


def test_obsidian_backend_rejects_untranslatable_nl() -> None:
    backend = _backend()

    with pytest.raises(ValueError, match="Cannot translate"):
        backend._build_command("[OBSIDIAN_NL] 这个需求你先自由发挥")


def test_obsidian_backend_process_output_success() -> None:
    backend = _backend()
    result = backend._process_output(
        stdout="12",
        stderr="",
        returncode=0,
        latency_ms=10.0,
        input_text="[OBSIDIAN_CMD] files total",
    )

    assert result.success is True
    assert result.response == "12"
    assert result.metadata and result.metadata["exit_code"] == 0


def test_obsidian_backend_process_output_failure() -> None:
    backend = _backend()
    result = backend._process_output(
        stdout="",
        stderr="Command not found",
        returncode=2,
        latency_ms=10.0,
        input_text="[OBSIDIAN_CMD] invalid",
    )

    assert result.success is False
    assert "Obsidian command failed" in (result.error or "")
    assert result.metadata and result.metadata["exit_code"] == 2


@pytest.mark.asyncio
async def test_obsidian_backend_health_check_binary_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _backend()

    monkeypatch.setattr(backend, "_find_cli", lambda: "/tmp/fake-obsidian")
    monkeypatch.setattr("gateway.backends.cli.os.path.isfile", lambda _: True)
    monkeypatch.setattr("gateway.backends.cli.os.access", lambda *_: True)

    assert await backend.health_check() is True


def test_user_gateway_yaml_contains_obsidian_provider_block() -> None:
    yaml_path = Path.home() / ".ccb_config" / "gateway.yaml"
    if not yaml_path.exists():
        pytest.skip("user gateway.yaml not found in this environment")

    content = yaml_path.read_text(encoding="utf-8")
    assert "obsidian:" in content
    assert "/Applications/Obsidian.app/Contents/MacOS/Obsidian" in content
