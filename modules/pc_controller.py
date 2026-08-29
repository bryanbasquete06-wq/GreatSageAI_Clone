# -*- coding: utf-8 -*-
"""
Great Sage AI — Universal PC Controller
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
    from GreatSageAI_Clone.modules.pc_controller import PCController
    PCController.open_app("google")        # abre Chrome com Google
    PCController.launch_game("valorant")   # lança Valorant
    PCController.media_play_pause()        # play/pause mídia
    PCController.maximize_window()         # maximiza janela ativa
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

logger = __import__("logging").getLogger("greatsage.pc_controller")


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
            for game_folder in p.iterdir():
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
    def close_window(cls) -> str:
        return WindowManager.close_window()

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
        """Shutdown the PC."""
        os.system("shutdown /s /t 10")
        return "PC desligando em 10 segundos..."

    @classmethod
    def restart_pc(cls) -> str:
        """Restart the PC."""
        os.system("shutdown /r /t 10")
        return "PC reiniciando em 10 segundos..."

    @classmethod
    def sleep_pc(cls) -> str:
        """Put PC to sleep."""
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "PC entrando em modo suspensão..."

    # =================================================================== SMART ROUTING

    @classmethod
    def smart_action(cls, text: str) -> Optional[str]:
        """Parse natural language and execute the right action.

        Returns None if no smart action matched (let other handlers try).
        """
        t = text.lower().strip()

        # ── Open/launch patterns ──
        if re.match(r'^(abra?|abre|abrir|open|start|inicie|iniciar|execute)\s+', t):
            target = re.sub(r'^(abra?|abre|abrir|open|start|inicie|iniciar|execute)\s+', '', t).strip()
            return cls.open_app(target)

        # ── Game patterns ──
        if re.match(r'^(jog(o|ue|ar)|play|rod(e|ar)|inicie o jogo|start game)\s+', t):
            target = re.sub(r'^(jog(o|ue|ar)|play|rod(e|ar)|inicie o jogo|start game)\s+', '', t).strip()
            return cls.launch_game(target)

        # ── Media patterns ──
        if t in ("próxima música", "proxima musica", "next song", "próxima", "next"):
            return cls.media_next()
        if t in ("música anterior", "musica anterior", "previous song", "volta", "previous"):
            return cls.media_prev()
        if t in ("pausa", "pause", "play", "play/pause", "pausa música", "para música"):
            return cls.media_play_pause()
        if t in ("para música", "pare música", "stop music", "stop"):
            return cls.media_stop()

        # ── Volume patterns ──
        vol_match = re.match(r'(volume|vol)\s+(up|down|mais|menos|mute|mudo|\d+)', t)
        if vol_match:
            return cls.volume(vol_match.group(1))

        if t in ("aumenta volume", "volume up", "mais volume", "mais"):
            return cls.volume("up")
        if t in ("diminui volume", "volume down", "menos volume", "menos"):
            return cls.volume("down")
        if t in ("mudo", "mute", "silêncio", "silencio"):
            return cls.volume("mute")

        # ── Window patterns ──
        if t in ("maximiza", "maximize", "maximizar", "tela cheia", "fullscreen"):
            return cls.maximize_window()
        if t in ("minimiza", "minimize", "minimizar", "minimiza janela"):
            return cls.minimize_window()
        if t in ("fecha janela", "close window", "fechar janela", "fechar"):
            return cls.close_window()
        if "snap" in t or "metade" in t:
            if "esquerda" in t or "left" in t:
                return cls.snap_window("left")
            elif "direita" in t or "right" in t:
                return cls.snap_window("right")
        if t in ("centraliza", "center", "centralizar"):
            return WindowManager.center()

        # ── Search patterns ──
        if re.match(r'^(pesquis(a|e|ar)|search|google|busque|buscar|procure)\s+', t):
            query = re.sub(r'^(pesquis(a|e|ar)|search|google|busque|buscar|procure)\s+', '', t).strip()
            return cls.google(query)

        if re.match(r'^(youtube|vídeo|video|toque|toca)\s+', t):
            query = re.sub(r'^(youtube|vídeo|video|toque|toca)\s+', '', t).strip()
            return cls.youtube(query)

        # ── Screenshot ──
        if t in ("screenshot", "captura de tela", "print screen", "tira print", "tirar print"):
            return cls.screenshot()

        # ── Lock/sleep/shutdown ──
        if t in ("bloqueia", "lock", "bloquear pc", "trava pc"):
            return cls.lock_pc()
        if t in ("dormir", "sleep", "hibernar", "hibernate"):
            return cls.sleep_pc()

        return None  # No smart action matched


# =========================================================================
# Module-level shortcut for intent engine integration
# =========================================================================

def handle_pc_command(text: str) -> Optional[str]:
    """Quick entry point for the intent engine."""
    return PCController.smart_action(text)
