"""Small HTTP helpers for an OpenAI-compatible server (Kindi, llama.cpp llama-server, and others)."""
import json
import time
import urllib.error
import urllib.request


def base(url):
    """http://host:port/v1 (no trailing slash)."""
    return url.rstrip("/")


def root(url):
    u = base(url)
    return u[:-3] if u.endswith("/v1") else u


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except ValueError:
        return body


def health(url, timeout=10):
    """-> (ok, response). Tries /health (Kindi, llama.cpp), then /v1/models."""
    try:
        return True, get(root(url) + "/health", timeout)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return False, "HTTP %d" % e.code             # llama.cpp answers 503 while it loads the model
    except Exception as e:  # noqa: BLE001
        return False, repr(e)
    try:
        return True, get(base(url) + "/models", timeout)
    except Exception as e:  # noqa: BLE001
        return False, repr(e)


def wait_healthy(url, wait=900):
    t0 = time.time()
    while True:
        ok, _ = health(url)
        if ok:
            return True
        if time.time() - t0 > wait:
            return False
        time.sleep(10)


def models(url):
    try:
        return get(base(url) + "/models")
    except Exception as e:  # noqa: BLE001
        return repr(e)


def chat(url, prompt, max_tokens, temperature=None, model=None, timeout=1800):
    """One user message, thinking off. -> (text, seconds, usage)."""
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False}}
    if temperature is not None:
        body["temperature"] = temperature
    if model:
        body["model"] = model
    t0 = time.time()
    req = urllib.request.Request(base(url) + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    return resp["choices"][0]["message"]["content"] or "", round(time.time() - t0, 2), resp.get("usage", {})
