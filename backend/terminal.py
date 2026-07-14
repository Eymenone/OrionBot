"""
OrionBot Backend — Terminal Runner
Sistem komutlarını çalıştırır, çıktıyı döndürür.

Kullanım:
    runner = Runner()
    out, err = runner.run("dir")
"""
import subprocess
from typing import Tuple


class Runner:
    TIMEOUT = 20  # saniye

    def run(self, cmd: str) -> Tuple[str, str]:
        """
        Komutu çalıştırır. (stdout, stderr) tuple döndürür.
        Timeout'ta stderr'e açıklayıcı mesaj koyar.
        """
        try:
            r = subprocess.run(
                cmd, shell=True,
                capture_output=True, text=True,
                timeout=self.TIMEOUT,
                encoding="utf-8", errors="replace",
            )
            return r.stdout.strip()[:2000], r.stderr.strip()[:500]
        except subprocess.TimeoutExpired:
            return "", f"Zaman aşımı ({self.TIMEOUT} saniye)"
        except Exception as e:
            return "", str(e)
