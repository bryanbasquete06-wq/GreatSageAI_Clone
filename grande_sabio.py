import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
except ImportError:
    tk = None


def load_env_file():
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


class Elivea:
    def __init__(self, voice_enabled: bool = False):
        self.voice_enabled = voice_enabled
        self.microphone_available = self._check_windows_voice()
        self.wake_phrases = ["elívea", "elvea", "great sage", "sage", "grande sábio", "sábio"]

    def _escape_powershell(self, value: str) -> str:
        return value.replace("`", "``").replace('"', '`"')

    def _check_windows_voice(self):
        if platform.system() != "Windows":
            return False
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    "Add-Type -AssemblyName System.Speech; Write-Output 'voice_ok'",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return result.returncode == 0 and "voice_ok" in result.stdout.lower()
        except Exception:
            return False

    def speak(self, text: str):
        print(f"Elívea: {text}")
        if not self.voice_enabled:
            return

        if platform.system() != "Windows":
            return

        safe_text = self._escape_powershell(text)
        command = (
            f'Add-Type -AssemblyName System.Speech; '
            f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'$s.Rate = -1; '
            f'$s.Volume = 100; '
            f'$s.Speak("{safe_text}");'
        )
        try:
            subprocess.run([
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ], check=False, timeout=30)
        except Exception:
            pass

    def listen(self):
        if platform.system() != "Windows":
            return input("Você: ").strip()

        script = r'''
[void][System.Reflection.Assembly]::LoadWithPartialName("System.Speech")
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine([System.Globalization.CultureInfo]::GetCultureInfo('pt-BR'))
try {
    $engine.SetInputToDefaultAudioDevice()
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    $engine.LoadGrammar($grammar)
    $engine.MaxAlternates = 1
    $result = $engine.Recognize()
    if ($null -ne $result -and $result.Confidence -gt 0.5) {
        Write-Output $result.Text
    }
} catch {
    Write-Error $_.Exception.Message
}
'''

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=15,
            )
            text = proc.stdout.strip()
            if text and not text.lower().startswith("error"):
                print(f"Você disse: {text}")
                return text
            return ""
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return input("Você: ").strip()

    def wait_for_wake_word(self):
        if not self.voice_enabled or not self.microphone_available:
            return ""

        while True:
            text = self.listen()
            candidate = text.lower().strip()
            if not candidate:
                continue

            if any(phrase in candidate for phrase in self.wake_phrases):
                return candidate

            if "great" in candidate and "sage" in candidate:
                return candidate

            if "grande" in candidate and "sabio" in candidate:
                return candidate

    def _format_time_now(self):
        return datetime.now().strftime("%H:%M:%S")

    def _format_date_now(self):
        return datetime.now().strftime("%d/%m/%Y")

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

    def _open_app_by_name(self, app_name: str):
        aliases = {
            "google chrome": ["chrome.exe", "googlechrome.exe"],
            "chrome": ["chrome.exe", "googlechrome.exe"],
            "navegador": ["chrome.exe", "msedge.exe", "firefox.exe"],
            "edge": ["msedge.exe"],
            "firefox": ["firefox.exe"],
            "notepad": ["notepad.exe"],
            "bloco de notas": ["notepad.exe"],
            "calculadora": ["calc.exe"],
            "paint": ["mspaint.exe"],
            "pintura": ["mspaint.exe"],
            "cmd": ["cmd.exe"],
            "prompt": ["cmd.exe"],
            "terminal": ["cmd.exe"],
            "vscode": ["code.exe"],
            "visual studio code": ["code.exe"],
            "explorer": ["explorer.exe"],
            "arquivos": ["explorer.exe"],
            "spotify": ["spotify.exe"],
            "discord": ["discord.exe"],
            "steam": ["steam.exe"],
        }

        candidates = aliases.get(app_name, [app_name])
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                subprocess.Popen([resolved])
                return True

            if candidate.lower().endswith(".exe"):
                base_dir = os.environ.get("SYSTEMROOT", r"C:\Windows")
                candidate_path = os.path.join(base_dir, "System32", candidate)
                if os.path.exists(candidate_path):
                    subprocess.Popen([candidate_path])
                    return True

        url_map = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "youtube music": "https://music.youtube.com",
        }
        if app_name in url_map:
            return self._open_url(url_map[app_name])

        return False

    def _local_answer(self, question: str):
        q = question.lower().strip()
        if not q:
            return "Peço que me faça uma pergunta clara."

        if q in {"oi", "olá", "bom dia", "boa tarde", "boa noite"}:
            return "Saudações. Sou o Elívea, e estou à sua disposição."

        if "quem é você" in q or "quem e voce" in q or "quem é o grande sabio" in q:
            return "Sou o Elívea, um assistente pessoal que pode responder perguntas, abrir programas, pesquisar na web e executar tarefas no computador."

        if "hora" in q:
            return f"Agora são {self._format_time_now()}."

        if "data" in q:
            return f"Hoje é {self._format_date_now()}."

        if "seu nome" in q:
            return "Meu nome é Elívea."

        if "sistema" in q or "windows" in q or "pc" in q:
            return f"O sistema operacional detectado é {platform.system()} {platform.release()}."

        if "abrir" in q or "execute" in q or "inicie" in q or "abra" in q:
            keywords = [
                "google", "youtube", "chrome", "edge", "firefox", "notepad",
                "bloco de notas", "calculadora", "paint", "pintura", "cmd",
                "prompt", "terminal", "arquivos", "explorer", "vscode",
                "visual studio code", "spotify", "discord", "steam"
            ]
            for keyword in keywords:
                if keyword in q:
                    if self._open_app_by_name(keyword):
                        return f"Abrindo {keyword}."
                    return f"Não consegui abrir {keyword}."

            if "google" in q:
                self._open_url("https://www.google.com")
                return "Abrindo o Google."

            if "youtube" in q:
                self._open_url("https://www.youtube.com")
                return "Abrindo o YouTube."

            return "Posso abrir Google, YouTube, Bloco de Notas, Calculadora, terminal, arquivos e outras aplicações comuns."

        if "pesquisar" in q or "buscar" in q or "procure" in q:
            match = re.search(r"(?:pesquisar|buscar|procure|procura)\s+(.*)", q)
            termo = match.group(1) if match else ""
            if termo:
                url = "https://www.google.com/search?q=" + termo.replace(" ", "+")
                self._open_url(url)
                return f"Pesquisando por {termo} no Google."
            return "Diga o que deseja pesquisar."

        if "desligar" in q or "encerrar" in q or "sair" in q:
            return "Até logo. Saindo do sistema."

        if "comandos" in q or "ajuda" in q or "funções" in q or "funcao" in q:
            return (
                "Posso responder perguntas, dizer a hora e a data, abrir o Google, YouTube, Bloco de Notas, "
                "Calculadora, Paint, arquivos, terminal, Spotify e realizar buscas no navegador."
            )

        if "como" in q and "funciona" in q:
            return "Eu posso interpretar comandos em texto e voz e executar ações no Windows e no navegador."

        return (
            "Não tenho uma resposta exata para isso agora, mas posso ajudá-lo com perguntas gerais, "
            "horas, datas, abrir aplicativos e pesquisar na web."
        )

    def _search_web(self, question: str):
        if requests is None:
            return None

        try:
            endpoint = "https://api.duckduckgo.com/"
            params = {"q": question, "format": "json", "no_html": 1, "skip_disambig": 1}
            response = requests.get(endpoint, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            snippets = []
            abstract = data.get("Abstract")
            if abstract:
                snippets.append(abstract.strip())

            related = data.get("RelatedTopics") or []
            for item in related[:3]:
                if isinstance(item, dict):
                    text = item.get("Text")
                    if text:
                        snippets.append(text.strip())

            if snippets:
                return "\n\n".join(snippets[:4])
            return None
        except Exception:
            return None

    def _call_groq(self, question: str, web_context: str = ""):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or requests is None:
            return None

        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        context = web_context.strip()

        try:
            messages = [{
                "role": "system",
                "content": "Você é o Elívea, um assistente inteligente em português. Responda de forma útil, clara e objetiva. Use o contexto da web quando houver. Se não souber, diga honestamente e ajude o usuário.",
            }]

            if context:
                messages.append({
                    "role": "user",
                    "content": f"Contexto da web:\n{context}\n\nPergunta do usuário:\n{question}",
                })
            else:
                messages.append({"role": "user", "content": question})

            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500,
            }

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            return None

    def _call_ollama(self, question: str):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.1")

        if requests is None:
            return None

        try:
            payload = {"model": model, "prompt": question, "stream": False}
            response = requests.post(f"{base_url}/api/generate", json=payload, timeout=20)
            if response.status_code != 200:
                return None
            data = response.json()
            return data.get("response", "").strip()
        except Exception:
            return None

    def process(self, question: str):
        q = question.strip()
        if not q:
            return "Peço que você formule uma pergunta ou comando."

        if q.lower() in {"sair", "fechar", "encerra", "encerrar", "desligar"}:
            return "encerrar"

        groq_answer = self._call_groq(q)
        if groq_answer:
            return groq_answer

        web_context = self._search_web(q)
        if web_context:
            groq_answer = self._call_groq(q, web_context)
            if groq_answer:
                return groq_answer

        resposta_ollama = self._call_ollama(q)
        if resposta_ollama:
            return resposta_ollama

        return self._local_answer(q)

    def run(self):
        print("=== ELÍVEA ===")
        print("Diga 'sair' para encerrar.")
        while True:
            try:
                command = self.listen()
            except KeyboardInterrupt:
                print("\nEncerrando.")
                break

            if not command:
                continue

            result = self.process(command)
            if result == "encerrar":
                self.speak("Até logo.")
                break

            self.speak(result)


