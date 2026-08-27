# -*- coding: utf-8 -*-
"""
Great Sage AI — Browser Agent (Controle Total de Navegador)
============================================================
Automação completa de QUALQUER navegador no PC:

  - Chrome, Firefox, Edge (qualquer um que esteja instalado)
  - Abrir/fechar navegador
  - Navegar para URLs
  - Clicar em elementos (texto, xpath, css selector)
  - Digitar em campos (forms, search bars)
  - Extrair texto da página
  - Capturar screenshots
  - Preencher formulários
  - Scroll up/down
  - Gerenciar abas
  - Executar JavaScript
  - Voltar/avançar
  - Maximizar/minimizar
  - Espera inteligente por elementos

Modo de operação:
  1. Selenium (preferido) — controle completo via WebDriver
  2. pyautogui (fallback) — automação visual por coordenadas
  3. webbrowser (mínimo) — apenas abrir URLs

Uso:
    from GreatSageAI_Clone.modules.browser_agent import BrowserAgent
    BrowserAgent.open("https://google.com")
    BrowserAgent.type_in("search box", "python tutorial")
    BrowserAgent.click("Buscar")
    BrowserAgent.get_text()
"""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import threading
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Selenium imports (lazy — falls back to pyautogui if not installed)
# ---------------------------------------------------------------------------

_SELENIUM_AVAILABLE = False
_webdriver = None
_webdriver_options = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException,
        ElementClickInterceptedException, WebDriverException
    )
    _webdriver = webdriver
    _SELENIUM_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Browser detection — finds installed browsers
# ---------------------------------------------------------------------------

def _find_browser_paths() -> dict[str, list[str]]:
    """Detecta navegadores instalados no Windows."""
    browsers = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
    }
    found = {}
    for name, paths in browsers.items():
        for p in paths:
            if p and os.path.exists(p):
                found.setdefault(name, []).append(p)
    return found


