"""Install/locate FFmpeg for the Live Slicer pre-MVP and restart after installation."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
import sys
from pathlib import Path
from typing import Optional


def _find_ffmpeg(requested: str) -> Optional[str]:
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
            local / "LiveSlicer/ffmpeg/bin/ffmpeg.exe",
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


def _installer_command() -> Optional[list[str]]:
    system = platform.system()
    if system == "Windows":
        winget = shutil.which("winget")
        if not winget:
            local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            candidate = local / "Microsoft/WindowsApps/winget.exe"
            if candidate.is_file():
                winget = str(candidate)
        if winget:
            return [
                winget, "install", "--id", "Gyan.FFmpeg.Shared", "--exact",
                "--accept-package-agreements", "--accept-source-agreements",
            ]
        return ["__download_ffmpeg_zip__"]
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



def _install_windows_ffmpeg_zip() -> str:
    """Install an FFmpeg essentials build under the current user's LocalAppData."""
    if platform.system() != "Windows":
        raise RuntimeError("This fallback is only available on Windows.")
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    install_dir = local / "LiveSlicer" / "ffmpeg"
    install_dir.mkdir(parents=True, exist_ok=True)
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    with tempfile.TemporaryDirectory(prefix="liveslicer-ffmpeg-") as temp_dir:
        archive = Path(temp_dir) / "ffmpeg.zip"
        request = urllib.request.Request(url, headers={"User-Agent": "LiveSlicer-pre-MVP"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response, archive.open("wb") as target:
                shutil.copyfileobj(response, target)
        except Exception as exc:
            raise RuntimeError(f"FFmpeg download failed ({url}): {exc}") from exc

        try:
            with zipfile.ZipFile(archive) as bundle:
                root = Path(temp_dir).resolve()
                for member in bundle.infolist():
                    destination = (root / member.filename).resolve()
                    if os.path.commonpath((str(root), str(destination))) != str(root):
                        raise RuntimeError("The FFmpeg archive contains an invalid extraction path.")
                bundle.extractall(root)
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeError(f"Could not extract downloaded FFmpeg package: {exc}") from exc

        candidates = list(Path(temp_dir).glob("**/bin/ffmpeg.exe"))
        if not candidates:
            raise RuntimeError("Downloaded package does not contain bin/ffmpeg.exe.")
        destination_bin = install_dir / "bin"
        if destination_bin.exists():
            shutil.rmtree(destination_bin)
        shutil.copytree(candidates[0].parent, destination_bin)

    executable = str((install_dir / "bin" / "ffmpeg.exe").resolve())
    if not Path(executable).is_file():
        raise RuntimeError("FFmpeg installation finished but ffmpeg.exe was not found.")
    return executable


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

    try:
        if command == ["__download_ffmpeg_zip__"]:
            print("winget não está disponível. Baixando FFmpeg para o perfil deste usuário...")
            executable = _install_windows_ffmpeg_zip()
        else:
            print("Executando instalador:", " ".join(command))
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                raise SystemExit(
                    "A instalação do FFmpeg falhou ou foi cancelada. "
                    "Verifique a mensagem do gerenciador de pacotes e tente novamente."
                )
            executable = _find_ffmpeg("ffmpeg")
    except (OSError, RuntimeError) as exc:
        raise SystemExit(f"Não foi possível instalar o FFmpeg: {exc}") from exc

    if not executable:
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
