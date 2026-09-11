# 🛡️ AUDIO SHIELD • DSP Phase Cloaker Engine (Standalone)

Aplicação web executiva independente para automação de cancelamento de fase estéreo e camuflagem acústica anti-Content ID.

---

## 🚀 Como Executar Localmente
Dê um duplo clique no arquivo:
👉 **`INICIAR_AUDIO_SHIELD.bat`**

O servidor iniciará automaticamente em **`http://localhost:8090`** e abrirá no seu navegador.

---

## 🌐 Como Subir em um Domínio Próprio (Ex: shield.suaempresa.com)

Esta aplicação foi configurada como um microsserviço com **`Dockerfile`**, o que significa que o FFmpeg e o Python já vêm instalados automaticamente em qualquer servidor de nuvem.

### Passo 1: Criar Repositório no GitHub
1. Crie um novo repositório no seu GitHub (ex: `audio-shield-web`).
2. No terminal dentro desta pasta, execute:
   ```bash
   git remote add origin https://github.com/SEU_USUARIO/audio-shield-web.git
   git branch -M main
   git push -u origin main
   ```

### Passo 2: Publicar no Render
1. Acesse **[render.com](https://render.com)**.
2. Clique em **New +** > **Web Service**.
3. Conecte com o repositório `audio-shield-web`.
4. O Render detectará automaticamente o **Dockerfile**. Basta clicar em **Deploy Web Service**.

### Passo 3: Apontar o Domínio Personalizado
1. No painel do seu serviço no Render, vá em **Settings** > **Custom Domains**.
2. Digite o domínio ou subdomínio que desejar (ex: `shield.minhaempresa.com`).
3. No seu registrador de domínio (Cloudflare, GoDaddy, Registro.br), crie o apontamento **CNAME** indicado pelo Render.
4. Pronto! O SSL (HTTPS) é gerado automaticamente e o seu chefe poderá acessar diretamente pela URL da sua empresa.
