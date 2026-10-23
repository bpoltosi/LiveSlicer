"""Install/locate FFmpeg for the Live Slicer pre-MVP and restart after installation."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _find_ffmpeg(requested: str) -> str | None:
    candidate = shutil.which(requested)
    if candidate:
        return str(Path(candidate).resolve())
    path = Path(requested).expanduser()
    if path.is_file():
        return str(path.resolve())

    # winget may add a link that is not visible in the current process PATH yet.
    if platform.system() == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        candidates = [
            local / "Microsoft/WinGet/Links/ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/FFmpeg/bin/ffmpeg.exe"),
        ]
        packages = local / "Microsoft/WinGet/Packages"
        if packages.is_dir():
            candidates.extend(packages.glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"))
            candidates.extend(packages.glob("Gyan.FFmpeg*/*/ffmpeg.exe"))
        for item in candidates:
            if item.is_file():
                return str(item.resolve())
    return None


def _has_libx264(executable: str) -> bool:
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "libx264" in (result.stdout + result.stderr)


def _installer_command() -> list[str] | None:
    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            return [
                "winget", "install", "--id", "Gyan.FFmpeg.Shared", "--exact",
                "--accept-package-agreements", "--accept-source-agreements",
            ]
        return None
    if system == "Darwin":
        if shutil.which("brew"):
            return ["brew", "install", "ffmpeg"]
        return None
    if system == "Linux":
        if shutil.which("apt-get"):
            command = ["apt-get", "install", "-y", "ffmpeg"]
        elif shutil.which("dnf"):
            command = ["dnf", "install", "-y", "ffmpeg"]
        elif shutil.which("pacman"):
            command = ["pacman", "-S", "--noconfirm", "ffmpeg"]
        elif shutil.which("zypper"):
            command = ["zypper", "--non-interactive", "install", "ffmpeg"]
        else:
            return None
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            if not shutil.which("sudo"):
                return None
            command.insert(0, "sudo")
        return command
    return None


def ensure_ffmpeg(requested: str = "ffmpeg") -> str:
    """Return a usable FFmpeg path; install on user consent and restart the app if needed."""
    executable = _find_ffmpeg(requested)
    if executable:
        if _has_libx264(executable):
            return executable
        raise SystemExit(
            f"FFmpeg foi encontrado em: {executable}\n"
            "Mas essa versão não anuncia o encoder libx264, necessário para salvar MP4 H.264.\n"
            "Instale uma versão do FFmpeg que inclua libx264 e execute o Live Slicer novamente."
        )

    print("FFmpeg não foi encontrado. Ele é necessário para exportar vídeos MP4/H.264.")
    command = _installer_command()
    if command is None:
        print("Não encontrei um instalador compatível configurado neste sistema.")
        print("Instale o FFmpeg manualmente e garanta que ele esteja no PATH.")
        print("Guia oficial: https://ffmpeg.org/download.html")
        raise SystemExit(1)

    answer = input("Deseja instalar o FFmpeg automaticamente agora? [s/N] ").strip().lower()
    if answer not in {"s", "sim", "y", "yes"}:
        print("Instalação cancelada. Instale o FFmpeg e abra o Live Slicer novamente.")
        raise SystemExit(1)

    print("Executando instalador:", " ".join(command))
    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        raise SystemExit(f"Não foi possível executar o instalador: {exc}") from exc
    if result.returncode != 0:
        raise SystemExit(
            "A instalação do FFmpeg falhou ou foi cancelada. "
            "Verifique a mensagem do gerenciador de pacotes e tente novamente."
        )

    executable = _find_ffmpeg("ffmpeg")
    if not executable:
        raise SystemExit(
            "A instalação terminou, mas o executável ffmpeg ainda não foi localizado. "
            "Feche e abra um novo terminal ou adicione o FFmpeg ao PATH e tente novamente."
        )
    if not _has_libx264(executable):
        raise SystemExit(
            f"FFmpeg foi instalado em {executable}, mas não oferece libx264. "
            "Instale uma distribuição com suporte a libx264."
        )

    # Start a fresh Python process and pass the discovered executable explicitly.
    # This avoids relying on the old process's PATH after a package manager changes it.
    script = Path(sys.argv[0]).resolve()
    if not script.is_file():
        raise SystemExit(
            f"FFmpeg instalado em {executable}. Reabra o Live Slicer manualmente."
        )
    print("FFmpeg instalado e validado. Reiniciando o Live Slicer...")
    os.execv(
        sys.executable,
        [sys.executable, str(script), *sys.argv[1:], "--ffmpeg", executable],
    )
    raise SystemExit(0)  # pragma: no cover
