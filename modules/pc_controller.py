# -*- coding: utf-8 -*-
"""
Elívea — Universal PC Controller
=========================================
Controle TOTAL do PC: apps, jogos, mídia, janelas, tudo.

  - Descobre TODOS os apps instalados (Start Menu, Registry, PATH)
  - Lança jogos (Steam, Epic, Xbox, GGLauncher, games descobertos)
  - Controla mídia (play/pause/next/prev em qualquer app)
  - Gerencia janelas (maximizar, minimizar, mover, redimensionar, snap)
  - Controle de volume por-app
  - Screen recording, brightness, power actions
  - Tudo via voz ou texto — "abre o google", "joga valorant", "próxima música"

Uso:
    from modules.pc_controller import PCController
    PCController.open_app("google")        # abre Chrome com Google
    PCController.launch_game("valorant")   # lança Valorant
    PCController.media_play_pause()        # play/pause mídia
    PCController.maximize_window()         # maximiza janela ativa
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import re
import subprocess
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

logger = __import__("logging").getLogger("elvea.pc_controller")


# =========================================================================
# 1. App Discovery — finds ALL installed apps on the PC
# =========================================================================

@dataclass
class DiscoveredApp:
    """An app discovered on the system."""
    name: str
    display_name: str = ""
    command: str = ""          # executable path or command
    args: List[str] = field(default_factory=list)
    source: str = ""           # "start_menu", "registry", "path", "steam", "epic", "winget"
    icon_path: str = ""
    category: str = "general"  # "browser", "media", "dev", "game", "productivity", "general"


# Well-known apps with smart aliases
_SMART_ALIASES: Dict[str, str] = {
    # Browsers
    "google": "chrome",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "mozilla": "firefox",
    "edge": "edge",
    "microsoft edge": "edge",
    "brave": "brave",
    # Dev
    "vscode": "code",
    "visual studio code": "code",
    "visual studio": "devenv",
    "intellij": "idea",
    "pycharm": "pycharm64",
    "sublime": "sublime_text",
    "vim": "vim",
    "nvim": "nvim",
    "notepad++": "notepad++",
    "git bash": "git-bash",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    # Media
    "spotify": "spotify",
    "vlc": "vlc",
    "foobar": "foobar2000",
    "music": "msmusic",
    "groove": "msmusic",
    "youtube": "https://www.youtube.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    # Productivity
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "teams": "teams",
    "slack": "slack",
    "discord": "discord",
    "zoom": "zoom",
    "notepad": "notepad",
    "paint": "mspaint",
    "calculator": "calc",
    "paint 3d": "mspaint",
    "snipping tool": "SnippingTool",
    "snip": "SnippingTool",
    # Gaming
    "steam": "steam",
    "epic": "com.epicgames.launcher",
    "epic games": "com.epicgames.launcher",
    "epic games launcher": "com.epicgames.launcher",
    "xbox": "xbox",
    "xbox app": "xbox",
    "gog": "gog galaxy",
    "battle.net": "battle.net",
    "blizzard": "battle.net",
    "origin": "origin",
    "ea": "origin",
    "ubisoft": "upc",
    "riot": "riot client",
    "valorant": "valorant",
    "league": "league of legends",
    "league of legends": "league of legends",
    "fortnite": "fortnite",
    "minecraft": "minecraft",
    "roblox": "roblox",
    # System
    "explorer": "explorer",
    "file manager": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "control panel": "control",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "registry": "regedit",
    "registry editor": "regedit",
    "services": "services.msc",
    "system info": "msinfo32",
    "resource monitor": "resmon",
    "performance": "resmon",
    " Firewall": "wf.msc",
    "event viewer": "eventvwr",
    "cmd": "cmd",
    "prompt": "cmd",
    "command prompt": "cmd",
    " powershell": "powershell",
    "windows powershell": "powershell",
    "terminal": "wt",
    # Image/Video
    "photos": "ms-photos:",
    "photo viewer": "ms-photos:",
    "camera": "microsoft.windows.camera:",
    "screen recorder": "ms-screenclip:",
    "snip & sketch": "ms-screenclip:",
}

# Known game executables (for when we find them on disk)
_KNOWN_GAME_EXES: Dict[str, List[str]] = {
    "valorant": ["VALORANT.exe", "RiotClientServices.exe"],
    "league of legends": ["League of Legends.exe"],
    "fortnite": ["FortniteClient-Win64-Shipping.exe"],
    "minecraft": ["MinecraftLauncher.exe", "Minecraft.exe"],
    "cs2": ["cs2.exe", "csgo.exe"],
    "counter-strike": ["cs2.exe", "csgo.exe"],
    "gta v": ["GTA5.exe", "GTAV.exe"],
    "gta 5": ["GTA5.exe", "GTAV.exe"],
    "cyberpunk": ["Cyberpunk2077.exe"],
    "elden ring": ["eldenring.exe"],
    "hogwarts": ["HogwartsLegacy.exe"],
    "roblox": ["RobloxPlayerBeta.exe"],
    "apex legends": ["r5apex.exe"],
    "overwatch": ["Overwatch.exe"],
    "genshin": ["GenshinImpact.exe"],
    "genshin impact": ["GenshinImpact.exe"],
    "genshin impact.exe": ["GenshinImpact.exe"],
    "starfield": ["Starfield.exe"],
    "baldur's gate": ["bg3.exe"],
    "baldurs gate": ["bg3.exe"],
    "diablo": ["Diablo IV.exe"],
    "diablo 4": ["Diablo IV.exe"],
    "warzone": ["ModernWarfare.exe"],
    "call of duty": ["ModernWarfare.exe"],
    "rainbow six": ["RainbowSix.exe"],
    "assassin": ["ACValhalla.exe"],
    "fifa": ["FIFA.exe"],
    "ea fc": ["FC25.exe"],
    "forza": ["ForzaHorizon5.exe"],
    "forza horizon": ["ForzaHorizon5.exe"],
    "halo": ["haloinfinite.exe"],
    "doom": ["DOOMEternalx64vk.exe"],
    "red dead": ["RDR2.exe"],
    "red dead redemption": ["RDR2.exe"],
    "the witcher": ["witcher3.exe"],
    "witcher": ["witcher3.exe"],
    "metro": ["metroexodus.exe"],
    "resident evil": ["re4.exe"],
    "silent hill": ["sh2.exe"],
}

# Common game install paths
_GAME_SEARCH_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common",
    r"C:\Program Files\Steam\steamapps\common",
    r"D:\Steam\steamapps\common",
    r"E:\Steam\steamapps\common",
    r"F:\Steam\steamapps\common",
    r"C:\Program Files\Epic Games",
    r"D:\Epic Games",
    r"E:\Epic Games",
    r"C:\Program Files\EA Games",
    r"C:\Program Files (x86)\Origin Games",
    r"C:\Program Files\Microsoft Games",
    r"C:\Program Files\WindowsApps",
    r"C:\Riot Games",
    r"C:\Program Files\Riot Games",
    r"D:\Riot Games",
    r"C:\Program Files\Roblox",
    r"C:\Users\{}\AppData\Local\Roblox".format(os.getenv("USERNAME", "")),
]

# Common app install paths
_APP_SEARCH_PATHS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"D:\Program Files",
    r"E:\Program Files",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    os.path.expandvars(r"%LOCALAPPDATA%"),
]


class AppDiscovery:
    """Discovers all installed apps on the PC."""

    _cache: Dict[str, DiscoveredApp] = {}
    _cache_time: float = 0
    _CACHE_TTL = 300  # 5 minutes

    @classmethod
    def discover_all(cls, force: bool = False) -> Dict[str, DiscoveredApp]:
        """Discover all installed apps. Results cached for 5 minutes."""
        now = time.time()
        if not force and cls._cache and (now - cls._cache_time < cls._CACHE_TTL):
            return cls._cache

        apps: Dict[str, DiscoveredApp] = {}

        # 1) Start Menu shortcuts (most comprehensive)
        cls._scan_start_menu(apps)

        # 2) Registry (installed programs)
        cls._scan_registry(apps)

        # 3) PATH environment
        cls._scan_path(apps)

        # 4) Known game locations
        cls._scan_game_dirs(apps)

        # 5) Winget installed packages
        cls._scan_winget(apps)

        cls._cache = apps
        cls._cache_time = now
        logger.info(f"AppDiscovery: found {len(apps)} apps")
        return apps

    @classmethod
    def find_app(cls, query: str) -> Optional[DiscoveredApp]:
        """Find an app by fuzzy name match."""
        q = query.lower().strip()

        # 1) Check smart aliases first
        alias_target = _SMART_ALIASES.get(q)
        if alias_target:
            apps = cls.discover_all()
            # Try exact match in discovered apps
            if alias_target in apps:
                return apps[alias_target]
            # For URLs, return a special app
            if alias_target.startswith("http"):
                return DiscoveredApp(
                    name=q, display_name=query,
                    command=alias_target, source="alias", category="web"
                )
            # For executable names, create a synthetic app
            return DiscoveredApp(
                name=alias_target, display_name=query,
                command=alias_target, source="alias", category="general"
            )

        # 2) Exact match in discovered apps
        apps = cls.discover_all()
        if q in apps:
            return apps[q]

        # 3) Fuzzy match — check display_name
        for key, app in apps.items():
            if q in app.display_name.lower() or q in app.name.lower():
                return app

        # 4) Partial match
        for key, app in apps.items():
            if q in key or key in q:
                return app

        return None

    @classmethod
    def _scan_start_menu(cls, apps: Dict[str, DiscoveredApp]):
        """Scan Start Menu for .lnk shortcuts."""
        start_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        ]
        for start_dir in start_dirs:
            p = Path(start_dir)
            if not p.exists():
                continue
            for lnk in p.rglob("*.lnk"):
                try:
                    # Get the target of the shortcut
                    name = lnk.stem.lower()
                    # Skip uninstallers
                    if "uninstall" in name or "remove" in name:
                        continue
                    app = DiscoveredApp(
                        name=name,
                        display_name=lnk.stem,
                        command=str(lnk),
                        source="start_menu",
                    )
                    apps[name] = app
                except Exception:
                    pass

    @classmethod
    def _scan_registry(cls, apps: Dict[str, DiscoveredApp]):
        """Scan Windows Registry for installed programs."""
        try:
            import winreg
            hives = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, key_path in hives:
                try:
                    key = winreg.OpenKey(hive, key_path)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                install_loc = ""
                                try:
                                    install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                except Exception:
                                    pass
                                if display_name and len(display_name) > 1:
                                    name_key = display_name.lower().replace(" ", "_")[:50]
                                    if name_key not in apps:
                                        apps[name_key] = DiscoveredApp(
                                            name=name_key,
                                            display_name=display_name,
                                            command=install_loc or "",
                                            source="registry",
                                        )
                            except Exception:
                                pass
                            winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass
        except ImportError:
            pass

    @classmethod
    def _scan_path(cls, apps: Dict[str, DiscoveredApp]):
        """Scan PATH for executables."""
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for d in path_dirs[:20]:  # limit to first 20 PATH dirs
            p = Path(d)
            if not p.exists():
                continue
            for exe in p.glob("*.exe"):
                name = exe.stem.lower()
                if name not in apps and len(name) > 1:
                    apps[name] = DiscoveredApp(
                        name=name,
                        display_name=exe.stem,
                        command=str(exe),
                        source="path",
                    )

    @classmethod
    def _scan_game_dirs(cls, apps: Dict[str, DiscoveredApp]):
        """Scan common game directories."""
        for game_dir in _GAME_SEARCH_PATHS:
            p = Path(game_dir)
            if not p.exists():
                continue
            try:
                folders = list(p.iterdir())
            except (PermissionError, OSError):
                continue
            for game_folder in folders:
                if not game_folder.is_dir():
                    continue
                # Look for .exe files in the game folder
                for exe in game_folder.glob("*.exe"):
                    name = exe.stem.lower()
                    if name not in apps:
                        apps[name] = DiscoveredApp(
                            name=name,
                            display_name=game_folder.name,
                            command=str(exe),
                            source="game_dir",
                            category="game",
                        )

    @classmethod
    def _scan_winget(cls, apps: Dict[str, DiscoveredApp]):
        """Scan winget for installed packages."""
        try:
            result = subprocess.run(
                ["winget", "list", "--accept-source-agreements"],
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in result.stdout.splitlines():
                # winget output: Name    Id    Version    Available
                parts = line.split()
                if len(parts) >= 2 and not line.startswith("-"):
                    name = parts[0].lower()
                    if name and len(name) > 1 and name not in apps:
                        apps[name] = DiscoveredApp(
                            name=name,
                            display_name=parts[0],
                            source="winget",
                        )
        except Exception:
            pass


# =========================================================================
# 2. Game Launcher
# =========================================================================

class GameLauncher:
    """Launches games from any platform (Steam, Epic, Riot, etc.)."""

    @classmethod
    def launch(cls, game_name: str) -> str:
        """Launch a game by name. Tries multiple strategies."""
        q = game_name.lower().strip()

        # 1) Try direct app discovery
        app = AppDiscovery.find_app(q)
        if app and app.command:
            return cls._launch_app(app)

        # 2) Try Steam launch
        result = cls._launch_steam_game(q)
        if result:
            return result

        # 3) Try Epic Games launch
        result = cls._launch_epic_game(q)
        if result:
            return result

        # 4) Try known game executables
        result = cls._launch_known_game(q)
        if result:
            return result

        # 5) Try winget (install + launch)
        return f"Jogo '{game_name}' não encontrado. Posso tentar instalar via winget ou buscar no Steam."

    @classmethod
    def _launch_app(cls, app: DiscoveredApp) -> str:
        """Launch a discovered app."""
        try:
            if app.command.startswith("http"):
                webbrowser.open(app.command)
                return f"Abrindo {app.display_name}..."
            elif app.command.endswith(".lnk"):
                os.startfile(app.command)
                return f"Abrindo {app.display_name}..."
            elif os.path.isfile(app.command):
                subprocess.Popen([app.command], cwd=str(Path(app.command).parent))
                return f"Abrindo {app.display_name}..."
            else:
                os.system(f'start "" "{app.command}"')
                return f"Abrindo {app.display_name}..."
        except Exception as e:
            return f"Erro ao abrir {app.display_name}: {e}"

    @classmethod
    def _launch_steam_game(cls, game_name: str) -> Optional[str]:
        """Try to launch a game via Steam."""
        steam_paths = [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
            r"D:\Steam\steam.exe",
        ]
        steam_exe = None
        for p in steam_paths:
            if os.path.exists(p):
                steam_exe = p
                break
        if not steam_exe:
            return None

        # Steam app IDs for popular games (partial list)
        steam_apps = {
            "counter-strike": "730", "cs2": "730", "csgo": "730",
            "dota": "570", "dota 2": "570",
            "gta v": "271590", "gta 5": "271590", "grand theft auto": "271590",
            "pubg": "578080", "playerunknown": "578080",
            "apex legends": "1172470", "apex": "1172470",
            "elden ring": "1245620",
            "cyberpunk": "1091500", "cyberpunk 2077": "1091500",
            "hogwarts": "990080", "hogwarts legacy": "990080",
            "red dead": "1174180", "red dead redemption": "1174180", "rdr2": "1174180",
            "the witcher": "292030", "witcher 3": "292030",
            "skyrim": "489830", "elder scrolls": "489830",
            "fallout": "377160", "fallout 4": "377160",
            "baldur": "1086940", "baldurs gate": "1086940",
            "metro": "412020", "metro exodus": "412020",
            "resident evil": "1541780",
            "frostpunk": "324304",
            "cities skylines": "255710",
            "terraria": "105600",
            "stardew valley": "413150",
            "hollow knight": "367520",
            "cuphead": "268910",
            "doom": "379720", "doom eternal": "782330",
            "disco elysium": "632470",
            "outer wilds": "753640",
            "hades": "1145360",
            "valheim": "892970",
            "subnautica": "264710",
            "no man's sky": "275850",
            "factorio": "427520",
            "rimworld": "294100",
            "prison architect": "233450",
            "kerbal": "224460", "kerbal space": "224460",
            "ARK": "346110", "ark survival": "346110",
            "rust": "252490",
            "palworld": "1623732",
            "lethal company": "1966720",
            "content warning": "2243720",
            "helldivers": "553850", "helldivers 2": "553850",
            "manor lords": "1363430",
            "satisfactory": "526800",
            "deep rock": "548430", "deep rock galactic": "548430",
            "liar's bar": "2959410",
        }

        # Try exact Steam app ID
        app_id = steam_apps.get(q)
        if app_id:
            os.system(f'start "" "{steam_exe}" -applaunch {app_id}')
            return f"Abrindo {game_name} via Steam (ID: {app_id})..."

        # Try fuzzy match
        for key, aid in steam_apps.items():
            if key in q or q in key:
                os.system(f'start "" "{steam_exe}" -applaunch {aid}')
                return f"Abrindo {game_name} via Steam (ID: {aid})..."

        # Try Steam search (open Steam to the game's store page)
        os.system(f'start "" "{steam_exe}"')
        return f"Abrindo Steam — busque '{game_name}' na loja."

    @classmethod
    def _launch_epic_game(cls, game_name: str) -> Optional[str]:
        """Try to launch a game via Epic Games Launcher."""
        epic_paths = [
            r"C:\Program Files\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\EpicGamesLauncher\Portal\Binaries\Win64\EpicGamesLauncher.exe"),
        ]
        for p in epic_paths:
            if os.path.exists(p):
                os.system(f'start "" "{p}"')
                return f"Abrindo Epic Games Launcher — busque '{game_name}' lá."
        return None

    @classmethod
    def _launch_known_game(cls, game_name: str) -> Optional[str]:
        """Try to find and launch a known game executable."""
        exe_names = _KNOWN_GAME_EXES.get(game_name, [])
        if not exe_names:
            # Fuzzy search
            for key, exes in _KNOWN_GAME_EXES.items():
                if key in game_name or game_name in key:
                    exe_names = exes
                    break

        if not exe_names:
            return None

        # Search game directories
        for search_dir in _GAME_SEARCH_PATHS:
            p = Path(search_dir)
            if not p.exists():
                continue
            for exe_name in exe_names:
                for found in p.rglob(exe_name):
                    try:
                        subprocess.Popen([str(found)], cwd=str(found.parent))
                        return f"Iniciando {game_name} ({found.name})..."
                    except Exception:
                        pass

        return None


# =========================================================================
# 3. Media Controller
# =========================================================================

class MediaController:
    """Controls media playback in any app (Spotify, YouTube, VLC, etc.)."""

    # Virtual key codes for media keys
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_MEDIA_NEXT = 0xB0
    VK_MEDIA_PREV = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_VOLUME_UP = 0xAF
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_MUTE = 0xAD

    @classmethod
    def play_pause(cls) -> str:
        """Toggle play/pause in any media app."""
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
        return "Play/Pause"

    @classmethod
    def next_track(cls) -> str:
        """Skip to next track."""
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_NEXT, 0, 0, 0)
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_NEXT, 0, 2, 0)
        return "Próxima faixa"

    @classmethod
    def prev_track(cls) -> str:
        """Go to previous track."""
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_PREV, 0, 0, 0)
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_PREV, 0, 2, 0)
        return "Faixa anterior"

    @classmethod
    def stop(cls) -> str:
        """Stop media playback."""
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_STOP, 0, 0, 0)
        ctypes.windll.user32.keybd_event(cls.VK_MEDIA_STOP, 0, 2, 0)
        return "Reprodução parada"

    @classmethod
    def volume_up(cls, steps: int = 5) -> str:
        """Increase system volume."""
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(cls.VK_VOLUME_UP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(cls.VK_VOLUME_UP, 0, 2, 0)
        return f"Volume +{steps}"

    @classmethod
    def volume_down(cls, steps: int = 5) -> str:
        """Decrease system volume."""
        for _ in range(steps):
            ctypes.windll.user32.keybd_event(cls.VK_VOLUME_DOWN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(cls.VK_VOLUME_DOWN, 0, 2, 0)
        return f"Volume -{steps}"

    @classmethod
    def mute(cls) -> str:
        """Toggle mute."""
        ctypes.windll.user32.keybd_event(cls.VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(cls.VK_VOLUME_MUTE, 0, 2, 0)
        return "Mudo"

    @classmethod
    def set_volume(cls, level: int) -> str:
        """Set system volume to specific level (0-100)."""
        # Use PowerShell to set volume precisely
        level = max(0, min(100, level))
        # Calculate number of up/down presses from current 50%
        target = int(level / 2)  # Windows volume range is 0-50
        # First mute and unmute to reset, then set
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = iface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Volume definido para {level}%"
        except ImportError:
            # Fallback: use WScript.Shell SendKeys
            # First go to 0%, then press up to desired level
            os.system(f'powershell -c "$obj = New-Object -ComObject WScript.Shell; '
                      f'1..50 | % {{$obj.SendKeys([char]174)}}; '  # volume all the way down
                      f'1..{target} | % {{$obj.SendKeys([char]175)}}"'  # volume up to target
                      )
            return f"Volume ajustado para ~{level}%"

    @classmethod
    def play_youtube(cls, query: str) -> str:
        """Open YouTube and play a video."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        return f"Abrindo YouTube: {query}"

    @classmethod
    def play_spotify(cls, query: str = "") -> str:
        """Open Spotify (and search if query provided)."""
        app = AppDiscovery.find_app("spotify")
        if app:
            try:
                if app.command.endswith(".lnk"):
                    os.startfile(app.command)
                else:
                    os.system(f'start spotify:')
                return f"Abrindo Spotify{' — ' + query if query else ''}..."
            except Exception:
                pass
        webbrowser.open("https://open.spotify.com")
        return "Abrindo Spotify no navegador..."


