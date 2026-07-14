"""
OrionBot — .exe Paketleyici
main.py'yi PyInstaller ile tek dosyalık, ikonlu, gerçek bir Windows
uygulamasına (.exe) dönüştürür. Çift tıklayınca açılır, taskbar'da
kendi ikonuyla görünür, konsol penceresi açmaz.

Kullanım (Windows'ta, bu dosyanın olduğu klasörde):
    pip install pyinstaller pywebview requests psutil
    python build_exe.py

Çıktı:
    dist/OrionBot.exe   <- tek dosya, çift tıkla çalışır
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

HERE = Path(__file__).parent
BACKEND_DIR = HERE.parent / "backend"


def build():
    print("OrionBot .exe paketleniyor...\n")

    # pywebview gerçekten bu Python ortamında kurulu mu, build'den önce doğrula.
    # PyInstaller farklı bir Python/venv ile çalıştırılırsa webview'i bulamaz
    # ve .exe çalışma zamanında "No module named 'webview'" hatası verir.
    try:
        import webview  # noqa: F401
        print(f"  pywebview bulundu: {webview.__file__}")
    except ImportError:
        print("HATA: pywebview bu Python ortamında kurulu değil.")
        print(f"  Kullanılan Python: {sys.executable}")
        print("  Şunu çalıştır: ")
        print(f"  {sys.executable} -m pip install pywebview")
        sys.exit(1)

    icon_path = HERE / "orion.ico"
    logo_path = HERE / "orion-logo.png"
    html_path = HERE / "index.html"
    main_path = HERE / "main.py"

    if not icon_path.exists():
        print(f"UYARI: {icon_path} bulunamadı, ikonsuz devam ediliyor.")
        icon_arg = []
    else:
        icon_arg = ["--icon", str(icon_path)]

    # Önceki build kalıntıları webview'in eksik göründüğü en sık nedendir —
    # her seferinde tamamen temiz başla.
    for stale in [HERE / "build", HERE / "dist", HERE / "OrionBot.spec"]:
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
        elif stale.exists():
            stale.unlink()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "OrionBot",
        "--onefile",                     # tek .exe dosyası
        "--windowed",                    # konsol penceresi açma
        "--noconfirm",
        "--clean",
        *icon_arg,
        # Backend modüllerini ve statik dosyaları exe içine göm
        "--add-data", f"{html_path}{os.pathsep}.",
        "--add-data", f"{logo_path}{os.pathsep}.",
        "--add-data", f"{icon_path}{os.pathsep}." if icon_path.exists() else f"{html_path}{os.pathsep}.",
        "--paths", str(BACKEND_DIR),
        # pywebview'in kendisi ve Windows'taki edgechromium backend'i
        # PyInstaller'ın statik analizle bulamadığı gizli bağımlılıklar
        # içerir — hepsini açıkça belirtmek gerekiyor.
        "--hidden-import", "webview",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "webview.platforms.winforms",
        "--hidden-import", "clr_loader",
        "--collect-all", "webview",
        # Backend modülleri
        "--hidden-import", "ai_client",
        "--hidden-import", "vault",
        "--hidden-import", "config",
        "--hidden-import", "terminal",
        "--hidden-import", "home_assistant",
        "--hidden-import", "skills",
        "--hidden-import", "conversations",
        "--hidden-import", "orion_engine",
        str(main_path),
    ]

    print("Komut:", " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(HERE))

    if result.returncode == 0:
        exe_path = HERE / "dist" / "OrionBot.exe"
        print(f"\nBaşarılı! .exe dosyası: {exe_path}")
        print("Bu dosyayı istediğin yere kopyalayıp çift tıklayarak çalıştırabilirsin.")
    else:
        print("\nPaketleme başarısız oldu, yukarıdaki hata mesajına bak.")
        sys.exit(1)


if __name__ == "__main__":
    build()
