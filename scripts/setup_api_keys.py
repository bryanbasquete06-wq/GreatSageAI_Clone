# -*- coding: utf-8 -*-
"""
Great Sage AI — Configurador de Chaves API
Execute: py setup_api_keys.py
"""
import os
import sys

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, ".env")

PROVIDERS = [
    {
        "name": "Groq",
        "env": "GROQ_API_KEY",
        "url": "https://console.groq.com/keys",
        "desc": "Ultra-rapido, 14.400 req/dia",
    },
    {
        "name": "Google Gemini",
        "env": "GOOGLE_API_KEY",
        "url": "https://aistudio.google.com/apikey",
        "desc": "1.500 req/dia, 1M contexto",
    },
    {
        "name": "OpenRouter",
        "env": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "desc": "50+ modelos free",
    },
    {
        "name": "GitHub Models",
        "env": "GITHUB_TOKEN",
        "url": "https://github.com/settings/tokens",
        "desc": "GPT-4o, Grok-3, o3-mini gratis",
    },
    {
        "name": "xAI (Grok)",
        "env": "XAI_API_KEY",
        "url": "https://console.x.ai",
        "desc": "$25 creditos gratis, Grok-4",
    },
    {
        "name": "NVIDIA NIM",
        "env": "NVIDIA_API_KEY",
        "url": "https://build.nvidia.com",
        "desc": "125 modelos, 40 RPM",
    },
    {
        "name": "Cerebras",
        "env": "CEREBRAS_API_KEY",
        "url": "https://cloud.cerebras.ai",
        "desc": "1M tokens/dia, ultra-rapido",
    },
    {
        "name": "Zhipu AI (GLM)",
        "env": "ZHIPUAI_API_KEY",
        "url": "https://open.bigmodel.cn",
        "desc": "GLM-4 Flash gratis, sem limite",
    },
    {
        "name": "HuggingFace",
        "env": "HUGGINGFACE_API_KEY",
        "url": "https://huggingface.co/settings/tokens",
        "desc": "300+ modelos community",
    },
    {
        "name": "DeepSeek",
        "env": "DEEPSEEK_API_KEY",
        "url": "https://platform.deepseek.com",
        "desc": "5M tokens gratis, Chat+Reasoner",
    },
    {
        "name": "Alibaba (Qwen)",
        "env": "DASHSCOPE_API_KEY",
        "url": "https://dashscope.console.aliyun.com",
        "desc": "Qwen-2.5 gratuito",
    },
    {
        "name": "SambaNova",
        "env": "SAMBANOVA_API_KEY",
        "url": "https://cloud.sambanova.ai",
        "desc": "70B free, rapido",
    },
    {
        "name": "AI21 Labs",
        "env": "AI21_API_KEY",
        "url": "https://www.ai21.com",
        "desc": "$10 creditos gratis, 3 meses",
    },
    {
        "name": "Reka",
        "env": "REKA_API_KEY",
        "url": "https://reka.ai",
        "desc": "$10/mes gratis",
    },
    {
        "name": "Mistral",
        "env": "MISTRAL_API_KEY",
        "url": "https://console.mistral.ai",
        "desc": "Small/Large/Codestral free",
    },
    {
        "name": "Together AI",
        "env": "TOGETHER_API_KEY",
        "url": "https://api.together.xyz",
        "desc": "$25 creditos gratis",
    },
    {
        "name": "SiliconFlow",
        "env": "SILICONFLOW_API_KEY",
        "url": "https://cloud.siliconflow.cn",
        "desc": "Open-source models gratis",
    },
    {
        "name": "Fireworks AI",
        "env": "FIREWORKS_API_KEY",
        "url": "https://fireworks.ai",
        "desc": "Creditos gratis",
    },
    {
        "name": "Cohere",
        "env": "COHERE_API_KEY",
        "url": "https://dashboard.cohere.com",
        "desc": "Command R free",
    },
]


def load_env():
    keys = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys


def save_env(keys):
    lines = [
        "# Great Sage AI — Chaves de API (gerado pelo setup_api_keys.py)",
        "# Todas as chaves sao gratuitas — NENHUM cartao de credito necessario",
        "",
    ]

    written = set()
    for p in PROVIDERS:
        env = p["env"]
        if env in keys and keys[env]:
            lines.append(f"{env}={keys[env]}")
            written.add(env)

    for k, v in sorted(keys.items()):
        if k not in written and v:
            lines.append(f"{k}={v}")

    lines.append("")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("=" * 60)
    print("   GREAT SAGE AI — CONFIGURADOR DE CHAVES API")
    print("   Todas as chaves sao 100% GRATUITAS")
    print("   NENHUM cartao de credito necessario")
    print("=" * 60)
    print()

    keys = load_env()
    existing = sum(1 for p in PROVIDERS if keys.get(p["env"]))
    print(f"  Chaves ja configuradas: {existing}/{len(PROVIDERS)}")
    print()

    changed = False

    for i, p in enumerate(PROVIDERS, 1):
        env = p["env"]
        current = keys.get(env, "")
        status = " [OK]" if current else ""

        print("-" * 60)
        print(f"  [{i}/{len(PROVIDERS)}] {p['name']}{status}")
        print(f"  {p['desc']}")
        print(f"  Pegue em: {p['url']}")
        if current:
            masked = current[:8] + "..." + current[-4:] if len(current) > 12 else "***"
            print(f"  Chave atual: {masked}")
        print()

        val = input(f"  Cole a chave (Enter para pular): ").strip()
        if val:
            keys[env] = val
            changed = True
            print(f"  -> Salva!")
        elif not current:
            print(f"  -> Pulado")
        else:
            print(f"  -> Mantida")

        print()

    if changed:
        save_env(keys)
        print("=" * 60)
        print("  Chaves salvas em .env!")
    else:
        print("=" * 60)
        print("  Nenhuma chave alterada.")

    configured = sum(1 for p in PROVIDERS if keys.get(p["env"]))
    print(f"  Total configuradas: {configured}/{len(PROVIDERS)}")
    print()
    print("  Para iniciar o Great Sage AI:")
    print("    py main.py")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelado.")
        sys.exit(0)
