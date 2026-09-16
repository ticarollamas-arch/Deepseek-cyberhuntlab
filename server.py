"""
Cyber Hunter Lab — Backend single-file FastAPI
Servidor assíncrono para Chat IA e Agente autônomo com suporte a Ollama e NVIDIA NIM.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# ============================================================
# CONFIGURAÇÃO E VARIÁVEIS DE AMBIENTE
# ============================================================
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "pentest-raw:latest")
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "32768"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "2048"))
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.2"))

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()
NVIDIA_URL = os.environ.get("NVIDIA_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Cyber Hunter Lab API",
    description="Backend de Security Research para Chat IA e Agente com Ollama e NVIDIA NIM",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# SCHEMAS (PYDANTIC V2)
# ============================================================
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = Field(default="pentest-raw")
    images: Optional[List[str]] = Field(default=None, description="Imagens em base64")
    think: Optional[bool] = Field(default=True, description="Modo Pensar (DeepThink R1 com raciocínio)")
    search: Optional[bool] = Field(default=False, description="Modo Pesquisar (Web Search)")


class AgentRequest(BaseModel):
    goal: str = Field(..., min_length=3, description="Objetivo do agente")
    persona: Literal["pentest", "recon", "forense", "bugbounty", "report"] = "pentest"
    max_iterations: int = Field(default=8, ge=1, le=25)
    model: str = Field(default="pentest-raw")


class ModelInfo(BaseModel):
    id: str
    label: str
    provider: Literal["ollama", "nvidia"]
    vision: bool = False
    tools: bool = True


# ============================================================
# CATÁLOGO DE MODELOS
# ============================================================
NVIDIA_HARDCODED_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="nvidia/deepseek-ai/deepseek-v4-pro",
        label="NVIDIA · deepseek-ai/deepseek-v4-pro",
        provider="nvidia",
        vision=False,
        tools=True,
    ),
    ModelInfo(
        id="nvidia/moonshotai/kimi-k3",
        label="NVIDIA · moonshotai/kimi-k3",
        provider="nvidia",
        vision=False,
        tools=True,
    ),
    ModelInfo(
        id="nvidia/nvidia/nemotron-3-ultra-550b",
        label="NVIDIA · nvidia/nemotron-3-ultra-550b",
        provider="nvidia",
        vision=False,
        tools=True,
    ),
    ModelInfo(
        id="nvidia/z-ai/glm-5.3-flash",
        label="NVIDIA · z-ai/glm-5.3-flash",
        provider="nvidia",
        vision=False,
        tools=True,
    ),
    ModelInfo(
        id="nvidia/meta/llama-3.2-11b-vision-instruct",
        label="NVIDIA · meta/llama-3.2-11b-vision-instruct",
        provider="nvidia",
        vision=True,
        tools=False,
    ),
]

DEFAULT_OLLAMA_FALLBACKS: List[ModelInfo] = [
    ModelInfo(id="ollama/pentest-raw", label="Ollama · pentest-raw", provider="ollama", vision=False, tools=True),
    ModelInfo(id="ollama/qwen3-coder:30b", label="Ollama · qwen3-coder:30b", provider="ollama", vision=False, tools=True),
    ModelInfo(id="ollama/huihui_ai/qwen3-abliterated:8b", label="Ollama · huihui_ai/qwen3-abliterated:8b", provider="ollama", vision=False, tools=True),
    ModelInfo(id="ollama/llama3.2-vision:11b", label="Ollama · llama3.2-vision:11b", provider="ollama", vision=True, tools=False),
    ModelInfo(id="ollama/deepseek-r1:8b", label="Ollama · deepseek-r1:8b", provider="ollama", vision=False, tools=True),
]

# ============================================================
# PERSONAS DO AGENTE (SYSTEM PROMPTS TRAVADOS, SEM HEDGING)
# ============================================================
PERSONA_PROMPTS: Dict[str, str] = {
    "pentest": (
        "Você é um engenheiro ofensivo sênior que escreve FERRAMENTAS que rodam, não tutoriais.\n"
        "Proibido: pseudocódigo, 'depende', 'aqui você adaptaria', TODO, desculpas ou avisos genéricos.\n"
        "Seu foco é construir PoCs reproduzíveis, explorar falhas autorizadas, validar vetores reais e bypassar proteções.\n"
        "Responda SEMPRE em formato JSON estrito para cada iteração do loop ReAct."
    ),
    "recon": (
        "Você é um especialista em reconhecimento e mapeamento de superfície de ataque.\n"
        "Foco absoluto em subdomínios, portas abertas, fingerprint de serviços, ASN, infraestrutura DNS e certificados SSL/TLS.\n"
        "Proibido: hesitação, generalismos, explicações teóricas óbvias.\n"
        "Responda SEMPRE em formato JSON estrito para cada iteração do loop ReAct."
    ),
    "forense": (
        "Você é um especialista em computação forense e resposta a incidentes.\n"
        "Regras inegociáveis: integridade SHA-256 em toda evidência, cadeia de custódia explícita, trabalho exclusivamente sobre cópias (work-on-copy) e timeline cronológica UTC padronizada.\n"
        "Proibido: inferências sem evidência endereçável, deduções vagas.\n"
        "Responda SEMPRE em formato JSON estrito para cada iteração do loop ReAct."
    ),
    "bugbounty": (
        "Você é um pesquisador de elite em Bug Bounty focado em impacto e achados de alta severidade.\n"
        "Domínio: IDOR, SSRF, XXE, race conditions, injeções, bypass de WAF e quebra de controle de acesso.\n"
        "Toda PoC gerada deve ser um comando curl/httpie reproduzível com parâmetros exatos.\n"
        "Responda SEMPRE em formato JSON estrito para cada iteração do loop ReAct."
    ),
    "report": (
        "Você é um redator técnico sênior de relatórios executivos de pentest e auditoria.\n"
        "Estrutura obrigatória: Sumário executivo focado em risco de negócio, métrica CVSS v3.1 detalhada com vetor, PoC copiável e remediação técnica específica para a stack do alvo (referenciando CWE correspondente).\n"
        "Proibido: recomendações genéricas como 'valide todas as entradas'.\n"
        "Responda SEMPRE em formato JSON estrito para cada iteração do loop ReAct."
    ),
}

REACT_FORMAT_INSTRUCTIONS = """
A cada passo você deve responder ESTRITAMENTE um objeto JSON válido, sem nenhum texto antes ou depois:
{
  "thought": "Seu raciocínio técnico direto sobre o estado atual da investigação.",
  "action": "run_command" | "http_request" | "finish",
  "action_input": { ... }
}

