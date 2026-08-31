# -*- coding: utf-8 -*-
"""
Elívea — Real-time System Monitor
==========================================
Monitoramento completo do sistema em tempo real.
"""
from __future__ import annotations

import os
import time
from typing import Optional


class SystemMonitor:
    """Monitor de sistema em tempo real."""

    @classmethod
    def get_cpu_usage(cls) -> dict:
        """Uso de CPU."""
        try:
            import psutil
            percent = psutil.cpu_percent(interval=1)
            freq = psutil.cpu_freq()
            cores = psutil.cpu_count()
            return {
                "percent": percent,
                "frequency_mhz": round(freq.current, 0) if freq else 0,
                "cores": cores,
            }
        except ImportError:
            return cls._cpu_wmi()

    @classmethod
    def _cpu_wmi(cls) -> dict:
        try:
            import wmi
            c = wmi.WMI()
            load = c.Win32_Processor()[0].LoadPercentage
            return {"percent": load or 0, "frequency_mhz": 0, "cores": os.cpu_count() or 0}
        except Exception:
            return {"percent": 0, "frequency_mhz": 0, "cores": os.cpu_count() or 0}

    @classmethod
    def get_memory_info(cls) -> dict:
        """Informacoes de memoria RAM."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "percent": mem.percent,
            }
        except ImportError:
            return cls._mem_wmi()

    @classmethod
    def _mem_wmi(cls) -> dict:
        try:
            import wmi
            c = wmi.WMI()
            os_info = c.Win32_OperatingSystem()[0]
            total = int(os_info.TotalVisibleMemorySize) // (1024**2)
            free = int(os_info.FreePhysicalMemory) // (1024**2)
            used = total - free
            return {
                "total_gb": round(total / 1024, 2),
                "used_gb": round(used / 1024, 2),
                "available_gb": round(free / 1024, 2),
                "percent": round((used / total * 100), 1) if total > 0 else 0,
            }
        except Exception:
            return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0}

    @classmethod
    def get_disk_info(cls) -> list:
        """Informacoes de discos."""
        try:
            import psutil
            disks = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except Exception:
                    continue
            return disks
        except ImportError:
            return []

    @classmethod
    def get_network_info(cls) -> dict:
        """Informacoes de rede."""
        try:
            import psutil
            net = psutil.net_io_counters()
            addrs = psutil.net_if_addrs()
            return {
                "bytes_sent_mb": round(net.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(net.bytes_recv / (1024**2), 2),
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
                "interfaces": list(addrs.keys()),
            }
        except ImportError:
            return {"bytes_sent_mb": 0, "bytes_recv_mb": 0, "interfaces": []}

    @classmethod
    def get_top_processes(cls, limit: int = 5) -> list:
        """Top processos por uso de CPU."""
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    procs.append({
                        "pid": info["pid"],
                        "name": info["name"],
                        "cpu_percent": round(info.get("cpu_percent", 0), 1),
                        "memory_percent": round(info.get("memory_percent", 0), 1),
                    })
                except Exception:
                    continue
            procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
            return procs[:limit]
        except ImportError:
            return []

    @classmethod
    def get_battery_info(cls) -> Optional[dict]:
        """Informacoes da bateria (se houver)."""
        try:
            import psutil
            bat = psutil.sensors_battery()
            if not bat:
                return None
            return {
                "percent": bat.percent,
                "plugged": bat.power_plugged,
                "secs_left": bat.secsleft if bat.secsleft > 0 else None,
            }
        except Exception:
            return None

    @classmethod
    def get_uptime(cls) -> str:
        """Tempo ligado."""
        try:
            import psutil
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = datetime.now() - boot
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}min")
            return " ".join(parts)
        except ImportError:
            return "desconhecido"

    @classmethod
    def full_report(cls) -> str:
        """Relatorio completo do sistema."""
        from datetime import datetime
        cpu = cls.get_cpu_usage()
        mem = cls.get_memory_info()
        disks = cls.get_disk_info()
        net = cls.get_network_info()
        procs = cls.get_top_processes(5)
        bat = cls.get_battery_info()

        lines = ["=== RELATORIO DO SISTEMA ==="]
        lines.append(f"CPU: {cpu['percent']}% ({cpu['cores']} cores)")
        lines.append(f"RAM: {mem['used_gb']}/{mem['total_gb']} GB ({mem['percent']}%)")

        for d in disks:
            lines.append(f"Disco {d['device']}: {d['used_gb']}/{d['total_gb']} GB ({d['percent']}%)")

        lines.append(f"Rede: enviado {net['bytes_sent_mb']} MB, recebido {net['bytes_recv_mb']} MB")

        if bat:
            status = "carregando" if bat["plugged"] else "bateria"
            lines.append(f"Bateria: {bat['percent']}% ({status})")

        lines.append("\nTop 5 processos:")
        for p in procs:
            lines.append(f"  {p['name']}: CPU {p['cpu_percent']}%, RAM {p['memory_percent']}%")

        return "\n".join(lines)

    @classmethod
    def quick_status(cls) -> str:
        """Status rapido para voz."""
        cpu = cls.get_cpu_usage()
        mem = cls.get_memory_info()
        msg = f"CPU em {cpu['percent']} por cento. "
        msg += f"RAM: {mem['used_gb']} de {mem['total_gb']} gigabytes em uso."
        return msg