class EliveaGui:
    def __init__(self, root):
        self.root = root
        self.root.title("Elívea")
        self.root.geometry("1000x750")
        self.root.minsize(820, 600)
        self.root.configure(bg="#050505")
        self.root.attributes("-alpha", 0.98)

        self.assistant = Elivea(voice_enabled=True)
        self.orb_anim_job = None
        self.orb_rings = []
        self.orb_particles = []
        self.orb_glow = []
        self.last_input_time = time.time()
        self.animation_frame = 0

        self.top_bar = tk.Frame(root, bg="#000000", height=180)
        self.top_bar.pack(fill="x")

        self.status_panel = tk.Frame(self.top_bar, bg="#000000")
        self.status_panel.pack(fill="x", padx=28, pady=(18, 0))

        self.live_dot = tk.Label(self.status_panel, text="●", bg="#000000", fg="#ffd700", font=("Segoe UI", 14, "bold"))
        self.live_dot.pack(side="left")

        self.live_status = tk.Label(self.status_panel, text=" ORACLE ONLINE", bg="#000000", fg="#ffed4e", font=("Segoe UI", 10, "bold"))
        self.live_status.pack(side="left", padx=(8, 0))

        self.canvas = tk.Canvas(self.top_bar, width=320, height=140, bg="#000000", highlightthickness=0)
        self.canvas.pack(side="left", padx=(30, 8), pady=(8, 10))
        self._build_orb()

        self.title_label = tk.Label(
            self.top_bar,
            text="Elívea",
            bg="#000000",
            fg="#ffd700",
            font=("Segoe UI", 32, "bold"),
            anchor="w",
            justify="left",
        )
        self.title_label.pack(side="left", fill="both", expand=True, padx=(0, 26), pady=(26, 0))

        self.subtitle = tk.Label(
            self.top_bar,
            text="✦ Oracle Intelligence · Autonomous Assistant · Windows Control ✦",
            bg="#000000",
            fg="#daa520",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        )
        self.subtitle.pack(side="bottom", fill="x", padx=(0, 20), pady=(0, 18))

        self.main_panel = tk.Frame(root, bg="#0a0806")
        self.main_panel.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self.chat = ScrolledText(
            self.main_panel,
            wrap="word",
            width=120,
            height=22,
            bg="#0f0c09",
            fg="#ffe680",
            insertbackground="#ffd700",
            font=("Segoe UI", 11),
            state="disabled",
            bd=0,
            relief="flat",
            highlightthickness=2,
            highlightbackground="#daa520",
        )
        self.chat.pack(fill="both", expand=True, padx=16, pady=(16, 12))

        self.input_frame = tk.Frame(self.main_panel, bg="#0a0806")
        self.input_frame.pack(fill="x", padx=16, pady=(0, 14))

        self.entry = tk.Entry(
            self.input_frame,
            font=("Segoe UI", 12),
            bg="#1a1612",
            fg="#fff8dc",
            insertbackground="#ffd700",
            bd=0,
            highlightthickness=2,
            highlightbackground="#daa520",
            relief="flat",
            justify="left",
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=11)
        self.entry.bind("<Return>", self.on_submit)
        self.entry.bind("<KeyRelease>", self.on_typing)

        self.send_button = tk.Button(
            self.input_frame,
            text="SEND",
            command=self.submit_command,
            bg="#ffd700",
            fg="#000000",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            activebackground="#ffed4e",
            activeforeground="#000000",
            padx=20,
            pady=11,
            cursor="hand2",
        )
        self.send_button.pack(side="left", padx=(10, 0))

        self.voice_button = tk.Button(
            self.input_frame,
            text="🎤 VOICE",
            command=self.voice_input,
            bg="#1a1612",
            fg="#ffd700",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            activebackground="#2a2616",
            activeforeground="#ffed4e",
            padx=18,
            pady=11,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground="#daa520",
        )
        self.voice_button.pack(side="left", padx=(10, 0))

        self.status = tk.Label(
            root,
            text="Aguardando palavra de ativação: Elívea",
            bg="#050505",
            fg="#ffed4e",
            font=("Segoe UI", 10, "bold"),
            pady=8,
        )
        self.status.pack(fill="x")

        self.append_message("System", "✦ Elívea está online ✦ Diga 'Elívea' ou 'Sage' para ativar o assistente.")
        self.root.after(100, self._animate_idle)
        self.entry.focus_set()

    def _build_orb(self):
        canvas = self.canvas
        self.orb_particles = []
        self.orb_rings = []

        # Outer glow rings
        self.orb_rings.append(canvas.create_oval(60, 8, 220, 160, outline="#ffed4e", width=3, fill=""))
        self.orb_rings.append(canvas.create_oval(80, 28, 200, 140, outline="#ffd700", width=2, fill=""))
        self.orb_rings.append(canvas.create_oval(100, 48, 180, 120, outline="#ffa500", width=1, fill=""))
        
        # Core orb
        self.orb_core = canvas.create_oval(110, 50, 170, 110, fill="#ffed4e", outline="#ffff99", width=2)
        
        # Inner bright center
        self.orb_center = canvas.create_oval(125, 60, 155, 90, fill="#ffffff", outline="#fffacd", width=1)

        # Mystical particles orbiting the orb
        for x, y in [(40, 30), (240, 30), (250, 80), (35, 90), (70, 10), (210, 130), (140, 5), (140, 155)]:
            particle = canvas.create_oval(x, y, x + 6, y + 6, fill="#ffd700", outline="")
            self.orb_particles.append(particle)

    def _animate_idle(self):
        t = time.time() * 0.8
        self.animation_frame += 1
        
        # Main ring animations with different speeds
        amp1 = 18
        amp2 = 12
        amp3 = 8
        
        ring1_size = amp1 + (math.sin(t * 2.0) * 6)
        ring2_size = amp2 + (math.sin(t * 2.8 + 1.5) * 4)
        ring3_size = amp3 + (math.sin(t * 3.5 + 0.8) * 3)

        # Update rings with smooth pulsing
        for idx, item in enumerate(self.orb_rings):
            if idx == 0:
                x1 = 90 - ring1_size / 2
                y1 = 30 - ring1_size / 2
                x2 = 190 + ring1_size / 2
                y2 = 130 + ring1_size / 2
            elif idx == 1:
                x1 = 100 - ring2_size / 2
                y1 = 40 - ring2_size / 2
                x2 = 180 + ring2_size / 2
                y2 = 120 + ring2_size / 2
            else:
                x1 = 110 - ring3_size / 2
                y1 = 50 - ring3_size / 2
                x2 = 170 + ring3_size / 2
                y2 = 110 + ring3_size / 2
            self.canvas.coords(item, x1, y1, x2, y2)

        # Smooth particle orbital motion
        for idx, particle in enumerate(self.orb_particles):
            angle = t * 1.8 + idx * 0.785
            radius = 50 + math.sin(angle * 1.3 + idx) * 14
            cx = 140 + math.cos(angle + idx * 0.5) * radius
            cy = 75 + math.sin(angle * 1.2 + idx * 0.6) * radius * 0.8
            self.canvas.coords(particle, cx, cy, cx + 6, cy + 6)

        self.root.after(25, self._animate_idle)

    def _trigger_input_anim(self):
        self.last_input_time = time.time()
        for item in self.orb_rings:
            self.canvas.itemconfigure(item, outline="#ffff99")
        self.root.after(200, self._restore_orb_palette)

    def _restore_orb_palette(self):
        self.canvas.itemconfigure(self.orb_rings[0], outline="#ffed4e")
        self.canvas.itemconfigure(self.orb_rings[1], outline="#ffd700")
        self.canvas.itemconfigure(self.orb_rings[2], outline="#ffa500")

    def append_message(self, sender: str, text: str):
        self.chat.configure(state="normal")
        self.chat.insert(tk.END, f"{sender}: {text}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see(tk.END)

    def on_typing(self, _event=None):
        self._trigger_input_anim()

    def submit_command(self):
        command = self.entry.get().strip()
        if not command:
            return
        self.entry.delete(0, tk.END)
        self.append_message("Você", command)
        self.status.configure(text="Processando...")
        self._trigger_input_anim()

        response = self.assistant.process(command)
        if response == "encerrar":
            self.append_message("Elívea", "Até logo.")
            self.status.configure(text="Sistema finalizado")
            self.root.after(600, self.root.destroy)
            return

        self.append_message("Elívea", response)
        self.status.configure(text="Pronto para atender")

    def on_submit(self, _event=None):
        self.submit_command()

    def voice_input(self):
        self.append_message("Elívea", "Aguardando a palavra de ativação...")

        def _listen():
            try:
                text = self.assistant.wait_for_wake_word()
                if text:
                    self.root.after(0, self.append_message, "Elívea", "Ativado. Diga seu comando.")
                    self.root.after(0, self.status.configure, "text", "Ativado · ouvindo comando")
                    self.root.after(0, self.entry.focus_set)
                    recognized = self.assistant.listen()
                    if recognized:
                        self.root.after(0, self.entry.delete, 0, tk.END)
                        self.root.after(0, self.entry.insert, 0, recognized)
                        self.root.after(0, self.submit_command)
                    else:
                        self.root.after(0, self.append_message, "Elívea", "Não consegui capturar o comando. Tente novamente.")
                        self.root.after(0, self.status.configure, "text", "Aguardando palavra de ativação: Elívea")
                else:
                    self.root.after(0, self.append_message, "Elívea", "Não foi possível ativar por voz neste ambiente.")
                    self.root.after(0, self.status.configure, "text", "Aguardando palavra de ativação: Elívea")
            except Exception as exc:
                self.root.after(0, self.append_message, "Elívea", f"Não consegui ouvir: {exc}")
                self.root.after(0, self.status.configure, "text", "Aguardando palavra de ativação: Elívea")

        t = threading.Thread(target=_listen, daemon=True)
        t.start()


def main():
    if tk is None:
        print("Tkinter não está disponível neste ambiente.")
        return

    if "--voz" in sys.argv or "-v" in sys.argv:
        voice_enabled = True
    else:
        voice_enabled = False

    root = tk.Tk()
    root.iconbitmap(default=None)
    root.configure(bg="#040b12")
    gui = EliveaGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
