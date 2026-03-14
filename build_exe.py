"""Build script for creating a one-file Windows executable."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from app_metadata import APP_NAME, APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent
ENTRYPOINT = PROJECT_ROOT / "main.py"
THIRD_PARTY_FFMPEG_DIR = PROJECT_ROOT / "third_party" / "ffmpeg"
DOWNLOAD_URLS = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
)


def _version_tuple() -> tuple[int, int, int, int]:
        parts = [int(part) for part in APP_VERSION.split(".")]
        while len(parts) < 4:
                parts.append(0)
        return tuple(parts[:4])


def _version_file_contents() -> str:
        major, minor, patch, build = _version_tuple()
        return f"""VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=({major}, {minor}, {patch}, {build}),
        prodvers=({major}, {minor}, {patch}, {build}),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
        ),
    kids=[
        StringFileInfo([
            StringTable(
                '040904B0',
                [StringStruct('CompanyName', 'VideoSplitter'),
                StringStruct('FileDescription', 'Video splitter desktop application'),
                StringStruct('FileVersion', '{APP_VERSION}'),
                StringStruct('InternalName', '{APP_NAME}'),
                StringStruct('OriginalFilename', '{APP_NAME}.exe'),
                StringStruct('ProductName', '{APP_NAME}'),
                StringStruct('ProductVersion', '{APP_VERSION}')])
            ]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])
    ]
)"""


def _ensure_icon() -> Path:
    existing_icons = sorted(PROJECT_ROOT.glob("*.ico"))
    if existing_icons:
        return existing_icons[0]

    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "No se encontro .ico en la carpeta y tampoco se pudo crear uno automatico."
        ) from exc

    icon_path = PROJECT_ROOT / "videosplitter.ico"
    size = 256
    image = Image.new("RGBA", (size, size), (12, 33, 56, 255))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((24, 24, 232, 232), radius=32, fill=(24, 75, 114, 255))
    draw.rounded_rectangle((62, 74, 194, 182), radius=20, fill=(216, 239, 255, 255))
    draw.polygon([(116, 108), (116, 148), (152, 128)], fill=(24, 75, 114, 255))
    draw.rectangle((84, 192, 172, 208), fill=(167, 209, 238, 255))

    image.save(
        icon_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    return icon_path


def _extract_member(zip_file: zipfile.ZipFile, member_name: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zip_file.open(member_name, "r") as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target)


def _pick_member(names: list[str], needle: str) -> str | None:
    normalized = [name.replace("\\", "/") for name in names]
    matches = [name for name in normalized if name.lower().endswith(f"/{needle}")]
    if matches:
        return matches[0]

    exact_matches = [name for name in normalized if name.lower() == needle]
    if exact_matches:
        return exact_matches[0]

    return None


def _download_archive(url: str, destination: Path) -> None:
    print(f"Descargando FFmpeg desde: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VideoSplitterBuilder/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def _extract_ffmpeg_from_archive(archive_path: Path, destination_dir: Path) -> tuple[Path, Path]:
    with zipfile.ZipFile(archive_path, "r") as zip_file:
        names = zip_file.namelist()
        ffmpeg_member = _pick_member(names, "ffmpeg.exe")
        ffprobe_member = _pick_member(names, "ffprobe.exe")

        if not ffmpeg_member or not ffprobe_member:
            raise RuntimeError("El archivo descargado no contiene ffmpeg.exe y ffprobe.exe.")

        ffmpeg_path = destination_dir / "ffmpeg.exe"
        ffprobe_path = destination_dir / "ffprobe.exe"

        _extract_member(zip_file, ffmpeg_member, ffmpeg_path)
        _extract_member(zip_file, ffprobe_member, ffprobe_path)

        return ffmpeg_path.resolve(), ffprobe_path.resolve()


def _ensure_ffmpeg_binaries() -> tuple[Path, Path]:
    THIRD_PARTY_FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = THIRD_PARTY_FFMPEG_DIR / "ffmpeg.exe"
    ffprobe_path = THIRD_PARTY_FFMPEG_DIR / "ffprobe.exe"

    if ffmpeg_path.exists() and ffprobe_path.exists():
        print(f"Usando FFmpeg local: {ffmpeg_path}")
        return ffmpeg_path.resolve(), ffprobe_path.resolve()

    errors: list[str] = []
    download_dir = Path(tempfile.mkdtemp(prefix="videosplitter_ffmpeg_"))
    archive_path = download_dir / "ffmpeg.zip"

    try:
        for url in DOWNLOAD_URLS:
            try:
                _download_archive(url, archive_path)
                extracted = _extract_ffmpeg_from_archive(archive_path, THIRD_PARTY_FFMPEG_DIR)
                print(f"FFmpeg extraido en: {THIRD_PARTY_FFMPEG_DIR}")
                return extracted
            except (urllib.error.URLError, RuntimeError, zipfile.BadZipFile) as exc:
                errors.append(f"{url} -> {exc}")
                if archive_path.exists():
                    archive_path.unlink()
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    details = "\n".join(errors) if errors else "No se pudo descargar FFmpeg."
    raise RuntimeError(f"No fue posible preparar FFmpeg.\n{details}")


def _build(icon_path: Path, ffmpeg_path: Path, ffprobe_path: Path) -> None:
    work_path = Path(tempfile.mkdtemp(prefix="videosplitter_build_"))
    version_file = work_path / "version_info.txt"
    binary_separator = os.pathsep
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(icon_path),
        "--version-file",
        str(version_file),
        "--add-binary",
        f"{ffmpeg_path}{binary_separator}.",
        "--add-binary",
        f"{ffprobe_path}{binary_separator}.",
        "--distpath",
        str(PROJECT_ROOT),
        "--workpath",
        str(work_path),
        "--specpath",
        str(PROJECT_ROOT),
        str(ENTRYPOINT),
    ]
    try:
        version_file.write_text(_version_file_contents(), encoding="utf-8")
        subprocess.run(command, check=True)
    finally:
        shutil.rmtree(work_path, ignore_errors=True)


def main() -> None:
    if not ENTRYPOINT.exists():
        raise FileNotFoundError("No se encontro el archivo main.py para compilar.")

    icon = _ensure_icon()
    ffmpeg_path, ffprobe_path = _ensure_ffmpeg_binaries()

    print(f"Usando icono: {icon.name}")
    print(f"Incluyendo binarios: {ffmpeg_path.name}, {ffprobe_path.name}")
    _build(icon, ffmpeg_path, ffprobe_path)
    print(f"Compilacion completada: {PROJECT_ROOT / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()