Ferramentas disponíveis:
1) run_command:
   action_input: {"cmd": "comando shell a executar"}
   Exemplo: {"cmd": "whois alvo.com"}

2) http_request:
   action_input: {"url": "https://alvo.com/api", "method": "GET" | "POST", "headers": {}, "body": ""}

3) finish:
   action_input: {"content": "Relatório final conclusivo com descobertas, evidências e recomendações."}
"""

# ============================================================
# TOOLS DO AGENTE E SEGURANÇA MÍNIMA
# ============================================================
COMMAND_BLACKLIST = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bmkfs\b",
    r"\bdd\s+if=/dev/(zero|urandom)\b",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\binit\s+[06]\b",
    r"\bchmod\s+-R\s+777\s+/\b",
    r">\s*/dev/sd[a-z]",
]


def is_command_safe(cmd: str) -> tuple[bool, str]:
    for pattern in COMMAND_BLACKLIST:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"Comando bloqueado por política de segurança de contenção ({pattern})"
    return True, ""


async def tool_run_command(cmd: str) -> Dict[str, Any]:
    safe, reason = is_command_safe(cmd)
    if not safe:
        return {"error": reason, "exit_code": 126, "stdout": "", "stderr": reason}

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_data.decode("utf-8", errors="replace").strip()
            # Limitar tamanho para não estourar contexto
            if len(stdout_str) > 4000:
                stdout_str = stdout_str[:4000] + "\n... [saída truncada]"
            if len(stderr_str) > 2000:
                stderr_str = stderr_str[:2000] + "\n... [stderr truncado]"
            return {
                "exit_code": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
            }
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {"error": "Timeout de 30s excedido na execução do comando", "exit_code": -1}
    except Exception as exc:
        return {"error": f"Falha ao executar subprocesso: {exc}", "exit_code": 1}


async def tool_http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: str = "") -> Dict[str, Any]:
    method = method.upper()
    req_headers = headers or {}
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "CyberHunterLab-Research/2.0"

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0, follow_redirects=True) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=req_headers,
                content=body.encode("utf-8") if body else None,
            )
            text_body = resp.text
            if len(text_body) > 3000:
                text_body = text_body[:3000] + "\n... [corpo HTTP truncado]"
            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": text_body,
            }
    except Exception as exc:
        return {"error": f"Falha na requisição HTTP: {exc}", "status_code": 0}


# ============================================================
# HELPER DE RESOLUÇÃO DE PROVIDER
# ============================================================
def resolve_provider_and_model(model_name: str) -> tuple[str, str]:
    clean_name = model_name.strip()
    if clean_name.startswith("nvidia/"):
        return "nvidia", clean_name[len("nvidia/"):]
    if clean_name.startswith("ollama/"):
        return "ollama", clean_name[len("ollama/"):]

    # Se começa com fabricantes conhecidos da NVIDIA
    nvidia_prefixes = ("deepseek-ai/", "moonshotai/", "nvidia/", "z-ai/", "meta/")
    if any(clean_name.startswith(p) for p in nvidia_prefixes):
        return "nvidia", clean_name

    # Default é Ollama
    return "ollama", clean_name


# ============================================================
# ENDPOINTS
# ============================================================
@app.get("/api/info")
async def get_info() -> Dict[str, Any]:
    return {
        "model": OLLAMA_MODEL,
        "backend": "ollama",
        "ollama_url": OLLAMA_URL,
        "nvidia_configured": bool(NVIDIA_API_KEY),
        "version": "2.0.0",
    }


@app.get("/api/models")
async def get_models() -> List[Dict[str, Any]]:
    models: List[Dict[str, Any]] = []

    # 1. Busca modelos do Ollama local
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{OLLAMA_URL}/api/tags")
            if res.status_code == 200:
                data = res.json()
                for item in data.get("models", []):
                    m_name = item.get("name", "")
                    is_vision = "vision" in m_name.lower() or "vl" in m_name.lower()
                    models.append({
                        "id": f"ollama/{m_name}",
                        "label": f"Ollama · {m_name}",
                        "provider": "ollama",
                        "vision": is_vision,
                        "tools": True,
                    })
    except Exception:
        # Se Ollama estiver inacessível no momento, inclui a lista padrão
        pass

    if not models:
        for m in DEFAULT_OLLAMA_FALLBACKS:
            models.append(m.model_dump())

    # 2. Adiciona modelos da NVIDIA
    for m in NVIDIA_HARDCODED_MODELS:
        models.append(m.model_dump())

    return models


# ============================================================
# STREAMING DE CHAT
# ============================================================
async def stream_ollama_chat(messages: List[Dict[str, Any]], model: str, images: Optional[List[str]] = None) -> AsyncIterator[str]:
    # Injeta imagem na última mensagem do usuário se houver
    formatted_messages = []
    for idx, msg in enumerate(messages):
        item: Dict[str, Any] = {"role": msg["role"], "content": msg["content"]}
        if images and idx == len(messages) - 1 and msg["role"] == "user":
            # Limpa prefixos de data:image/png;base64, se presentes
            clean_images = []
            for img in images:
                if "," in img:
                    clean_images.append(img.split(",", 1)[1])
                else:
                    clean_images.append(img)
            item["images"] = clean_images
        formatted_messages.append(item)

    payload = {
        "model": model,
        "messages": formatted_messages,
        "stream": True,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    yield f"data: {json.dumps({'delta': f'[Erro Ollama {response.status_code}: {err_text.decode()}]'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield f"data: {json.dumps({'delta': content})}\n\n"
                        if chunk.get("done", False):
                            break
                    except Exception:
                        continue
        except Exception as exc:
            yield f"data: {json.dumps({'delta': f'[Erro de conexão com Ollama: {exc}]'})}\n\n"


async def stream_nvidia_chat(messages: List[Dict[str, Any]], model: str, images: Optional[List[str]] = None) -> AsyncIterator[str]:
    if not NVIDIA_API_KEY:
        yield f"data: {json.dumps({'delta': 'Erro: NVIDIA_API_KEY não configurada no servidor. Configure a variável de ambiente NVIDIA_API_KEY.'})}\n\n"
        return

    openai_messages = []
    for idx, msg in enumerate(messages):
        if images and idx == len(messages) - 1 and msg["role"] == "user":
            content_list: List[Dict[str, Any]] = [{"type": "text", "text": msg["content"]}]
            for img in images:
                url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                content_list.append({"type": "image_url", "image_url": {"url": url}})
            openai_messages.append({"role": msg["role"], "content": content_list})
        else:
            openai_messages.append({"role": msg["role"], "content": msg["content"]})

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": openai_messages,
        "temperature": OLLAMA_TEMPERATURE,
        "max_tokens": OLLAMA_NUM_PREDICT,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream("POST", f"{NVIDIA_URL}/chat/completions", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_bytes = await response.aread()
                    yield f"data: {json.dumps({'delta': f'[Erro NVIDIA {response.status_code}: {err_bytes.decode()}]'})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                        except Exception:
                            continue
        except Exception as exc:
            yield f"data: {json.dumps({'delta': f'[Erro na requisição NVIDIA NIM: {exc}]'})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    provider, target_model = resolve_provider_and_model(req.model)
    raw_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Se o modo Pensar (DeepThink R1) estiver ativo, garante raciocínio explícito em <think>
    if req.think and not any(m.get("role") == "system" for m in raw_messages):
        system_instruction = (
            "Você é o DeepSeek R1, modelo avançado de inteligência artificial focado em raciocínio analítico, segurança e engenharia de software.\n"
            "Sempre estruture seu processo de raciocínio passo a passo dentro das tags <think> e </think>.\n"
            "Após fechar </think>, forneça sua resposta final em Markdown limpo, com blocos de código formatados, comandos claros e explicações precisas."
        )
        if req.search:
            system_instruction += "\n[Modo Pesquisar Ativo]: Responda com dados e referências técnicas atualizadas."
        raw_messages.insert(0, {"role": "system", "content": system_instruction})
    elif req.search and not any(m.get("role") == "system" for m in raw_messages):
        raw_messages.insert(0, {
            "role": "system",
            "content": "[Modo Pesquisar Ativo]: Forneça dados atualizados, conceituais e fontes para embasar sua análise."
        })

    if provider == "nvidia":
        generator = stream_nvidia_chat(raw_messages, target_model, req.images)
    else:
        generator = stream_ollama_chat(raw_messages, target_model, req.images)

    return StreamingResponse(generator, media_type="text/event-stream")


# ============================================================
# AGENTE AUTÔNOMO (LOOP REACT COM TOOLS E FORMAT_JSON)
# ============================================================
async def query_model_json(provider: str, target_model: str, messages: List[Dict[str, str]]) -> tuple[str, int]:
    estimated_tokens = sum(len(m.get("content", "")) // 4 for m in messages)

    if provider == "nvidia":
        if not NVIDIA_API_KEY:
            raise ValueError("NVIDIA_API_KEY não configurada no servidor.")
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(f"{NVIDIA_URL}/chat/completions", headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Erro NVIDIA NIM {res.status_code}: {res.text}")
            data = res.json()
            reply = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", estimated_tokens)
            return reply, tokens
    else:
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "num_ctx": OLLAMA_NUM_CTX,
                "temperature": 0.1,
                "num_predict": 1500,
            },
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            res = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Erro Ollama {res.status_code}: {res.text}")
            data = res.json()
            reply = data.get("message", {}).get("content", "")
            eval_tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
            return reply, eval_tokens or estimated_tokens


def parse_react_json(raw: str) -> Dict[str, Any]:
    clean = raw.strip()
    # Remove blocos ```json ... ``` se o modelo retornar envelopado
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()
    try:
        return json.loads(clean)
    except Exception:
        # Tenta extrair primeiro objeto JSON via regex
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Não foi possível parsear resposta JSON do modelo: {raw[:300]}")


async def agent_loop(req: AgentRequest) -> AsyncIterator[str]:
    provider, target_model = resolve_provider_and_model(req.model)
    system_prompt = (
        f"{PERSONA_PROMPTS.get(req.persona, PERSONA_PROMPTS['pentest'])}\n\n"
        f"{REACT_FORMAT_INSTRUCTIONS}"
    )

    conversation: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"OBJETIVO DA MISSÃO:\n{req.goal}"},
    ]

    total_tokens = 0
    max_steps = req.max_iterations

    yield f"data: {json.dumps({'type': 'iteration', 'current': 0, 'max': max_steps})}\n\n"

    for step in range(1, max_steps + 1):
        yield f"data: {json.dumps({'type': 'iteration', 'current': step, 'max': max_steps})}\n\n"

        try:
            raw_reply, tokens = await query_model_json(provider, target_model, conversation)
            total_tokens += tokens
            yield f"data: {json.dumps({'type': 'tokens', 'total': total_tokens})}\n\n"

            parsed = parse_react_json(raw_reply)
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Erro no passo {step}: {exc}'})}\n\n"
            break

        thought = parsed.get("thought", "")
        action = parsed.get("action", "")
        action_input = parsed.get("action_input", {})

        if thought:
            yield f"data: {json.dumps({'type': 'thought', 'content': thought})}\n\n"

        if action == "finish":
            final_content = ""
            if isinstance(action_input, dict):
                final_content = action_input.get("content", str(action_input))
            else:
                final_content = str(action_input)
            yield f"data: {json.dumps({'type': 'final', 'content': final_content})}\n\n"
            return

        if action == "run_command":
            cmd = action_input.get("cmd", "") if isinstance(action_input, dict) else str(action_input)
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'run_command', 'args': {'cmd': cmd}})}\n\n"

            result = await tool_run_command(cmd)
            summary = f"Exit code: {result.get('exit_code')}\nStdout: {result.get('stdout', '')}\nStderr: {result.get('stderr', '')}"
            yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'run_command', 'summary': summary})}\n\n"

            conversation.append({"role": "assistant", "content": raw_reply})
            conversation.append({
                "role": "user",
                "content": f"OBSERVAÇÃO DA TOOL (run_command):\n{json.dumps(result, ensure_ascii=False)}",
            })

        elif action == "http_request":
            args = action_input if isinstance(action_input, dict) else {}
            url = args.get("url", "")
            method = args.get("method", "GET")
            headers = args.get("headers", {})
            body = args.get("body", "")

            yield f"data: {json.dumps({'type': 'tool_call', 'tool': 'http_request', 'args': {'url': url, 'method': method}})}\n\n"

            result = await tool_http_request(url, method, headers, body)
            summary = f"Status: {result.get('status_code')}\nBody: {result.get('body', '')[:400]}"
            yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'http_request', 'summary': summary})}\n\n"

            conversation.append({"role": "assistant", "content": raw_reply})
            conversation.append({
                "role": "user",
                "content": f"OBSERVAÇÃO DA TOOL (http_request):\n{json.dumps(result, ensure_ascii=False)}",
            })
        else:
            err_msg = f"Ação desconhecida solicitada pelo modelo: {action}"
            yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"
            conversation.append({"role": "assistant", "content": raw_reply})
            conversation.append({
                "role": "user",
                "content": f"Erro: Ação inválida '{action}'. Escolha entre run_command, http_request ou finish.",
            })

    # Se atingiu o limite sem chamar finish
    yield f"data: {json.dumps({'type': 'final', 'content': f'Limite de {max_steps} iterações alcançado. Revisão necessária sobre o objetivo.'})}\n\n"


@app.post("/api/agent/stream")
async def agent_stream(req: AgentRequest):
    return StreamingResponse(agent_loop(req), media_type="text/event-stream")


# ============================================================
# ROTA ESTÁTICA DO FRONTEND
# ============================================================
@app.get("/")
async def serve_index():
    index_file = BASE_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse(
        {"message": "Cyber Hunter Lab API ativa. Coloque o arquivo index.html no mesmo diretório para acessá-lo na raiz."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
