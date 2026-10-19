"""Write a pi config dir (PI_CODING_AGENT_DIR): models.json, settings.json and SYSTEM.md.

Each condition gets its own provider (kb-<cond>) with one model: the server's model id with the condition's output
cap. All providers point at the same OpenAI-compatible URL."""
import json
import os
import shutil
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_MD = os.path.join(HERE, "agent", "SYSTEM.md")
SETTINGS = os.path.join(HERE, "agent", "settings.json")

# Kindi and llama.cpp both take the Qwen chat-template switch for thinking; neither takes a developer role or
# reasoning_effort. pi sends the thinking budget in thinking_budget_tokens.
COMPAT = {"supportsDeveloperRole": False, "supportsReasoningEffort": False, "thinkingFormat": "qwen-chat-template",
          "thinkingTokenBudgetField": "thinking_budget_tokens"}
DUMMY_KEY = "no-key"               # the server does not check it; pi needs a value


def provider_name(cond):
    return "kb-" + cond


def models_json(url, model, conds, context):
    providers = {}
    for name, c in conds.items():
        providers[provider_name(name)] = {
            "baseUrl": url, "api": "openai-completions", "apiKey": os.environ.get("KBENCH_API_KEY") or DUMMY_KEY,
            "compat": dict(COMPAT),
            "models": [{"id": model, "name": model, "reasoning": True, "input": ["text"], "contextWindow": context,
                        "maxTokens": c["max_tokens"],
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}
    return {"providers": providers}


def write(dirpath, url, model, conds, context=24576, request_timeout_s=1800):
    """conds: {name: {"max_tokens": N, "thinking": "off"|"medium"|...}}"""
    os.makedirs(dirpath, exist_ok=True)
    with open(os.path.join(dirpath, "models.json"), "w") as f:
        json.dump(models_json(url, model, conds, context), f, indent=2)
    with open(SETTINGS) as f:
        s = json.load(f)
    first = next(iter(conds))
    s["defaultProvider"] = provider_name(first)
    s["defaultModel"] = model
    s["defaultThinkingLevel"] = conds[first]["thinking"]
    s["retry"]["provider"]["timeoutMs"] = int(request_timeout_s * 1000)
    with open(os.path.join(dirpath, "settings.json"), "w") as f:
        json.dump(s, f, indent=2)
    shutil.copy(SYSTEM_MD, os.path.join(dirpath, "SYSTEM.md"))
    return dirpath


def public_url(url):
    """The URL with the host replaced unless it is a loopback address (manifests must not name machines)."""
    u = urllib.parse.urlsplit(url)
    host = u.hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        host = "SERVER"
    netloc = host + (":%d" % u.port if u.port else "")
    return urllib.parse.urlunsplit((u.scheme, netloc, u.path, "", ""))


def redact(models):
    m = json.loads(json.dumps(models))
    for p in m.get("providers", {}).values():
        p["baseUrl"] = public_url(p["baseUrl"])
        if p.get("apiKey") != DUMMY_KEY:
            p["apiKey"] = "(from KBENCH_API_KEY)"
    return m