# =========================================================================
# 4. Window Manager
# =========================================================================

class WindowManager:
    """Controls window state: maximize, minimize, move, resize, snap."""

    SW_MAXIMIZE = 3
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    SW_SHOW = 5
    SW_HIDE = 0

    HWND_TOP = 0
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040

    user32 = ctypes.windll.user32

    @classmethod
    def _get_foreground(cls) -> int:
        """Get handle of foreground window."""
        return cls.user32.GetForegroundWindow()

    @classmethod
    def maximize(cls) -> str:
        """Maximize the active window."""
        hwnd = cls._get_foreground()
        cls.user32.ShowWindow(hwnd, cls.SW_MAXIMIZE)
        return "Janela maximizada"

    @classmethod
    def minimize(cls) -> str:
        """Minimize the active window."""
        hwnd = cls._get_foreground()
        cls.user32.ShowWindow(hwnd, cls.SW_MINIMIZE)
        return "Janela minimizada"

    @classmethod
    def restore(cls) -> str:
        """Restore the active window."""
        hwnd = cls._get_foreground()
        cls.user32.ShowWindow(hwnd, cls.SW_RESTORE)
        return "Janela restaurada"

    @classmethod
    def fullscreen(cls) -> str:
        """Toggle fullscreen for the active window."""
        hwnd = cls._get_foreground()
        cls.user32.ShowWindow(hwnd, cls.SW_MAXIMIZE)
        return "Tela cheia"

    @classmethod
    def close_window(cls) -> str:
        """Close the active window."""
        hwnd = cls._get_foreground()
        cls.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        return "Janela fechada"

    @classmethod
    def always_on_top(cls, toggle: bool = True) -> str:
        """Toggle always-on-top for the active window."""
        hwnd = cls._get_foreground()
        flag = cls.HWND_TOPMOST if toggle else cls.HWND_NOTOPMOST
        cls.user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, cls.SWP_NOMOVE | cls.SWP_NOSIZE)
        return f"Sempre no topo: {'ativado' if toggle else 'desativado'}"

    @classmethod
    def snap_left(cls) -> str:
        """Snap window to left half of screen."""
        hwnd = cls._get_foreground()
        screen_w = cls.user32.GetSystemMetrics(0)
        screen_h = cls.user32.GetSystemMetrics(1)
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, 0, 0, screen_w // 2, screen_h, cls.SWP_SHOWWINDOW)
        return "Janela snap esquerda"

    @classmethod
    def snap_right(cls) -> str:
        """Snap window to right half of screen."""
        hwnd = cls._get_foreground()
        screen_w = cls.user32.GetSystemMetrics(0)
        screen_h = cls.user32.GetSystemMetrics(1)
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, screen_w // 2, 0, screen_w // 2, screen_h, cls.SWP_SHOWWINDOW)
        return "Janela snap direita"

    @classmethod
    def snap_top_left(cls) -> str:
        """Snap window to top-left quarter."""
        hwnd = cls._get_foreground()
        sw = cls.user32.GetSystemMetrics(0)
        sh = cls.user32.GetSystemMetrics(1)
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, 0, 0, sw // 2, sh // 2, cls.SWP_SHOWWINDOW)
        return "Janela canto superior esquerdo"

    @classmethod
    def snap_top_right(cls) -> str:
        """Snap window to top-right quarter."""
        hwnd = cls._get_foreground()
        sw = cls.user32.GetSystemMetrics(0)
        sh = cls.user32.GetSystemMetrics(1)
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, sw // 2, 0, sw // 2, sh // 2, cls.SWP_SHOWWINDOW)
        return "Janela canto superior direito"

    @classmethod
    def center(cls) -> str:
        """Center the active window on screen."""
        hwnd = cls._get_foreground()
        sw = cls.user32.GetSystemMetrics(0)
        sh = cls.user32.GetSystemMetrics(1)
        rect = ctypes.wintypes.RECT()
        cls.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        x = (sw - w) // 2
        y = (sh - h) // 2
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, x, y, w, h, cls.SWP_SHOWWINDOW)
        return "Janela centralizada"

    @classmethod
    def resize(cls, width: int, height: int) -> str:
        """Resize the active window."""
        hwnd = cls._get_foreground()
        rect = ctypes.wintypes.RECT()
        cls.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, rect.left, rect.top, width, height, cls.SWP_SHOWWINDOW)
        return f"Janela redimensionada para {width}x{height}"

    @classmethod
    def move(cls, x: int, y: int) -> str:
        """Move the active window."""
        hwnd = cls._get_foreground()
        rect = ctypes.wintypes.RECT()
        cls.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        cls.user32.SetWindowPos(hwnd, cls.HWND_TOP, x, y, w, h, cls.SWP_SHOWWINDOW)
        return f"Janela movida para ({x}, {y})"

    @classmethod
    def get_active_window_title(cls) -> str:
        """Get the title of the active window."""
        hwnd = cls._get_foreground()
        length = cls.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        cls.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value or "(sem título)"

    @classmethod
    def list_windows(cls) -> str:
        """List all visible windows."""
        result = []

        def enum_callback(hwnd, _):
            if cls.user32.IsWindowVisible(hwnd):
                length = cls.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    cls.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title:
                        result.append(f"  [{hwnd}] {title}")
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        cls.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        return f"Janelas visíveis ({len(result)}):\n" + "\n".join(result[:50])


