# Como Distribuir o Elívea AI

## Passo 1: Subir o código no GitHub

```bash
cd "F:\programação\J.A.R.V.I.S\EliveaAI_Clone"

# Criar repo no GitHub (substitua SEU_USER pelo seu usuário)
# Vá em https://github.com/new e crie o repo "EliveaAI_Clone"

# Adicionar remote e enviar
git remote add origin https://github.com/SEU_USER/EliveaAI_Clone.git
git branch -M main
git push -u origin main
```

## Passo 2: Atualizar o instalador

Abra `Instalador_Elivea.py` e substitua:
```python
GITHUB_REPO = "https://github.com/SEU_USER/EliveaAI_Clone"
GITHUB_API = "https://api.github.com/repos/SEU_USER/EliveaAI_Clone/releases/latest"
```

## Passo 3: Compilar o .exe

```bash
cd "F:\programação\J.A.R.V.I.S\EliveaAI_Clone"
build_installer.bat
```

O .exe será gerado em: `dist\Instalador_Elivea.exe`

## Passo 4: Enviar para alguém

### Opção A: Arquivo direto
- Envie `dist\Instalador_Elivea.exe` por WhatsApp, Discord, Email, etc.
- A pessoa executa e a IA é baixada automaticamente

### Opção B: Link de download
- Crie uma Release no GitHub:
  ```bash
  git tag v1.0
  git push origin v1.0
  ```
- Vá em https://github.com/SEU_USER/EliveaAI_Clone/releases/new
- Adicione o .exe como asset
- Compartilhe o link da release

### Opção C: Pendrive
- Copie o .exe para um pendrive
- A pessoa executa direto do pendrive

## O que a pessoa precisa ter

- **Internet** (para baixar a IA e dependências)
- **Windows 10/11**
- O instalador cuida de TUDO automaticamente:
  1. Instala Python (se não tiver)
  2. Baixa a IA do GitHub
  3. Instala dependências
  4. Configura API keys
  5. Cria atalhos
  6. Inicia a IA

## O que a pessoa precisa fazer

1. Executar `Instalador_Elivea.exe`
2. Seguir o assistente (6 passos simples)
3. Colar a chave de API do Groq (gratuita, sem cartão)
4. Pronto! A IA já fala e ouve

## Obter chave de API (gratuita)

A pessoa precisa de uma chave de API para a IA funcionar:

1. Acesse: https://console.groq.com/keys
2. Crie uma conta gratuita
3. Clique em "Create API Key"
4. Copie a chave (começa com `gsk_`)
5. Cole no assistente de instalação

**Não precisa de cartão de crédito!**
