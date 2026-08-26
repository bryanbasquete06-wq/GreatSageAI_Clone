"""
Great Sage AI - System Interaction Module
Manages OS monitoring, performance diagnostics, and system settings.
"""

import psutil
import platform
import time

class SystemModule:
    @staticmethod
    def get_metrics() -> dict:
        """Collects real-time system performance metrics."""
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "OS": f"{platform.system()} {platform.release()}",
            "CPU Load": f"{cpu_usage}%",
            "RAM Usage": f"{ram.percent}% ({ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB)",
            "Disk Usage": f"{disk.percent}% ({disk.free // (1024**3)} GB free)",
            "Active Processes": len(psutil.pids()),
            "Uptime": f"{int(time.time() - psutil.boot_time()) // 3600} hours"
        }

    @staticmethod
    def get_status_report() -> str:
        metrics = SystemModule.get_metrics()
        lines = ["[Report] System Telemetry Diagnostics:"]
        for k, v in metrics.items():
            lines.append(f"  - {k}: {v}")
        return "\n".join(lines)
