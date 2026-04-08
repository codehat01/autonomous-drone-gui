"""
SystemMonitor — QThread that polls CPU, RAM, and ping latency.

Emits stats_updated(cpu_pct, ram_pct, latency_ms) every MONITOR_INTERVAL_MS.
Uses psutil for CPU/RAM; subprocess ping for round-trip latency.
Falls back gracefully if psutil is unavailable.
"""
import subprocess
import platform
import re
import time

from PyQt6.QtCore import QThread, pyqtSignal

from utils.config import DRONE_IP, MONITOR_INTERVAL_MS

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


def _ping_ms(host: str, timeout: int = 1) -> float:
    """
    Returns ping RTT in ms, or -1.0 on failure.
    Works on both Windows and Linux/macOS.
    """
    try:
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), host]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), host]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 1,
        )
        output = result.stdout + result.stderr

        # Extract RTT from ping output
        match = re.search(r"[Tt]ime[=<](\d+\.?\d*)\s*ms", output)
        if match:
            return float(match.group(1))
        # Windows: "Average = Xms"
        match = re.search(r"[Aa]verage\s*=\s*(\d+)\s*ms", output)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return -1.0


class SystemMonitor(QThread):
    """
    Background thread that emits system health stats at ~1Hz.

    Signals:
        stats_updated(cpu_pct: float, ram_pct: float, latency_ms: float)
    """

    stats_updated = pyqtSignal(float, float, float)

    def __init__(self, drone_ip: str = DRONE_IP, parent=None):
        super().__init__(parent)
        self._drone_ip = drone_ip
        self._running = False
        self._interval = MONITOR_INTERVAL_MS / 1000.0

    def run(self) -> None:
        self._running = True
        # psutil CPU needs a first non-blocking call to seed the counter
        if _HAS_PSUTIL:
            psutil.cpu_percent(interval=None)

        while self._running:
            t0 = time.monotonic()

            cpu = self._read_cpu()
            ram = self._read_ram()
            lat = _ping_ms(self._drone_ip)
            if lat < 0:
                lat = 999.0  # show "Poor" in UI when unreachable

            self.stats_updated.emit(cpu, ram, lat)

            elapsed = time.monotonic() - t0
            sleep_s = max(0.0, self._interval - elapsed)
            # Sleep in small slices so stop() is responsive
            deadline = time.monotonic() + sleep_s
            while self._running and time.monotonic() < deadline:
                time.sleep(0.05)

    def stop(self) -> None:
        self._running = False
        self.wait()

    @staticmethod
    def _read_cpu() -> float:
        if _HAS_PSUTIL:
            return psutil.cpu_percent(interval=None)
        return 0.0

    @staticmethod
    def _read_ram() -> float:
        if _HAS_PSUTIL:
            return psutil.virtual_memory().percent
        return 0.0
