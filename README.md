# 🛡️ Cyber Hunter Lab — Security Research & AI Platform

> **Plataforma Open Source de Pesquisa em Segurança Ofensiva & Defensiva, Inteligência Artificial e Agente Autônomo (ReAct).**

---

## 📌 Sobre o Projeto

O **Cyber Hunter Lab** é uma solução completa e moderna que une análise de segurança cibernética a modelos de linguagem de ponta. A plataforma conta com:

1. **Interface de Chat com IA** com suporte a raciocínio em tempo real (*Chain of Thought* expansível / `<think>`), renderização Markdown avançada, streaming em tempo real e visualização limpa de código.
2. **Agente Autônomo ReAct** para automação de tarefas investigativas, análise de vulnerabilidades, varreduras de rede e geração de relatórios técnicos.
3. **Suporte Híbrido a Modelos**:
   - **Local via Ollama**: Totalmente offline e privado (`deepseek-r1:8b`, `pentest-raw`, `qwen3-coder:30b`, `huihui_ai/qwen3-abliterated:8b`, `llama3.2-vision:11b`).
   - **Cloud via NVIDIA NIM**: Acesso a modelos de altíssima escala e inferência acelerada (`deepseek-v4-pro`, `kimi-k3`, `nemotron-3-ultra-550b`, `glm-5.3-flash`, `llama-3.2-11b-vision`).

---

## ⚡ Funcionalidades Principais

- 💬 **Chat em Tempo Real**: Streaming assíncrono via SSE (*Server-Sent Events*) com suporte a blocos de código com destaque de sintaxe e botão de cópia com 1 clique.
- 🧠 **Painel de Raciocínio (Deep Think)**: Caixas retráteis com o processo de pensamento das IAs que suportam raciocínio detalhado (como DeepSeek-R1).
- 🤖 **Agente de Segurança Autônomo**: Loop iterativo ReAct (*Thought → Action → Observation → Answer*) para diagnosticar e investigar requisições de segurança.
- 📱 **Interface 100% Responsiva**: Otimizada para navegadores desktop e dispositivos móveis, sem vazamento de texto ou quebra de layout.
- 🎛️ **Seletor Dinâmico de Modelos**: Alternância instantânea entre instâncias locais (Ollama) e em nuvem (NVIDIA NIM).
- 🎙️ **Reconhecimento de Voz**: Entrada por comando de voz integrada para facilidade de uso em campo.
- 🛡️ **Foco em Segurança**: Desenvolvido sob princípios de segurança da informação e pesquisa ética de vulnerabilidades.

---

## 🏗️ Arquitetura do Sistema

```
cyber-hunter-lab/
├── index.html        # Frontend SPA completo (Tailwind CSS, Marked.js, Áudio, Mobile-First)
├── server.py         # Backend assíncrono FastAPI (Rotas /api/chat, /api/agent, /api/models, Ollama + NVIDIA)
├── package.json      # Configurações de frontend e scripts Vite
├── .env.example      # Modelo de variáveis de ambiente
└── README.md         # Documentação e termos de licença
```

---

## 🚀 Como Executar Localmente

### Pré-requisitos
- **Python 3.10+** instalado
- **Node.js 18+** (opcional para desenvolvimento Vite)
- **Ollama** instalado e em execução (para modelos locais):
  ```bash
  ollama serve
  ollama pull deepseek-r1:8b
  ```

### 1. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/cyber-hunter-lab.git
cd cyber-hunter-lab
```

### 2. Configurar o Ambiente Python
```bash
python3 -m venv venv
source venv/bin/activate   # No Windows: venv\Scripts\activate
pip install fastapi uvicorn httpx pydantic
```

### 3. Configurar Variáveis de Ambiente
Crie ou edite o arquivo `.env` com base no `.env.example`:

```env
# Configurações do Ollama (Local)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:8b

# Configurações da NVIDIA NIM (Opcional para modelos em nuvem)
NVIDIA_API_KEY=sua_chave_nvidia_nim_aqui
NVIDIA_URL=https://integrate.api.nvidia.com/v1
```

### 4. Iniciar o Servidor
```bash
# Executando o backend FastAPI (Porta 3000 ou 8000)
python3 server.py
# Ou via uvicorn:
uvicorn server:app --host 0.0.0.0 --port 3000 --reload
```

Abra no navegador em `http://localhost:3000`.

---

## 🌐 Integração com Modelos

| Provedor | Modelo | Tipo | Uso Recomendado |
| :--- | :--- | :--- | :--- |
| **Ollama (Local)** | `deepseek-r1:8b` | Raciocínio / CoT | Análise lógica, engenharia reversa, análise de código |
| **Ollama (Local)** | `pentest-raw` | Segurança | Comandos técnicos, enumeração e auditoria |
| **Ollama (Local)** | `qwen3-coder:30b` | Código / Scripting | Desenvolvimento de exploits e automação de scripts |
| **NVIDIA NIM** | `deepseek-v4-pro` | Cloud API | Tarefas complexas de alto desempenho |
| **NVIDIA NIM** | `nemotron-3-ultra` | Cloud API | Raciocínio analítico avançado e geração de relatórios |

---

## 📜 Licença e Termos de Código Aberto

Este projeto é um **software de código aberto (Open Source)**.

### Termos de Uso e Modificação:
- ✅ **Livre para Usar**: Você tem total liberdade para clonar, estudar, executar e utilizar este software para fins educacionais, pessoais ou profissionais.
- ✅ **Livre para Modificar**: Qualquer pessoa pode alterar, adaptar, adicionar novos recursos, criar forks ou redistribuir este projeto.
- ⚠️ **Manutenção Obrigatória de Créditos**: A única exigência obrigatória para qualquer redistribuição, modificação ou publicação derivada é **manter intactos todos os créditos originais do autor**.

```
Copyright (c) 2025-2026 Cyber Hunter Lab.
Desenvolvido por: Cyber Hunter Lab / Autor Original

É concedida permissão a qualquer pessoa que obtenha uma cópia deste software 
para utilizá-lo, modificá-lo e distribuí-lo livremente, sob a condição de que 
o aviso de direitos autorais acima e esta nota de crédito sejam preservados 
em todas as cópias ou partes substanciais do software.
```

---

## 🤝 Contribuições

Contribuições da comunidade de cibersegurança e desenvolvedores de IA são sempre bem-vindas! Sinta-se à vontade para abrir uma *Issue* ou enviar um *Pull Request*, respeitando as diretrizes de código aberto e atribuição de créditos.
