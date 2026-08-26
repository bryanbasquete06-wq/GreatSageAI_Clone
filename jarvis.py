import os
import subprocess
import sys
import webbrowser
from datetime import datetime

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None


class Jarvis:
    def __init__(self):
        self.engine = None
        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
            except Exception:
                self.engine = None

    def speak(self, text: str):
        print(f"Jarvis: {text}")
        if self.engine is not None:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception:
                pass

    def listen(self):
        if sr is None:
            return input("Você: ").strip().lower()

        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("Ouvindo...")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio, language="pt-BR")
            print(f"Você disse: {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("Não entendi a sua fala.")
            return ""
        except sr.RequestError:
            print("Erro no serviço de reconhecimento de voz.")
            return ""

    def open_website(self, url: str):
        webbrowser.open(url)
        self.speak(f"Abrindo {url}")

    def handle_command(self, command: str):
        if not command:
            return True

        if command in {"oi", "olá", "bom dia", "boa tarde", "boa noite"}:
            self.speak("Olá, senhor. Como posso ajudar?")
            return True

        if "hora" in command:
            now = datetime.now().strftime("%H:%M")
            self.speak(f"Agora são {now}")
            return True

        if "data" in command:
            today = datetime.now().strftime("%d/%m/%Y")
            self.speak(f"Hoje é {today}")
            return True

        if "google" in command:
            self.open_website("https://www.google.com")
            return True

        if "youtube" in command:
            self.open_website("https://www.youtube.com")
            return True

        if "explorer" in command or "arquivo" in command:
            os.startfile(os.path.expanduser("~"))
            self.speak("Abrindo o explorador de arquivos.")
            return True

        if "sair" in command or "fechar" in command:
            self.speak("Sistema encerrado. Até logo.")
            return False

        if "lista" in command or "comandos" in command:
            self.speak(
                "Posso dizer a hora, abrir o Google, abrir o YouTube, abrir arquivos e encerrar o sistema."
            )
            return True

        self.speak("Comando não reconhecido. Posso buscar hora, abrir sites ou encerrar o sistema.")
        return True

    def run(self):
        self.speak("Jarvis inicializado. Pronto para atender.")
        while True:
            command = self.listen()
            if not self.handle_command(command):
                break


if __name__ == "__main__":
    jarvis = Jarvis()
    jarvis.run()