# =========================================================================
# 5. PC Controller — Unified Interface
# =========================================================================

class PCController:
    """Universal PC Controller — the one-stop interface for everything.

    Fala ou digita "abre o google" → abre Chrome com Google.
    Fala ou digita "joga valorant" → lança Valorant.
    Fala ou digita "próxima música" → skip track.
    Fala ou digita "maximiza" → maximiza janela ativa.
    """

    # =================================================================== APPS

    @classmethod
    def open_app(cls, name: str) -> str:
        """Open any app by name. Smart resolution with aliases."""
        q = name.lower().strip()

        # Handle URLs
        if q.startswith("http") or "." in q and " " not in q:
            webbrowser.open(name)
            return f"Abrindo {name} no navegador..."

        # Handle YouTube/Netflix/Streaming
        streaming = {
            "youtube": "https://www.youtube.com",
            "netflix": "https://www.netflix.com",
            "prime video": "https://www.primevideo.com",
            "disney": "https://www.disneyplus.com",
            "twitch": "https://www.twitch.tv",
            "hulu": "https://www.hulu.com",
            "hbo": "https://www.max.com",
            "spotify web": "https://open.spotify.com",
        }
        for key, url in streaming.items():
            if key in q:
                webbrowser.open(url)
                return f"Abrindo {name}..."

        # Use app discovery
        app = AppDiscovery.find_app(q)
        if app:
            return GameLauncher._launch_app(app)

        # Last resort: try os.startfile
        try:
            os.startfile(name)
            return f"Tentando abrir {name}..."
        except Exception:
            return f"Não consegui encontrar '{name}'. Tente o nome completo do programa."

    @classmethod
    def close_app(cls, name: str) -> str:
        """Close an app by name."""
        try:
            os.system(f'taskkill /IM {name}.exe /F')
            return f"{name} fechado."
        except Exception:
            return f"Erro ao fechar {name}."

    # =================================================================== GAMES

    @classmethod
    def launch_game(cls, name: str) -> str:
        """Launch a game by name."""
        return GameLauncher.launch(name)

    # =================================================================== MEDIA

    @classmethod
    def media_play_pause(cls) -> str:
        return MediaController.play_pause()

    @classmethod
    def media_next(cls) -> str:
        return MediaController.next_track()

    @classmethod
    def media_prev(cls) -> str:
        return MediaController.prev_track()

    @classmethod
    def media_stop(cls) -> str:
        return MediaController.stop()

    @classmethod
    def play_music(cls, query: str = "") -> str:
        """Play music. Opens Spotify or YouTube."""
        if query:
            return MediaController.play_youtube(query)
        return MediaController.play_spotify()

    @classmethod
    def volume(cls, level: str) -> str:
        """Set volume. Accepts 'up', 'down', 'mute', or a number 0-100."""
        level = level.strip().lower()
        if level in ("up", "mais", "aumenta", "+"):
            return MediaController.volume_up()
        elif level in ("down", "menos", "diminui", "-"):
            return MediaController.volume_down()
        elif level in ("mute", "mudo", "silencio"):
            return MediaController.mute()
        else:
            try:
                return MediaController.set_volume(int(level))
            except ValueError:
                return MediaController.volume_up()

    # =================================================================== WINDOW

    @classmethod
    def maximize_window(cls) -> str:
        return WindowManager.maximize()

    @classmethod
    def minimize_window(cls) -> str:
        return WindowManager.minimize()

    @classmethod
    def restore_window(cls) -> str:
        return WindowManager.restore()

    @classmethod
    def close_window(cls) -> str:
        return WindowManager.close_window()

    @classmethod
    def close_tab(cls) -> str:
        """Close the current browser tab (Ctrl+W)."""
        return cls._hotkey("ctrl", "w")

    @classmethod
    def snap_window(cls, side: str) -> str:
        """Snap window to side: 'left', 'right', 'top', 'bottom'."""
        side = side.lower().strip()
        if side in ("left", "esquerda", "esq"):
            return WindowManager.snap_left()
        elif side in ("right", "direita", "dir"):
            return WindowManager.snap_right()
        elif side in ("top_left", "canto esquerdo"):
            return WindowManager.snap_top_left()
        elif side in ("top_right", "canto direito"):
            return WindowManager.snap_top_right()
        return WindowManager.center()

    @classmethod
    def get_active_window(cls) -> str:
        return WindowManager.get_active_window_title()

    @classmethod
    def list_windows(cls) -> str:
        return WindowManager.list_windows()

    # =================================================================== BROWSER

    @classmethod
    def google(cls, query: str = "") -> str:
        """Open Google (with optional search)."""
        if query:
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        else:
            url = "https://www.google.com"
        webbrowser.open(url)
        return f"Abrindo Google{' — ' + query if query else ''}..."

    @classmethod
    def youtube(cls, query: str = "") -> str:
        """Open YouTube (with optional search)."""
        return MediaController.play_youtube(query)

    @classmethod
    def open_url(cls, url: str) -> str:
        """Open any URL."""
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Abrindo {url}..."

    # =================================================================== SYSTEM

    @classmethod
    def screenshot(cls) -> str:
        """Take a screenshot."""
        try:
            import pyautogui
            downloads = Path.home() / "Downloads"
            downloads.mkdir(exist_ok=True)
            path = downloads / f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot(str(path))
            return f"Screenshot salvo: {path}"
        except ImportError:
            # Fallback: use Snipping Tool
            os.system("start ms-screenclip:")
            return "Abrindo ferramenta de captura..."

    @classmethod
    def lock_pc(cls) -> str:
        """Lock the PC."""
        ctypes.windll.user32.LockWorkStation()
        return "PC bloqueado."

    @classmethod
    def shutdown_pc(cls) -> str:
        """Shutdown the PC — MIN 30s delay for safety."""
        # SAFETY: use SuperUser which enforces 30s minimum
        from modules.superuser import SuperUser
        return SuperUser.shutdown(30)

    @classmethod
    def restart_pc(cls) -> str:
        """Restart the PC — MIN 30s delay for safety."""
        from modules.superuser import SuperUser
        return SuperUser.restart(30)

    @classmethod
    def sleep_pc(cls) -> str:
        """Put PC to sleep."""
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "PC entrando em modo suspensão..."

    # =================================================================== SMART ROUTING

    # ── Pattern tables for fast matching ──
    _EXACT_MEDIA = {
        # PT-BR
        "proxima musica": "next", "próxima música": "next",
        "proximo musica": "next",
        "musica anterior": "prev", "música anterior": "prev",
        "volta musica": "prev",
        "pausa": "pause", "pause": "pause", "play": "pause",
        "play pause": "pause", "pausa musica": "pause",
        "para musica": "stop", "pare musica": "stop",
        "stop music": "stop", "stop": "stop",
        "reproduz": "pause", "reproduzir": "pause",
        "retoma": "pause", "retomar": "pause",
        # EN
        "next song": "next", "next track": "next",
        "previous song": "prev", "previous track": "prev",
        "go back": "prev",
    }

    _EXACT_WINDOW = {
        "maximiza": "max", "maximizar": "max", "maximize": "max",
        "maximiza janela": "max", "maximizar janela": "max",
        "tela cheia": "max", "fullscreen": "max", "full screen": "max",
        "minimiza": "min", "minimizar": "min", "minimize": "min",
        "minimiza janela": "min", "minimizar janela": "min",
        "restaura": "restore", "restaurar": "restore", "restore": "restore",
        "fecha janela": "close", "fechar janela": "close",
        "fechar": "close", "close window": "close", "close": "close",
        "fecha aba": "close_tab", "fechar aba": "close_tab",
        "centraliza": "center", "centralizar": "center", "center": "center",
        "no topo": "topmost", "sempre no topo": "topmost",
        "always on top": "topmost", "fixa": "topmost",
        "snap esquerda": "snap_left", "snap left": "snap_left",
        "esquerda": "snap_left", "lado esquerdo": "snap_left",
        "snap direita": "snap_right", "snap right": "snap_right",
        "direita": "snap_right", "lado direito": "snap_right",
        "snap cima esquerda": "snap_tl", "canto superior esquerdo": "snap_tl",
        "snap cima direita": "snap_tr", "canto superior direito": "snap_tr",
        "snap baixo esquerda": "snap_bl", "snap baixo direita": "snap_br",
        "canto inferior esquerdo": "snap_bl", "canto inferior direito": "snap_br",
        "metade esquerda": "snap_left", "metade direita": "snap_right",
        "mover esquerda": "snap_left", "mover direita": "snap_right",
    }

    _EXACT_VOLUME = {
        "aumenta volume": "up", "volume up": "up", "mais volume": "up",
        "aumentar volume": "up", "sobe volume": "up", "mais": "up",
        "diminui volume": "down", "volume down": "down", "menos volume": "down",
        "diminuir volume": "down", "abaixa volume": "down", "menos": "down",
        "mudo": "mute", "mute": "mute", "silencio": "mute",
        "silêncio": "mute", "sem som": "mute", "mute on": "mute",
        "desmutar": "unmute", "unmute": "mute",
        "volume maximo": "100", "volume máximo": "100",
        "volume zero": "0", "zera volume": "0",
    }

    _EXACT_SYSTEM = {
        "bloqueia": "lock", "lock": "lock", "bloquear": "lock",
        "bloquear pc": "lock", "trava pc": "lock", "travar": "lock",
        "travar pc": "lock", "lock pc": "lock",
        "dormir": "sleep", "sleep": "sleep", "hibernar": "sleep",
        "hibernate": "sleep", "soneca": "sleep",
        # REMOVED: shutdown/restart from exact matches — too dangerous
        # These require explicit confirmation via SecurityGuard
        "captura": "screenshot", "captura de tela": "screenshot",
        "screenshot": "screenshot", "print screen": "screenshot",
        "tira print": "screenshot", "tirar print": "screenshot",
        "print": "screenshot", "screen": "screenshot",
        "tela": "screenshot", "foto da tela": "screenshot",
        "imagem da tela": "screenshot",
    }

    @classmethod
    def smart_action(cls, text: str) -> Optional[str]:
        """Parse natural language and execute the right action.

        Hundreds of patterns across 15+ categories.
        Returns None if no smart action matched.
        """
        t = text.lower().strip()

        # ══════════════════════════════════════════════════════════════════
        # 1. EXACT MATCH TABLES (fastest path)
        # ══════════════════════════════════════════════════════════════════

        # Media (exact)
        if t in cls._EXACT_MEDIA:
            action = cls._EXACT_MEDIA[t]
            if action == "next": return cls.media_next()
            if action == "prev": return cls.media_prev()
            if action == "pause": return cls.media_play_pause()
            if action == "stop": return cls.media_stop()

        # Window (exact)
        if t in cls._EXACT_WINDOW:
            action = cls._EXACT_WINDOW[t]
            if action == "max": return cls.maximize_window()
            if action == "min": return cls.minimize_window()
            if action == "restore": return cls.restore_window()
            if action == "close": return cls.close_window()
            if action == "close_tab": return cls.close_tab()
            if action == "center": return WindowManager.center()
            if action == "topmost": return WindowManager.always_on_top()
            if action == "snap_left": return cls.snap_window("left")
            if action == "snap_right": return cls.snap_window("right")
            if action == "snap_tl": return WindowManager.snap_top_left()
            if action == "snap_tr": return WindowManager.snap_top_right()
            if action == "snap_bl": return WindowManager.snap_left()  # fallback
            if action == "snap_br": return WindowManager.snap_right()  # fallback

        # Volume (exact)
        if t in cls._EXACT_VOLUME:
            return cls.volume(cls._EXACT_VOLUME[t])

        # System (exact)
        if t in cls._EXACT_SYSTEM:
            action = cls._EXACT_SYSTEM[t]
            if action == "lock": return cls.lock_pc()
            if action == "sleep": return cls.sleep_pc()
            if action == "shutdown": return cls.shutdown_pc()
            if action == "restart": return cls.restart_pc()
            if action == "screenshot": return cls.screenshot()

        # ══════════════════════════════════════════════════════════════════
        # 2. REGEX PATTERNS (flexible matching)
        # ══════════════════════════════════════════════════════════════════

        # ── 2.1 Open/launch apps ──
        m = re.match(r'^(abra?|abre|abrir|open|start|inicie|iniciar|execute|roda|rode|rodar|executa|execute)\s+(.+)', t)
        if m:
            return cls.open_app(m.group(2).strip())

        # ── 2.2 Close/kill apps ──
        m = re.match(r'^(fecha|fechar|close|kill|mate|mata|encerrar|encerra|finalizar|finaliza|stop|pare|parar)\s+(o |a |o |a )?\s*(.+)', t)
        if m:
            return cls.close_app(m.group(3).strip())

        # ── 2.3 Launch games ──
        m = re.match(r'^(jog(o|ue|ar)|play|rod(e|ar)|inicie o jogo|start game|abre o jogo|abra o jogo|joga)\s+(.+)', t)
        if m:
            return cls.launch_game(m.group(4).strip())

        # ── 2.4 Search Google ──
        m = re.match(r'^(pesquis(a|e|ar)|search|google|busque|buscar|procure|procurar|ache|achar|look up|pesquisar|pesquise)\s+(.+)', t)
        if m:
            return cls.google(m.group(3).strip())

        # ── 2.5 YouTube / Video ──
        m = re.match(r'^(youtube|vídeo|video|toque|toca|toque|reproduza|reproduz|assista|assiste|video no youtube|filme|série|serie)\s+(.+)', t)
        if m:
            return cls.youtube(m.group(2).strip())

        # ── 2.6 Volume with number ──
        m = re.match(r'(volume|vol)\s*(\d+)', t)
        if m:
            return cls.volume(m.group(2))
        m = re.match(r'^(define|defina|set|coloca|coloque)\s+volume\s+(para|to)?\s*(\d+)', t)
        if m:
            return cls.volume(m.group(4))

        # ── 2.7 Set volume to number ──
        m = re.match(r'volume\s+(para|to|em|at)\s*(\d+)', t)
        if m:
            return cls.volume(m.group(2))
        m = re.match(r'(coloca|coloque|set|define|defina|ajusta|ajuste)\s+volume\s+(em|para|to|at)?\s*(\d+)', t)
        if m:
            return cls.volume(m.group(3))

        # ── 2.8 Window snap with direction ──
        if "snap" in t or "metade" in t or "dividir" in t:
            if any(w in t for w in ("esquerda", "left", "esq")):
                return cls.snap_window("left")
            if any(w in t for w in ("direita", "right", "dir")):
                return cls.snap_window("right")
            if any(w in t for w in ("cima", "top", "superior")):
                return cls.snap_window("left")  # snap to top-left

        # ── 2.9 Navigate URL ──
        m = re.match(r'^(abra?|abre|navegue|navegar|acesse|acessar|visite|visitar|va para|vá para|go to|ir para)\s+(https?://\S+)', t)
        if m:
            return cls.open_url(m.group(2))
        m = re.match(r'^(abra?|abre|navegue|acesse|visite|va para|vá para|go to)\s+(\S+\.\S+)', t)
        if m:
            return cls.open_url(m.group(2))

        # ── 2.10 Play music/artist on Spotify/YouTube ──
        m = re.match(r'^(toque|toca|reproduza|reproduz|coloque|coloca|ponha|ponha|play)\s+(música|musica|song|music|de |do |da )?\s*(.+)', t)
        if m:
            query = m.group(3).strip()
            if any(w in t for w in ("youtube", "vídeo", "video")):
                return cls.youtube(query)
            return MediaController.play_spotify(query)

        # ── 2.11 Open specific websites ──
        _WEBSITES = {
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "youtube": "https://www.youtube.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "tiktok": "https://www.tiktok.com",
            "reddit": "https://www.reddit.com",
            "linkedin": "https://www.linkedin.com",
            "github": "https://www.github.com",
            "stackoverflow": "https://stackoverflow.com",
            "stack overflow": "https://stackoverflow.com",
            "spotify": "https://open.spotify.com",
            "netflix": "https://www.netflix.com",
            "prime video": "https://www.primevideo.com",
            "amazon": "https://www.amazon.com",
            "mercado livre": "https://www.mercadolivre.com.br",
            "mercadolivre": "https://www.mercadolivre.com.br",
            "olx": "https://www.olx.com.br",
            "uber": "https://www.uber.com",
            "ifood": "https://www.ifood.com.br",
            "rappi": "https://www.rappi.com.br",
            "uber eats": "https://www.ubereats.com",
            "reclame aqui": "https://www.reclameaqui.com.br",
            "chatgpt": "https://chat.openai.com",
            "openai": "https://chat.openai.com",
            "gemini": "https://gemini.google.com",
            "copilot": "https://copilot.microsoft.com",
            "bing": "https://www.bing.com",
            "yahoo": "https://www.yahoo.com",
            "wikipedia": "https://www.wikipedia.org",
            "maps": "https://maps.google.com",
            "google maps": "https://maps.google.com",
            "waze": "https://www.waze.com",
            "twitch": "https://www.twitch.tv",
            "discord web": "https://discord.com/app",
            "slack": "https://slack.com",
            "notion": "https://www.notion.so",
            "trello": "https://trello.com",
            "canva": "https://www.canva.com",
            "figma": "https://www.figma.com",
            "dribbble": "https://dribbble.com",
            "behance": "https://www.behance.net",
            "medium": "https://medium.com",
            "dev.to": "https://dev.to",
            "pypi": "https://pypi.org",
            "npm": "https://www.npmjs.com",
            "docker hub": "https://hub.docker.com",
            "vercel": "https://vercel.com",
            "netlify": "https://www.netlify.com",
            "heroku": "https://www.heroku.com",
            "aws console": "https://console.aws.amazon.com",
            "firebase": "https://console.firebase.google.com",
            "supabase": "https://supabase.com",
            "pinterest": "https://www.pinterest.com",
            "snapchat": "https://www.snapchat.com",
            "whatsapp web": "https://web.whatsapp.com",
            "telegram web": "https://web.telegram.org",
            "teams": "https://teams.microsoft.com",
            "zoom web": "https://zoom.us",
            "onedrive": "https://onedrive.live.com",
            "google drive": "https://drive.google.com",
            "dropbox": "https://www.dropbox.com",
            "mega": "https://mega.nz",
            "mediafire": "https://www.mediafire.com",
            "adobe": "https://www.adobe.com",
            "canva": "https://www.canva.com",
            "deezer": "https://www.deezer.com",
            "tidal": "https://tidal.com",
            "soundcloud": "https://soundcloud.com",
            "shazam": "https://www.shazam.com",
            "weather": "https://weather.com",
            "clima": "https://weather.com",
            "tempo": "https://weather.com",
            "horario": "https://www.timeanddate.com",
            "hora": "https://www.timeanddate.com",
            "google tradutor": "https://translate.google.com",
            "tradutor": "https://translate.google.com",
            "calculator": "https://www.calculator.net",
            "calculadora": "https://www.calculator.net",
            "converter": "https://www.google.com/search?q=converter",
            "moeda": "https://www.google.com/search?q=conversor+de+moeda",
        }
        for key, url in _WEBSITES.items():
            if t == key or t == f"abra {key}" or t == f"abre {key}" or t == f"abra o {key}" or t == f"abre o {key}":
                return cls.open_url(url)

        # ── 2.12 Specific app shortcuts ──
        _APP_SHORTCUTS = {
            "calculadora": "calc", "calculator": "calc",
            "paint": "mspaint", "paintbrush": "mspaint",
            "bloco de notas": "notepad", "notepad": "notepad",
            "explorador": "explorer", "explorer": "explorer",
            "file explorer": "explorer", "gerenciador de arquivos": "explorer",
            "gerenciador de tarefas": "taskmgr", "task manager": "taskmgr",
            "taskmgr": "taskmgr", "tarefas": "taskmgr",
            "prompt": "cmd", "cmd": "cmd", "command prompt": "cmd",
            "terminal": "wt", "windows terminal": "wt",
            "powershell": "powershell", "ps": "powershell",
            "configuracoes": "ms-settings:", "settings": "ms-settings:",
            "config": "ms-settings:", "opcoes": "ms-settings:",
            "painel de controle": "control", "control panel": "control",
            "gerenciador de dispositivos": "devmgmt.msc", "device manager": "devmgmt.msc",
            "gerenciamento de disco": "diskmgmt.msc", "disk management": "diskmgmt.msc",
            "registro": "regedit", "registry": "regedit", "regedit": "regedit",
            "servicos": "services.msc", "services": "services.msc",
            "event viewer": "eventvwr", "visualizador de eventos": "eventvwr",
            "performance": "resmon", "resource monitor": "resmon",
            "monitor de recursos": "resmon",
            "informacoes do sistema": "msinfo32", "system info": "msinfo32",
            "msinfo32": "msinfo32",
            "firewall": "wf.msc", "firewall do windows": "wf.msc",
            "limpeza de disco": "cleanmgr", "disk cleanup": "cleanmgr",
            "cleanmgr": "cleanmgr",
            "desfragmentar": "dfrgui", "defrag": "dfrgui",
            "loja": "ms-windows-store:", "microsoft store": "ms-windows-store:",
            "store": "ms-windows-store:", "app store": "ms-windows-store:",
            "xbox": "xbox", "xbox app": "xbox",
            "fotos": "ms-photos:", "photos": "ms-photos:",
            "camera": "microsoft.windows.camera:",
            "snipping tool": "SnippingTool", "snip": "ms-screenclip:",
            "alarms": "ms-clock:", "relogio": "ms-clock:", "clock": "ms-clock:",
            "notas": "ms-stickynotes:", "sticky notes": "ms-stickynotes:",
            "mapas": "bingmaps:", "maps": "bingmaps:",
            "3d viewer": "3dviewer:",
            "mixed reality": "hololens:",
            "accessibility": "ms-settings:easeofaccess",
            "acessibilidade": "ms-settings:easeofaccess",
            "wifi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "display": "ms-settings:display",
            "tela": "ms-settings:display",
            "som": "ms-settings:sound", "sound": "ms-settings:sound",
            "bateria": "ms-settings:batterysaver", "battery": "ms-settings:batterysaver",
            "privacidade": "ms-settings:privacy", "privacy": "ms-settings:privacy",
            "conta": "ms-settings:accounts", "account": "ms-settings:accounts",
            "atualizacao": "ms-settings:windowsupdate", "update": "ms-settings:windowsupdate",
            "windows update": "ms-settings:windowsupdate",
            "antivirus": "ms-settings:windowsdefender",
            "windows defender": "ms-settings:windowsdefender",
        }
        for key, cmd in _APP_SHORTCUTS.items():
            if t == key or t == f"abra {key}" or t == f"abre {key}" or t == f"abra o {key}" or t == f"abre o {key}":
                return cls.open_app(cmd)

        # ══════════════════════════════════════════════════════════════════
        # 3. COMPLEX PATTERNS (regex with context)
        # ══════════════════════════════════════════════════════════════════

        # ── 3.1 Window management ──
        m = re.match(r'^(maximiza|maximizar|maximize|max|maximiza a janela|maximizar a janela)\s*(a janela|janela|window)?', t)
        if m: return cls.maximize_window()
        m = re.match(r'^(minimiza|minimizar|minimize|min|minimiza a janela|minimizar a janela)\s*(a janela|janela|window)?', t)
        if m: return cls.minimize_window()
        m = re.match(r'^(restaura|restaurar|restore)\s*(a janela|janela|window)?', t)
        if m: return cls.restore_window()
        m = re.match(r'^(fecha|fechar|close)\s+(a janela|janela|window|aba|tab|programa|app| aplicativo)', t)
        if m: return cls.close_window()

        # ── 3.2 Volume dynamic ──
        m = re.match(r'^(aumenta|sobe|subir|increase|raise|up)\s+(o )?(volume|som|audio|sound)', t)
        if m: return cls.volume("up")
        m = re.match(r'^(diminui|abaixa|baixar|decrease|lower|down)\s+(o )?(volume|som|audio|sound)', t)
        if m: return cls.volume("down")
        m = re.match(r'^(muta|mutar|mude|mute|silencia|silenciar|silencie|desliga o som|sem som|no sound)\s*(o )?(volume|som|audio|sound)?', t)
        if m: return cls.volume("mute")

        # ── 3.3 Search patterns ──
        m = re.match(r'^(pesquis(a|e|ar)|search|google|busque|buscar|procure|procurar|ache|achar|look up|pesquisar|pesquise|procure por|busque por|pesquise por)\s+(.+)', t)
        if m: return cls.google(m.group(3).strip())

        # ── 3.4 YouTube patterns ──
        m = re.match(r'^(youtube|vídeo|video|toque|toca|toque|reproduza|reproduz|assista|assiste|video no youtube|filme|série|serie|ponha no youtube|coloque no youtube)\s+(.+)', t)
        if m: return cls.youtube(m.group(2).strip())

        # ── 3.5 Play music patterns ──
        m = re.match(r'^(toque|toca|reproduza|reproduz|coloque|coloca|ponha|ponha|play)\s+(música|musica|song|music|de |do |da )?\s*(.+)', t)
        if m:
            query = m.group(3).strip()
            if any(w in t for w in ("youtube", "vídeo", "video")):
                return cls.youtube(query)
            return MediaController.play_spotify(query)

        # ── 3.6 Game launch patterns ──
        m = re.match(r'^(jog(o|ue|ar)|play|rod(e|ar)|inicie o jogo|start game|abre o jogo|abra o jogo|joga)\s+(.+)', t)
        if m:
            target = m.group(4).strip()
            # Check if it looks like a game
            game_keywords = ("valorant", "fortnite", "minecraft", "cs2", "csgo", "gta", "apex",
                           "league", "dota", "pubg", "roblox", "cyberpunk", "elden",
                           "hogwarts", "red dead", "witcher", "skyrim", "doom",
                           "diablo", "overwatch", "genshin", "starfield", "baldur",
                           "halo", "forza", "fifa", "ea fc", "rainbow",
                           "assassin", "metro", "resident", "silent hill",
                           "palworld", "lethal company", "helldivers", "manor lords",
                           "satisfactory", "deep rock", "factorio", "rimworld",
                           "terraria", "stardew", "hollow knight", "cuphead",
                           "disco elysium", "outer wilds", "hades", "valheim",
                           "subnautica", "no man", "kerbal", "ark", "rust",
                           "liar", "content warning")
            if any(g in target for g in game_keywords):
                return cls.launch_game(target)

        # ══════════════════════════════════════════════════════════════════
        # 4. SYSTEM COMMANDS (exact phrases)
        # ══════════════════════════════════════════════════════════════════

        # ── 4.1 Power ──
        # Use word-boundary regex to avoid false positives like "não desligar o wifi"
        # REMOVED: shutdown/restart from PCController smart_action
        # These are handled ONLY through _local_answer with SecurityGuard confirmation
        if re.search(r'\b(dormir|sleep|hibernar|hibernate|soneca)\b', t):
            if not any(neg in t for neg in ("não", "nao", "don't")):
                if len(t) <= 20 or any(w in t for w in ("o pc", "computador", "o computador", "pc")):
                    return cls.sleep_pc()
        if re.search(r'\b(bloquear?|lock|travar?)\b', t):
            if not any(neg in t for neg in ("não", "nao", "don't")):
                if len(t) <= 20 or any(w in t for w in ("o pc", "computador", "o computador", "pc", "tela")):
                    return cls.lock_pc()

        # ── 4.2 Screenshot ──
        if any(w in t for w in ("screenshot", "captura de tela", "print screen",
                                 "tira print", "tirar print", "print", "screen",
                                 "foto da tela", "imagem da tela", "capture")):
            return cls.screenshot()

        # ── 4.3 Clipboard ──
        m = re.match(r'^(copiar|copie|copy)\s+(.+)', t)
        if m: return cls._clipboard_copy(m.group(2))
        m = re.match(r'^(colar|cole|paste)\s*(.+)?', t)
        if m: return cls._clipboard_paste()
        m = re.match(r'^(limpar|limpe|clear)\s*(clipboard|area de transferencia|area de transferência)?', t)
        if m: return cls._clipboard_clear()

        # ── 4.4 Keyboard shortcuts ──
        if any(w in t for w in ("ctrl c", "copiar selecionado", "copy selected")):
            return cls._hotkey("ctrl", "c")
        if any(w in t for w in ("ctrl v", "colar clipboard", "paste clipboard")):
            return cls._hotkey("ctrl", "v")
        if any(w in t for w in ("ctrl x", "recortar", "cut")):
            return cls._hotkey("ctrl", "x")
        if any(w in t for w in ("ctrl z", "desfazer", "undo")):
            return cls._hotkey("ctrl", "z")
        if any(w in t for w in ("ctrl y", "refazer", "redo")):
            return cls._hotkey("ctrl", "y")
        if any(w in t for w in ("ctrl s", "salvar", "save")):
            return cls._hotkey("ctrl", "s")
        if any(w in t for w in ("ctrl a", "selecionar tudo", "select all")):
            return cls._hotkey("ctrl", "a")
        if any(w in t for w in ("alt tab", "alternar janelas", "switch windows")):
            return cls._hotkey("alt", "tab")
        if any(w in t for w in ("alt f4", "fechar programa", "close program")):
            return cls._hotkey("alt", "f4")
        if any(w in t for w in ("ctrl w", "fechar aba", "close tab")):
            return cls._hotkey("ctrl", "w")
        if any(w in t for w in ("ctrl t", "nova aba", "new tab")):
            return cls._hotkey("ctrl", "t")
        if any(w in t for w in ("ctrl shift t", "restaurar aba", "reopen tab")):
            return cls._hotkey("ctrl", "shift", "t")
        if any(w in t for w in ("ctrl shift n", "aba anonima", "incognito")):
            return cls._hotkey("ctrl", "shift", "n")
        if any(w in t for w in ("ctrl l", "barra de endereco", "address bar")):
            return cls._hotkey("ctrl", "l")
        if any(w in t for w in ("ctrl r", "recarregar", "refresh", "reload")):
            return cls._hotkey("ctrl", "r")
        if any(w in t for w in ("f5", "recarregar pagina", "refresh page")):
            return cls._hotkey("f5")
        if any(w in t for w in ("ctrl shift esc", "abrir gerenciador de tarefas")):
            return cls._hotkey("ctrl", "shift", "esc")
        if any(w in t for w in ("win", "windows key", "menu inicio", "start menu")):
            return cls._hotkey("win")
        if any(w in t for w in ("win d", "mostrar desktop", "show desktop")):
            return cls._hotkey("win", "d")
        if any(w in t for w in ("win e", "explorador", "file explorer")):
            return cls._hotkey("win", "e")
        if any(w in t for w in ("win l", "bloquear pc", "lock pc")):
            return cls._hotkey("win", "l")
        if any(w in t for w in ("win i", "configuracoes", "settings")):
            return cls._hotkey("win", "i")
        if any(w in t for w in ("win r", "executar", "run dialog")):
            return cls._hotkey("win", "r")
        if any(w in t for w in ("win p", "projetar", "project display")):
            return cls._hotkey("win", "p")
        if any(w in t for w in ("win a", "centro de acoes", "action center")):
            return cls._hotkey("win", "a")
        if any(w in t for w in ("win v", "historico clipboard", "clipboard history")):
            return cls._hotkey("win", "v")
        if any(w in t for w in ("win shift s", "recorte", "snipping")):
            return cls._hotkey("win", "shift", "s")

        # ── 4.5 Browser navigation ──
        if any(w in t for w in ("voltar", "back", "go back", "page back")):
            return cls._hotkey("alt", "left")
        if any(w in t for w in ("avancar", "forward", "go forward", "page forward")):
            return cls._hotkey("alt", "right")
        if any(w in t for w in ("recarregar pagina", "refresh page", "reload page", "atualizar pagina")):
            return cls._hotkey("f5")
        if any(w in t for w in ("aba anterior", "previous tab")):
            return cls._hotkey("ctrl", "shift", "tab")
        if any(w in t for w in ("proxima aba", "next tab")):
            return cls._hotkey("ctrl", "tab")
        if any(w in t for w in ("ir para cima", "scroll to top", "topo da pagina")):
            return cls._hotkey("ctrl", "home")
        if any(w in t for w in ("ir para baixo", "scroll to bottom", "fim da pagina")):
            return cls._hotkey("ctrl", "end")
        if any(w in t for w in ("zoom in", "ampliar", "aumentar zoom", "zoom +")):
            return cls._hotkey("ctrl", "=")
        if any(w in t for w in ("zoom out", "reduzir", "diminuir zoom", "zoom -")):
            return cls._hotkey("ctrl", "-")
        if any(w in t for w in ("zoom normal", "reset zoom", "100%")):
            return cls._hotkey("ctrl", "0")

        # ── 4.6 Text editing ──
        if any(w in t for w in ("selecionar palavra", "select word")):
            return cls._hotkey("ctrl", "shift", "right")
        if any(w in t for w in ("ir para inicio da linha", "home")):
            return cls._hotkey("home")
        if any(w in t for w in ("ir para fim da linha", "end")):
            return cls._hotkey("end")
        if any(w in t for w in ("ir para inicio do documento", "ctrl home")):
            return cls._hotkey("ctrl", "home")
        if any(w in t for w in ("ir para fim do documento", "ctrl end")):
            return cls._hotkey("ctrl", "end")
        if any(w in t for w in ("delete", "deletar caractere", "apagar caractere")):
            return cls._hotkey("delete")
        if any(w in t for w in ("backspace", "apagar", "apagar para tras")):
            return cls._hotkey("backspace")
        if any(w in t for w in ("tab", "indentar", "tabular")):
            return cls._hotkey("tab")
        if any(w in t for w in ("enter", "pressionar enter", "nova linha")):
            return cls._hotkey("enter")
        if any(w in t for w in ("escape", "esc", "cancelar")):
            return cls._hotkey("escape")

        # ── 4.7 System info ──
        if any(w in t for w in ("horas", "hora", "que horas sao", "que horas são",
                                 "hora atual", "horario", "horário", "what time")):
            now = datetime.now().strftime("%H:%M")
            return f"São {now}."
        if any(w in t for w in ("data", "dia", "que dia e", "que dia é",
                                 "data atual", "what date", "what day")):
            now = datetime.now().strftime("%d/%m/%Y")
            return f"Hoje é {now}."
        if any(w in t for w in ("data e hora", "data e horario", "data e horário",
                                 "quando", "timestamp")):
            now = datetime.now().strftime("%d/%m/%Y %H:%M")
            return f"Data e hora: {now}."
        if any(w in t for w in ("dia da semana", "que dia", "what day of week")):
            days = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
            day = days[datetime.now().weekday()]
            return f"Hoje é {day}-feira."

        # ── 4.8 Quick math ──
        m = re.match(r'(quanto|calculate|calc|calcule|calcula|math)\s+(.+)', t)
        if m:
            expr = m.group(2).strip()
            try:
                # Safe eval for basic math only
                allowed = set('0123456789+-*/().% ')
                if all(c in allowed for c in expr):
                    result = eval(expr)
                    return f"{expr} = {result}"
            except Exception:
                pass
        # Direct math expression
        m = re.match(r'^([\d\s+\-*/().%]+)$', t)
        if m and any(op in t for op in ('+', '-', '*', '/', '%')):
            try:
                result = eval(t)
                return f"{t} = {result}"
            except Exception:
                pass

        # ── 4.9 Translate hint ──
        m = re.match(r'(traduz|translate|traduza|traduzir)\s+(.+)', t)
        if m:
            query = m.group(2).strip()
            return cls.open_url(f"https://translate.google.com/?sl=auto&tl=pt&text={urllib.parse.quote_plus(query)}")

        # ── 4.10 Weather ──
        if any(w in t for w in ("clima", "tempo", "weather", "tempo hoje",
                                 "como esta o tempo", "como está o tempo")):
            return cls.open_url("https://weather.com")
        m = re.match(r'(clima|tempo|weather)\s+(em|in|de|do|da)\s+(.+)', t)
        if m:
            city = m.group(3).strip()
            return cls.open_url(f"https://weather.com/search?query={urllib.parse.quote_plus(city)}")

        # ── 4.11 News ──
        if any(w in t for w in ("noticias", "notícias", "news", "ultimas noticias",
                                 "últimas notícias", "o que esta acontecendo")):
            return cls.open_url("https://news.google.com")
        m = re.match(r'(noticias|notícias|news)\s+(sobre|about|de|do|da)\s+(.+)', t)
        if m:
            query = m.group(3).strip()
            return cls.google(f"noticias {query}")

        # ── 4.12 Shopping ──
        m = re.match(r'(comprar|buy|buy|loja|store|mercado|market)\s+(.+)', t)
        if m:
            query = m.group(2).strip()
            return cls.google(f"comprar {query}")

        # ── 4.13 Map/Directions ──
        m = re.match(r'(como chegar|direcoes|direção|direções|route|mapa|map|ir para|vá para|como ir)\s+(.+)', t)
        if m:
            dest = m.group(2).strip()
            return cls.open_url(f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote_plus(dest)}")

        # ── 4.14 Timer/Alarm ──
        m = re.match(r'(timer|cronometro|cronômetro|alarme|alarm|lembrete|reminder)\s+(\d+)\s*(minuto|minutos|segundo|segundos|hora|horas|s|m|h)?', t)
        if m:
            amount = int(m.group(2))
            unit = m.group(3) or "minutos"
            if "hora" in unit:
                amount *= 3600
            elif "minuto" in unit:
                amount *= 60
            return cls._set_timer(amount)

        # ── 4.15 Open file/folder ──
        m = re.match(r'(abra|abre|open|open folder)\s+(a pasta|pasta|folder|o arquivo|arquivo|file)\s+(.+)', t)
        if m:
            path = m.group(3).strip()
            return cls._open_path(path)

        # ── 4.16 Create file/folder ──
        m = re.match(r'(crie|criar|create|nova|novo|new)\s+(pasta|folder|arquivo|file)\s+(.+)', t)
        if m:
            name = m.group(3).strip()
            return cls._create_path(name, "folder" if "pasta" in t or "folder" in t else "file")

        # ── 4.17 Delete file/folder ──
        m = re.match(r'(delete|deletar|delete|excluir|exclua|remova|remover|apague|apagar)\s+(o |a )?\s*(arquivo|pasta|file|folder)?\s*(.+)', t)
        if m:
            path = m.group(4).strip()
            return cls._delete_path(path)

        # ── 4.18 Run command ──
        m = re.match(r'(execute|executar|run|cmd|comando|command)\s+(.+)', t)
        if m:
            cmd = m.group(2).strip()
            return cls._run_command(cmd)

        # ── 4.19 Process management ──
        if any(w in t for w in ("processos", "processes", "processos ativos", "tasklist")):
            return cls._list_processes()
        m = re.match(r'(matar|mate|kill|encerrar|encerra|finalizar|finaliza|fechar|close)\s+(o |a )?\s*(processo|process|programa|program|app)?\s*(.+)', t)
        if m:
            target = m.group(4).strip()
            return cls._kill_process(target)

        # ── 4.20 WiFi ──
        if any(w in t for w in ("wifi list", "redes wifi", "wifi networks", "listar wifi")):
            return cls._wifi_list()
        m = re.match(r'(conectar|connect|conecta)\s+(wifi|rede|network|wi-fi)\s+(.+)', t)
        if m:
            ssid = m.group(3).strip()
            return cls._wifi_connect(ssid)

        # ── 4.21 Bluetooth ──
        if any(w in t for w in ("bluetooth", "emparelhar", "pair bluetooth")):
            return cls._open_bluetooth()

        # ── 4.22 Display/Brightness ──
        m = re.match(r'(brilho|brightness|luminosidade)\s+(\d+)', t)
        if m:
            level = int(m.group(2))
            return cls._set_brightness(level)

        # ── 4.23 Screensaver/Lock ──
        if any(w in t for w in ("screensaver", "protetor de tela")):
            return cls._start_screensaver()

        # ── 4.24 Empty recycle bin ──
        if any(w in t for w in ("esvaziar lixeira", "empty recycle", "limpar lixeira")):
            return cls._empty_recycle()

        # ── 4.25 System restore point ──
        if any(w in t for w in ("ponto de restauracao", "restore point", "criar restore point")):
            return cls._create_restore_point()

        # ── 4.26 Windows updates ──
        if any(w in t for w in ("atualizacoes", "updates", "windows update", "verificar atualizacoes")):
            return cls._check_updates()

        # ── 4.27 Disk space ──
        if any(w in t for w in ("espaco em disco", "disk space", "armazenamento",
                                 "quanto espaco", "espaço em disco", "storage")):
            return cls._disk_info()

        # ── 4.28 Network info ──
        if any(w in t for w in ("meu ip", "my ip", "endereco ip", "ip address",
                                 "ip publico", "public ip")):
            return cls._get_ip()
        if any(w in t for w in ("speed test", "teste de velocidade", "velocidade da internet",
                                 "internet speed", "velocidade da rede")):
            return cls.open_url("https://fast.com")

        # ── 4.29 Battery ──
        if any(w in t for w in ("bateria", "battery", "nivel da bateria", "battery level")):
            return cls._battery_info()

        # ── 4.30 Quick notes ──
        m = re.match(r'(anotar|anote|nota|note|salvar nota|save note|escrever|escreva)\s+(.+)', t)
        if m:
            text = m.group(2).strip()
            return cls._save_note(text)

        # ── 4.31 Calculator (open) ──
        if any(w in t for w in ("calculadora", "calculator", "calc", "abrir calculadora")):
            return cls.open_app("calc")

        # ── 4.32 Paint (open) ──
        if any(w in t for w in ("paint", "desenhar", "draw")):
            return cls.open_app("mspaint")

        # ── 4.33 Notepad (open) ──
        if any(w in t for w in ("bloco de notas", "notepad", "abrir notepad")):
            return cls.open_app("notepad")

        # ── 4.34 File Explorer (open) ──
        if any(w in t for w in ("explorador", "explorer", "file explorer",
                                 "gerenciador de arquivos", "abrir pasta")):
            return cls.open_app("explorer")

        # ── 4.35 Terminal/CMD (open) ──
        if any(w in t for w in ("terminal", "cmd", "prompt", "command prompt",
                                 "abrir terminal", "abrir cmd")):
            return cls.open_app("wt")

        # ── 4.36 PowerShell (open) ──
        if any(w in t for w in ("powershell", "ps", "abrir powershell")):
            return cls.open_app("powershell")

        # ── 4.37 Task Manager (open) ──
        if any(w in t for w in ("gerenciador de tarefas", "task manager",
                                 "abrir tarefas", "tarefas ativas")):
            return cls.open_app("taskmgr")

        # ── 4.38 Settings (open) ──
        if any(w in t for w in ("configuracoes", "configurações", "settings",
                                 "abrir configuracoes", "opcoes")):
            return cls.open_app("ms-settings:")

        # ── 4.39 Control Panel (open) ──
        if any(w in t for w in ("painel de controle", "control panel")):
            return cls.open_app("control")

        # ── 4.40 Device Manager (open) ──
        if any(w in t for w in ("gerenciador de dispositivos", "device manager")):
            return cls.open_app("devmgmt.msc")

        # ── 4.41 Disk Management (open) ──
        if any(w in t for w in ("gerenciamento de disco", "disk management")):
            return cls.open_app("diskmgmt.msc")

        # ── 4.42 Registry (open) ──
        if any(w in t for w in ("registro", "registry", "regedit")):
            return cls.open_app("regedit")

        # ── 4.43 Services (open) ──
        if any(w in t for w in ("servicos", "services", "abrir servicos")):
            return cls.open_app("services.msc")

        # ── 4.44 Event Viewer (open) ──
        if any(w in t for w in ("event viewer", "visualizador de eventos")):
            return cls.open_app("eventvwr")

        # ── 4.45 Resource Monitor (open) ──
        if any(w in t for w in ("monitor de recursos", "resource monitor", "performance")):
            return cls.open_app("resmon")

        # ── 4.46 System Info (open) ──
        if any(w in t for w in ("informacoes do sistema", "system info", "msinfo32")):
            return cls.open_app("msinfo32")

        # ── 4.47 Firewall (open) ──
        if any(w in t for w in ("firewall", "firewall do windows")):
            return cls.open_app("wf.msc")

        # ── 4.48 Disk Cleanup (open) ──
        if any(w in t for w in ("limpeza de disco", "disk cleanup", "cleanmgr")):
            return cls.open_app("cleanmgr")

        # ── 4.49 Defragment (open) ──
        if any(w in t for w in ("desfragmentar", "defrag", "otimizar drives")):
            return cls.open_app("dfrgui")

        # ── 4.50 Microsoft Store (open) ──
        if any(w in t for w in ("loja", "microsoft store", "store", "app store")):
            return cls.open_app("ms-windows-store:")

        # ── 4.51 Photos (open) ──
        if any(w in t for w in ("fotos", "photos", "abrir fotos")):
            return cls.open_app("ms-photos:")

        # ── 4.52 Camera (open) ──
        if any(w in t for w in ("camera", "câmera", "abrir camera")):
            return cls.open_app("microsoft.windows.camera:")

        # ── 4.53 Snipping Tool (open) ──
        if any(w in t for w in ("snipping tool", "ferramenta de captura", "recorte")):
            return cls.open_app("ms-screenclip:")

        # ── 4.54 Clock/Alarms (open) ──
        if any(w in t for w in ("relogio", "relógio", "clock", "alarms", "alarmes")):
            return cls.open_app("ms-clock:")

        # ── 4.55 Sticky Notes (open) ──
        if any(w in t for w in ("notas", "sticky notes", "notas adesivas")):
            return cls.open_app("ms-stickynotes:")

        # ── 4.56 Maps (open) ──
        if any(w in t for w in ("mapas", "maps", "bing maps")):
            return cls.open_app("bingmaps:")

        # ── 4.57 3D Viewer (open) ──
        if any(w in t for w in ("3d viewer", "visualizador 3d")):
            return cls.open_app("3dviewer:")

        # ── 4.58 Accessibility (open) ──
        if any(w in t for w in ("acessibilidade", "accessibility")):
            return cls.open_app("ms-settings:easeofaccess")

        # ── 4.59 WiFi Settings (open) ──
        if any(w in t for w in ("configurar wifi", "wifi settings", "config wifi")):
            return cls.open_app("ms-settings:network-wifi")

        # ── 4.60 Bluetooth Settings (open) ──
        if any(w in t for w in ("configurar bluetooth", "bluetooth settings")):
            return cls.open_app("ms-settings:bluetooth")

        # ── 4.61 Display Settings (open) ──
        if any(w in t for w in ("configurar tela", "display settings", "resolucao")):
            return cls.open_app("ms-settings:display")

        # ── 4.62 Sound Settings (open) ──
        if any(w in t for w in ("configurar som", "sound settings", "config som")):
            return cls.open_app("ms-settings:sound")

        # ── 4.63 Battery Settings (open) ──
        if any(w in t for w in ("configurar bateria", "battery settings")):
            return cls.open_app("ms-settings:batterysaver")

        # ── 4.64 Privacy Settings (open) ──
        if any(w in t for w in ("privacidade", "privacy", "configurar privacidade")):
            return cls.open_app("ms-settings:privacy")

        # ── 4.65 Account Settings (open) ──
        if any(w in t for w in ("conta", "account", "minha conta", "my account")):
            return cls.open_app("ms-settings:accounts")

        # ── 4.66 Windows Update (open) ──
        if any(w in t for w in ("atualizacao", "atualização", "windows update", "update")):
            return cls.open_app("ms-settings:windowsupdate")

        # ── 4.67 Windows Defender (open) ──
        if any(w in t for w in ("antivirus", "windows defender", "defender")):
            return cls.open_app("ms-settings:windowsdefender")

        # ══════════════════════════════════════════════════════════════════
        # 5. HELPER METHODS (for complex actions)
        # ══════════════════════════════════════════════════════════════════

    # --- Helper methods for smart routing ---

    @classmethod
    def _hotkey(cls, *keys) -> str:
        """Press a keyboard shortcut."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return f"Hotkey: {'+'.join(keys)}"
        except Exception as e:
            return f"Erro ao pressionar {'+'.join(keys)}: {e}"

    @classmethod
    def _clipboard_copy(cls, text: str = "") -> str:
        """Copy text to clipboard."""
        try:
            import pyperclip
            if text:
                pyperclip.copy(text)
            else:
                import pyautogui
                pyautogui.hotkey('ctrl', 'c')
            return "Copiado para clipboard."
        except ImportError:
            try:
                import pyautogui
                pyautogui.hotkey('ctrl', 'c')
                return "Copiado."
            except Exception:
                return "Erro ao copiar."

    @classmethod
    def _clipboard_paste(cls) -> str:
        """Paste from clipboard."""
        try:
            import pyautogui
            pyautogui.hotkey('ctrl', 'v')
            return "Colado."
        except Exception:
            return "Erro ao colar."

    @classmethod
    def _clipboard_clear(cls) -> str:
        """Clear clipboard."""
        try:
            import subprocess
            subprocess.run(['powershell', '-Command', 'Set-Clipboard -Value $null'],
                          capture_output=True, timeout=5)
            return "Clipboard limpo."
        except Exception:
            return "Erro ao limpar clipboard."

    @classmethod
    def _set_timer(cls, seconds: int) -> str:
        """Set a countdown timer."""
        try:
            # Open Windows Clock app with timer
            os.system(f'start ms-clock:timer-0-{seconds}')
            mins = seconds // 60
            secs = seconds % 60
            if mins > 0:
                return f"Timer de {mins}m {secs}s iniciado."
            return f"Timer de {secs}s iniciado."
        except Exception:
            return "Erro ao criar timer."

    @classmethod
    def _open_path(cls, path: str) -> str:
        """Open a file or folder."""
        try:
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                os.startfile(expanded)
                return f"Abrindo {path}..."
            return f"Caminho não encontrado: {path}"
        except Exception as e:
            return f"Erro ao abrir {path}: {e}"

    @classmethod
    def _create_path(cls, name: str, kind: str) -> str:
        """Create a file or folder."""
        try:
            downloads = Path.home() / "Downloads"
            if kind == "folder":
                (downloads / name).mkdir(exist_ok=True)
                return f"Pasta '{name}' criada em Downloads."
            else:
                (downloads / name).touch()
                return f"Arquivo '{name}' criado em Downloads."
        except Exception as e:
            return f"Erro ao criar {name}: {e}"

    @classmethod
    def _delete_path(cls, path: str) -> str:
        """Delete a file or folder."""
        try:
            expanded = os.path.expandvars(path)
            p = Path(expanded)
            if p.is_dir():
                import shutil
                shutil.rmtree(str(p))
            else:
                p.unlink()
            return f"Deletado: {path}"
        except Exception as e:
            return f"Erro ao deletar {path}: {e}"

    @classmethod
    def _run_command(cls, cmd: str) -> str:
        """Run a system command."""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=30,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            output = result.stdout.strip()
            if output:
                return output[:2000]
            return f"Comando executado (exit {result.returncode})."
        except Exception as e:
            return f"Erro ao executar comando: {e}"

    @classmethod
    def _list_processes(cls) -> str:
        """List running processes."""
        try:
            result = subprocess.run('tasklist /FO CSV /NH', shell=True,
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            lines = result.stdout.strip().split('\n')[:30]
            return f"Processos ativos ({len(lines)}):\n" + '\n'.join(lines)
        except Exception as e:
            return f"Erro ao listar processos: {e}"

    @classmethod
    def _kill_process(cls, name: str) -> str:
        """Kill a process."""
        try:
            result = subprocess.run(f'taskkill /F /IM {name}.exe', shell=True,
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode == 0:
                return f"Processo {name} finalizado."
            return f"Não encontrei o processo {name}."
        except Exception as e:
            return f"Erro ao finalizar {name}: {e}"

    @classmethod
    def _wifi_list(cls) -> str:
        """List WiFi networks."""
        try:
            result = subprocess.run('netsh wlan show networks', shell=True,
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return result.stdout[:2000] or "Nenhuma rede encontrada."
        except Exception as e:
            return f"Erro ao listar WiFi: {e}"

    @classmethod
    def _wifi_connect(cls, ssid: str) -> str:
        """Connect to WiFi network."""
        try:
            result = subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True,
                                   capture_output=True, text=True, timeout=15,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return f"Conectando a {ssid}..."
        except Exception as e:
            return f"Erro ao conectar: {e}"

    @classmethod
    def _open_bluetooth(cls) -> str:
        """Open Bluetooth settings."""
        return cls.open_app("ms-settings:bluetooth")

    @classmethod
    def _set_brightness(cls, level: int) -> str:
        """Set display brightness."""
        try:
            import wmi
            w = wmi.WMI(namespace='wmi')
            w.WmiMonitorBrightnessMethods().WmiSetBrightness(level, 0)
            return f"Brilho ajustado para {level}%."
        except ImportError:
            return f"Ajuste de brilho requer WMI. Use as teclas de brilho do teclado."
        except Exception as e:
            return f"Erro ao ajustar brilho: {e}"

    @classmethod
    def _start_screensaver(cls) -> str:
        """Start screensaver."""
        try:
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF140, 0)  # SC_SCREENSAVE
            return "Protetor de tela iniciado."
        except Exception:
            return "Erro ao iniciar protetor de tela."

    @classmethod
    def _empty_recycle(cls) -> str:
        """Empty recycle bin."""
        try:
            flags = 1 | 2 | 4  # NOCONFIRM | NOPROGRESSUI | NOSOUND
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return "Lixeira esvaziada."
        except Exception as e:
            return f"Erro ao esvaziar lixeira: {e}"

    @classmethod
    def _create_restore_point(cls) -> str:
        """Create system restore point."""
        try:
            result = subprocess.run(
                'powershell -Command "Checkpoint-Computer -Description \"Restore Point\" -RestorePointType MODIFY_SETTINGS"',
                shell=True, capture_output=True, text=True, timeout=120,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return "Ponto de restauração criado."
        except Exception as e:
            return f"Erro ao criar ponto de restauração: {e}"

    @classmethod
    def _check_updates(cls) -> str:
        """Check Windows updates."""
        return cls.open_app("ms-settings:windowsupdate")

    @classmethod
    def _disk_info(cls) -> str:
        """Get disk space info."""
        try:
            result = subprocess.run('wmic logicaldisk get size,freespace,caption', shell=True,
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return result.stdout[:1500] or "Erro ao obter info do disco."
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def _get_ip(cls) -> str:
        """Get public IP address."""
        try:
            import urllib.request
            ip = urllib.request.urlopen('https://api.ipify.org', timeout=5).read().decode()
            return f"Seu IP público: {ip}"
        except Exception:
            return "Erro ao obter IP."

    @classmethod
    def _battery_info(cls) -> str:
        """Get battery info."""
        try:
            result = subprocess.run(
                'powershell -Command "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | Format-List"',
                shell=True, capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return result.stdout[:500] or "Desktop (sem bateria)."
        except Exception:
            return "Erro ao obter info da bateria."

    @classmethod
    def _save_note(cls, text: str) -> str:
        """Save a quick note."""
        try:
            notes_dir = Path.home() / "Documents" / "GrandeSageNotes"
            notes_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            note_file = notes_dir / f"note_{timestamp}.txt"
            note_file.write_text(text, encoding='utf-8')
            return f"Nota salva: {note_file}"
        except Exception as e:
            return f"Erro ao salvar nota: {e}"


# =========================================================================
# Module-level shortcut for intent engine integration
# =========================================================================

def handle_pc_command(text: str) -> Optional[str]:
    """Quick entry point for the intent engine."""
    return PCController.smart_action(text)
