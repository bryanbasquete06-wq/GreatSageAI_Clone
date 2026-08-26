import asyncio
import ctypes
import os
import edge_tts

async def speak_neural(text: str, voice: str = "pt-BR-AntonioNeural"):
    mp3_file = "great_sage_voice.mp3"
    c = edge_tts.Communicate(text, voice)
    await c.save(mp3_file)
    
    # Play using Windows MCI
    ctypes.windll.winmm.mciSendStringW(f'open "{mp3_file}" type mpegvideo alias mp3', None, 0, 0)
    ctypes.windll.winmm.mciSendStringW('play mp3 wait', None, 0, 0)
    ctypes.windll.winmm.mciSendStringW('close mp3', None, 0, 0)

if __name__ == "__main__":
    asyncio.run(speak_neural("Voz neural do Grande Sábio inicializada para o Mestre Bryan."))