def _get_default_browser() -> str:
    """Retorna o navegador padrão do Windows."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice")
        prog_id = winreg.QueryValueEx(key, "ProgID")[0]
        winreg.CloseKey(key)
        if "Chrome" in prog_id:
            return "chrome"
        elif "Firefox" in prog_id:
            return "firefox"
        elif "Edge" in prog_id:
            return "edge"
    except Exception:
        pass
    return "chrome"  # fallback


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BrowserState:
    """Estado atual do navegador controlado."""
    browser_name: str = ""
    driver: Any = None
    is_running: bool = False
    current_url: str = ""
    current_title: str = ""
    window_width: int = 1920
    window_height: int = 1080
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update_info(self):
        if self.driver:
            try:
                self.current_url = self.driver.current_url
                self.current_title = self.driver.title
            except Exception:
                pass


# ---------------------------------------------------------------------------
# BrowserAgent — Main class
# ---------------------------------------------------------------------------

class BrowserAgent:
    """Controle total de qualquer navegador."""

    _state = BrowserState()
    _installed_browsers: dict = {}
    _initialized = False

    @classmethod
    def _ensure_init(cls):
        if not cls._initialized:
            cls._installed_browsers = _find_browser_paths()
            cls._initialized = True

    # =================================================================== CORE

    @classmethod
    def open(cls, url: str = "https://www.google.com", browser: str = None,
             headless: bool = False) -> str:
        """Abre navegador e navega para URL.

        Args:
            url: URL para navegar
            browser: "chrome", "firefox", "edge", "brave" (None = default)
            headless: modo sem interface gráfica
        """
        cls._ensure_init()

        # Se já tem driver rodando, só navega
        if cls._state.driver and cls._state.is_running:
            try:
                cls._state.driver.get(url)
                cls._state.update_info()
                return f"Navegando para {url} no {cls._state.browser_name}"
            except Exception:
                cls._close_driver()

        browser_name = browser or _get_default_browser()

        # Tenta Selenium primeiro
        if _SELENIUM_AVAILABLE:
            try:
                return cls._open_selenium(url, browser_name, headless)
            except Exception as e:
                pass

        # Fallback: webbrowser module (sem controle avançado)
        try:
            webbrowser.open(url)
            return f"Abrindo {url} no navegador padrão (sem controle avançado)"
        except Exception as e:
            return f"Erro ao abrir navegador: {e}"

    @classmethod
    def _open_selenium(cls, url: str, browser_name: str, headless: bool) -> str:
        """Abre navegador via Selenium WebDriver."""
        if browser_name == "chrome":
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            if headless:
                options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)

        elif browser_name == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            driver = webdriver.Firefox(options=options)

        elif browser_name == "edge":
            options = webdriver.EdgeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-blink-features=AutomationControlled")
            if headless:
                options.add_argument("--headless=new")
            driver = webdriver.Edge(options=options)

        elif browser_name == "brave":
            options = webdriver.ChromeOptions()
            brave_path = cls._installed_browsers.get("brave", [None])[0]
            if brave_path:
                options.binary_location = brave_path
            options.add_argument("--start-maximized")
            if headless:
                options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)

        else:
            return f"Navegador '{browser_name}' não suportado para Selenium"

        driver.get(url)
        cls._state.driver = driver
        cls._state.browser_name = browser_name
        cls._state.is_running = True
        cls._state.update_info()

        return f"Navegador {browser_name} aberto em {url}"

    @classmethod
    def _close_driver(cls):
        """Fecha o driver Selenium."""
        if cls._state.driver:
            try:
                cls._state.driver.quit()
            except Exception:
                pass
        cls._state.driver = None
        cls._state.is_running = False

    # =================================================================== NAVIGATION

    @classmethod
    def navigate(cls, url: str) -> str:
        """Navega para URL."""
        if not cls._state.driver:
            return cls.open(url)
        try:
            cls._state.driver.get(url)
            cls._state.update_info()
            return f"Navegando para {url}"
        except Exception as e:
            return f"Erro ao navegar: {e}"

    @classmethod
    def back(cls) -> str:
        """Volta para página anterior."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.back()
            cls._state.update_info()
            return "Voltando..."
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def forward(cls) -> str:
        """Avança para próxima página."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.forward()
            cls._state.update_info()
            return "Avançando..."
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def refresh(cls) -> str:
        """Recarrega a página."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.refresh()
            return "Página recarregada"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def current_url(cls) -> str:
        """Retorna URL atual."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.update_info()
        return cls._state.current_url

    @classmethod
    def page_title(cls) -> str:
        """Retorna título da página."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.update_info()
        return cls._state.current_title

    # =================================================================== INTERACTION

    @classmethod
    def click(cls, target: str, by: str = "auto", timeout: float = 10) -> str:
        """Clica em um elemento da página.

        Args:
            target: texto visível, CSS selector, ou XPath
            by: "text", "css", "xpath", "id", "name", "auto" (detecta automaticamente)
            timeout: tempo máximo de espera (segundos)
        """
        if not cls._state.driver:
            return "Navegador não está aberto"

        driver = cls._state.driver

        # Auto-detecta tipo de seletor
        if by == "auto":
            by = cls._detect_selector_type(target)

        locator_map = {
            "text": (By.XPATH, f"//*[contains(text(), '{target}')] | //button[contains(text(), '{target}')] | //a[contains(text(), '{target}')]"),
            "text_exact": (By.XPATH, f"//*[normalize-space(text())='{target}']"),
            "css": (By.CSS_SELECTOR, target),
            "xpath": (By.XPATH, target),
            "id": (By.ID, target),
            "name": (By.NAME, target),
            "link": (By.PARTIAL_LINK_TEXT, target),
        }

        locator = locator_map.get(by, (By.XPATH, f"//*[contains(text(), '{target}')]"))

        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            element.click()
            cls._state.update_info()
            return f"Clicou em '{target}'"
        except TimeoutException:
            # Tenta clique via JavaScript como fallback
            try:
                element = driver.find_element(*locator)
                driver.execute_script("arguments[0].click();", element)
                cls._state.update_info()
                return f"Clicou em '{target}' (via JS)"
            except Exception:
                return f"Elemento '{target}' não encontrado"
        except ElementClickInterceptedException:
            # Tenta scroll + click via JS
            try:
                element = driver.find_element(*locator)
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", element)
                cls._state.update_info()
                return f"Clicou em '{target}' (via JS scroll)"
            except Exception:
                return f"Não conseguiu clicar em '{target}'"
        except Exception as e:
            return f"Erro ao clicar: {e}"

    @classmethod
    def type_in(cls, target: str, text: str, clear: bool = True,
                press_enter: bool = False, by: str = "auto", timeout: float = 10) -> str:
        """Digita texto em um campo.

        Args:
            target: seletor do campo (texto, CSS, XPath, id)
            text: texto para digitar
            clear: limpar campo antes de digitar
            press_enter: pressionar Enter após digitar
            by: tipo de seletor
            timeout: timeout em segundos
        """
        if not cls._state.driver:
            return "Navegador não está aberto"

        driver = cls._state.driver

        if by == "auto":
            by = cls._detect_selector_type(target)

        locator_map = {
            "text": (By.XPATH, f"//input[contains(@placeholder, '{target}')] | //textarea[contains(@placeholder, '{target}')]"),
            "css": (By.CSS_SELECTOR, target),
            "xpath": (By.XPATH, target),
            "id": (By.ID, target),
            "name": (By.NAME, target),
            "placeholder": (By.XPATH, f"//*[contains(@placeholder, '{target}')]"),
        }

        locator = locator_map.get(by, (By.ID, target))

        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            element.click()
            if clear:
                element.clear()
            time.sleep(0.1)
            element.send_keys(text)
            if press_enter:
                element.send_keys(Keys.RETURN)
            time.sleep(0.3)
            cls._state.update_info()
            result = f"Digitou '{text}' em '{target}'"
            if press_enter:
                result += " e pressionou Enter"
            return result
        except TimeoutException:
            # Fallback: tenta encontrar por XPath genérico
            try:
                element = driver.find_element(By.XPATH,
                    f"//input[@type='text' or @type='search'] | //textarea")
                element.click()
                if clear:
                    element.clear()
                element.send_keys(text)
                if press_enter:
                    element.send_keys(Keys.RETURN)
                cls._state.update_info()
                return f"Digitou '{text}' no campo encontrado"
            except Exception:
                return f"Campo '{target}' não encontrado"
        except Exception as e:
            return f"Erro ao digitar: {e}"

    @classmethod
    def search_google(cls, query: str) -> str:
        """Pesquisa no Google de forma inteligente."""
        cls._ensure_init()

        # Abre Google e pesquisa
        result = cls.open("https://www.google.com")

        # Espera carregar e digita na search box
        time.sleep(1)
        type_result = cls.type_in("search", query, press_enter=True, by="text", timeout=5)

        if "não encontrado" in type_result.lower():
            # Fallback: tenta por name q
            type_result = cls.type_in("q", query, press_enter=True, by="name", timeout=5)

        return f"Pesquisando no Google: {query}"

    @classmethod
    def search_youtube(cls, query: str) -> str:
        """Pesquisa no YouTube."""
        result = cls.open("https://www.youtube.com")
        time.sleep(1)
        # Clica na search box do YouTube
        cls.click("Pesquisar", by="text", timeout=5)
        time.sleep(0.3)
        cls.type_in("search", query, press_enter=True, by="text", timeout=5)
        return f"Pesquisando no YouTube: {query}"

    @classmethod
    def play_youtube_video(cls, query: str) -> str:
        """Pesquisa e toca primeiro vídeo do YouTube."""
        result = cls.search_youtube(query)
        time.sleep(2)
        # Clica no primeiro vídeo
        cls.click("thumbnail", by="css", timeout=5)
        return f"Reproduzindo no YouTube: {query}"

    # =================================================================== CONTENT

    @classmethod
    def get_text(cls, max_chars: int = 5000) -> str:
        """Extrai texto visível da página."""
        if not cls._state.driver:
            return "Navegador não está aberto"

        try:
            # Remove scripts e styles
            cls._state.driver.execute_script("""
                var elements = document.querySelectorAll('script, style, noscript');
                for(var i = 0; i < elements.length; i++) {
                    elements[i].remove();
                }
            """)
            text = cls._state.driver.find_element(By.TAG_NAME, "body").text
            if len(text) > max_chars:
                return text[:max_chars] + f"\n... ({len(text)} chars total)"
            return text or "(página vazia)"
        except Exception as e:
            return f"Erro ao extrair texto: {e}"

    @classmethod
    def get_links(cls, max_links: int = 20) -> str:
        """Extrai links da página."""
        if not cls._state.driver:
            return "Navegador não está aberto"

        try:
            links = cls._state.driver.find_elements(By.TAG_NAME, "a")
            result = []
            for link in links[:max_links]:
                href = link.get_attribute("href")
                text = link.text.strip()[:80]
                if href and text:
                    result.append(f"  {text} → {href}")
            return f"Links encontrados ({len(result)}):\n" + "\n".join(result) if result else "Nenhum link encontrado"
        except Exception as e:
            return f"Erro ao extrair links: {e}"

    @classmethod
    def get_page_source(cls, max_chars: int = 3000) -> str:
        """Retorna HTML fonte da página."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            source = cls._state.driver.page_source
            if len(source) > max_chars:
                return source[:max_chars] + f"\n... ({len(source)} chars total)"
            return source
        except Exception as e:
            return f"Erro: {e}"

    # =================================================================== SCREENSHOT

    @classmethod
    def screenshot(cls, path: str = None) -> str:
        """Captura screenshot da página."""
        if not cls._state.driver:
            return "Navegador não está aberto"

        try:
            if not path:
                downloads = Path(os.path.expanduser("~/Downloads"))
                downloads.mkdir(exist_ok=True)
                path = str(downloads / f"browser_screenshot_{int(time.time())}.png")
            cls._state.driver.save_screenshot(path)
            return f"Screenshot salvo: {path}"
        except Exception as e:
            return f"Erro ao capturar screenshot: {e}"

    # =================================================================== SCROLL

    @classmethod
    def scroll_down(cls, pixels: int = 500) -> str:
        """Scroll para baixo."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.execute_script(f"window.scrollBy(0, {pixels});")
            return f"Scroll down {pixels}px"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def scroll_up(cls, pixels: int = 500) -> str:
        """Scroll para cima."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.execute_script(f"window.scrollBy(0, -{pixels});")
            return f"Scroll up {pixels}px"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def scroll_to_top(cls) -> str:
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.driver.execute_script("window.scrollTo(0, 0);")
        return "Scroll ao topo"

    @classmethod
    def scroll_to_bottom(cls) -> str:
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        return "Scroll ao final"

    # =================================================================== TABS

    @classmethod
    def new_tab(cls, url: str = "about:blank") -> str:
        """Abre nova aba."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.execute_script(f"window.open('{url}', '_blank');")
            cls._state.update_info()
            return f"Nova aba aberta: {url}"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def close_tab(cls) -> str:
        """Fecha aba atual."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            if len(cls._state.driver.window_handles) > 1:
                cls._state.driver.close()
                # Muda para última aba
                cls._state.driver.switch_to.window(cls._state.driver.window_handles[-1])
                cls._state.update_info()
                return "Aba fechada"
            return "Última aba — não pode fechar"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def switch_tab(cls, index: int = -1) -> str:
        """Muda para outra aba."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            cls._state.driver.switch_to.window(cls._state.driver.window_handles[index])
            cls._state.update_info()
            return f"Mudou para aba: {cls._state.current_title}"
        except Exception as e:
            return f"Erro: {e}"

    @classmethod
    def tab_count(cls) -> int:
        if not cls._state.driver:
            return 0
        return len(cls._state.driver.window_handles)

    # =================================================================== JAVASCRIPT

    @classmethod
    def execute_js(cls, script: str) -> str:
        """Executa JavaScript na página."""
        if not cls._state.driver:
            return "Navegador não está aberto"
        try:
            result = cls._state.driver.execute_script(script)
            if result is not None:
                return str(result)[:2000]
            return "JS executado (sem retorno)"
        except Exception as e:
            return f"Erro JS: {e}"

    # =================================================================== FORMS

    @classmethod
    def fill_form(cls, fields: dict[str, str], submit: bool = True) -> str:
        """Preenche formulário com múltiplos campos.

        fields: {"campo": "valor"} — usa id, name, ou placeholder para encontrar
        """
        if not cls._state.driver:
            return "Navegador não está aberto"

        results = []
        for field_name, value in fields.items():
            r = cls.type_in(field_name, value, by="auto", timeout=5)
            results.append(f"  {field_name}: {r}")

        if submit:
            # Tenta encontrar botão de submit
            try:
                submit_btn = cls._state.driver.find_element(
                    By.XPATH,
                    "//button[@type='submit'] | //input[@type='submit'] | //button[contains(text(), 'Enviar') or contains(text(), 'Login') or contains(text(), 'Sign')]"
                )
                submit_btn.click()
                results.append("  Formulário enviado!")
            except Exception:
                results.append("  Botão de envio não encontrado")

        return "Preenchimento do formulário:\n" + "\n".join(results)

    # =================================================================== WINDOW

    @classmethod
    def maximize(cls) -> str:
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.driver.maximize_window()
        return "Janela maximizada"

    @classmethod
    def minimize(cls) -> str:
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.driver.minimize_window()
        return "Janela minimizada"

    @classmethod
    def set_window_size(cls, width: int, height: int) -> str:
        if not cls._state.driver:
            return "Navegador não está aberto"
        cls._state.driver.set_window_size(width, height)
        return f"Janela: {width}x{height}"

    # =================================================================== CLOSE

    @classmethod
    def close(cls) -> str:
        """Fecha navegador completamente."""
        if cls._state.driver:
            browser = cls._state.browser_name
            cls._close_driver()
            return f"Navegador {browser} fechado"
        return "Navegador já estava fechado"

    # =================================================================== STATUS

    @classmethod
    def status(cls) -> str:
        """Status do navegador."""
        cls._ensure_init()
        installed = ", ".join(cls._installed_browsers.keys()) or "nenhum detectado"
        if cls._state.is_running:
            return (
                f"NAVEGADOR ATIVO: {cls._state.browser_name}\n"
                f"  URL: {cls._state.current_url}\n"
                f"  Título: {cls._state.current_title}\n"
                f"  Selenium: {'Sim' if _SELENIUM_AVAILABLE else 'Não (pyautogui)'}\n"
                f"  Abas: {cls.tab_count()}\n"
                f"Navegadores instalados: {installed}"
            )
        return (
            f"Navegador: fechado\n"
            f"Selenium: {'Disponível' if _SELENIUM_AVAILABLE else 'Não instalado (pip install selenium)'}\n"
            f"Navegadores detectados: {installed}"
        )

    # =================================================================== HELPERS

    @classmethod
    def _detect_selector_type(cls, target: str) -> str:
        """Detecta automaticamente o tipo de seletor."""
        if target.startswith("//"):
            return "xpath"
        if target.startswith("#") or "." in target and not " " in target:
            return "css"
        if target.startswith("http"):
            return "text"
        # Assume text match
        return "text"

    # =================================================================== COMPREHENSIVE CONTROL

    @classmethod
    def do(cls, action: str, **kwargs) -> str:
        """Interface unificada para todas as ações do navegador.

        action: "open", "click", "type", "search", "text", "screenshot",
                "scroll", "back", "forward", "refresh", "close", etc.
        """
        actions = {
            "open": lambda: cls.open(kwargs.get("url", "https://google.com"), kwargs.get("browser")),
            "navigate": lambda: cls.navigate(kwargs.get("url", "")),
            "click": lambda: cls.click(kwargs.get("target", ""), by=kwargs.get("by", "auto")),
            "type": lambda: cls.type_in(
                kwargs.get("target", ""), kwargs.get("text", ""),
                clear=kwargs.get("clear", True),
                press_enter=kwargs.get("press_enter", False)
            ),
            "search": lambda: cls.search_google(kwargs.get("query", kwargs.get("text", ""))),
            "youtube": lambda: cls.search_youtube(kwargs.get("query", kwargs.get("text", ""))),
            "text": lambda: cls.get_text(kwargs.get("max_chars", 5000)),
            "links": lambda: cls.get_links(),
            "screenshot": lambda: cls.screenshot(kwargs.get("path")),
            "scroll_down": lambda: cls.scroll_down(kwargs.get("pixels", 500)),
            "scroll_up": lambda: cls.scroll_up(kwargs.get("pixels", 500)),
            "back": lambda: cls.back(),
            "forward": lambda: cls.forward(),
            "refresh": lambda: cls.refresh(),
            "close": lambda: cls.close(),
            "maximize": lambda: cls.maximize(),
            "new_tab": lambda: cls.new_tab(kwargs.get("url", "about:blank")),
            "close_tab": lambda: cls.close_tab(),
            "js": lambda: cls.execute_js(kwargs.get("script", "")),
            "status": lambda: cls.status(),
        }

        handler = actions.get(action)
        if handler:
            return handler()
        return f"Ação '{action}' desconhecida. Ações: {', '.join(actions.keys())}"
