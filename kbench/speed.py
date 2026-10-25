"""kbench speed - read (prefill) and write (decode) throughput of an OpenAI-compatible server.

Measured, never estimated:
- write (decode): tokens counted two ways, both reported -- SSE data chunks (the
  OpenAI streaming contract is one data event per token) and, when the server
  honors stream_options.include_usage, usage.completion_tokens.
- read (prefill): TTFT measured exactly. Prompt token rate is reported only when
  the server returns usage.prompt_tokens; otherwise the row shows words/bytes and
  TTFT ms, and no token rate is invented.

Run:
    python3 -m kbench speed --url http://host:port/v1 --model <id>
    python3 kbench/speed.py --url http://host:port/v1  (standalone, stdlib only)
"""
import argparse
import json
import os
import time
import urllib.request

UNIT = ("the history of the river is long and the banks remember every season "
        "and the water keeps the names of those who crossed it ")


def words_to(n):
    out, c = [], 0
    while c < n:
        out.append(UNIT)
        c += len(UNIT.split())
    return " ".join(out)


def measure(url, model, prompt_words, gen, timeout):
    prompt = words_to(prompt_words)
    body = {"model": model, "temperature": 0, "max_tokens": gen, "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft = None
    chunks = 0
    usage = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                ev = json.loads(payload)
            except ValueError:
                continue
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                if ch.get("delta", {}).get("content"):
                    chunks += 1
                    if ttft is None:
                        ttft = time.perf_counter() - t0
    total = time.perf_counter() - t0
    decode = total - ttft if ttft is not None else 0.0
    ptok = usage.get("prompt_tokens")
    ctok = usage.get("completion_tokens")
    return {
        "prompt_words": len(prompt.split()), "prompt_chars": len(prompt),
        "prompt_tokens": ptok, "ttft_ms": round((ttft or 0) * 1000, 1),
        "read_tok_s": round(ptok / ttft, 2) if ptok and ttft else None,
        "decode_chunks": chunks, "completion_tokens": ctok,
        "write_tok_s": round((ctok or chunks) / decode, 2) if decode > 0 else None,
        "write_basis": "usage" if ctok else "chunks",
        "total_s": round(total, 2),
        "e2e_tok_s": round((ctok or chunks) / total, 2) if total > 0 else None,
    }


def speed(a):
    url = a.url
    model = a.model
    if not model:
        with urllib.request.urlopen(url.rstrip("/") + "/models", timeout=30) as r:
            model = json.load(r)["data"][0]["id"]
        print("model:", model)
    sizes = [int(x) for x in str(a.sizes).split(",") if x.strip()]
    rows = []
    print("%8s %10s %12s %12s %10s %9s %8s" % ("words", "ttft_ms", "read_tok/s", "write_tok/s", "basis", "total_s", "e2e_tok/s"))
    for n in sizes:
        acc = []
        for _ in range(a.repeat):
            row = measure(url, model, n, a.gen, a.timeout)
            row["model"] = model
            row["url"] = url
            acc.append(row)
            rows.append(row)
            print("%8d %10s %12s %12s %10s %9s %8s" % (
                row["prompt_words"], row["ttft_ms"], row["read_tok_s"] or "-",
                row["write_tok_s"] or "-", row["write_basis"], row["total_s"], row["e2e_tok_s"] or "-"))
        if a.runs > 1:
            w = [r["write_tok_s"] for r in acc if r["write_tok_s"]]
            t = [r["ttft_ms"] for r in acc]
            print("    avg: ttft %s ms, write %s tok/s" % (round(sum(t) / len(t), 1), round(sum(w) / len(w), 2) if w else "-"))
    if a.save:
        host = url.split("//")[-1].split("/")[0].replace(":", "-").replace(".", "_")
        os.makedirs("results", exist_ok=True)
        fn = "results/speed-%s-%s-%d.json" % (host, model.replace("/", "_"), time.time())
        with open(fn, "w", encoding="utf-8") as f:
            json.dump({"url": url, "model": model, "gen": a.gen, "sizes": sizes, "rows": rows}, f, indent=1)
        print("saved:", fn)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="read/write throughput of an OpenAI-compatible server")
    ap.add_argument("--url", default="http://127.0.0.1:8093/v1")
    ap.add_argument("--model", default=None)
    ap.add_argument("--sizes", default="128,512,2048")
    ap.add_argument("--gen", type=int, default=128)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--save", action="store_true")
    speed(ap.parse_args(argv))


if __name__ == "__main__":
    main()
