"""kbench textjobs: short text jobs through the server's chat API, at temperature 0, thinking off.

Jobs: classification (sentiment, escalate, spam, topic), spelling and grammar fixes, text to a Markdown table, note
cleanup and news summaries. The first seven jobs are scored automatically; notes and news are for a person to read.
Every input, output and time goes into OUT.json."""
import concurrent.futures as cf
import json
import re
import time

from . import piconfig, server
from . import textjobs_data as D

CLASSIFY = {
    "sentiment": (D.SENTIMENT, ["positive", "negative", "neutral"],
                  "Classify the sentiment of this customer review as positive, negative or neutral. A neutral review "
                  "states facts with no opinion."),
    "escalate": (D.ESCALATE, ["yes", "no"],
                 "You triage customer messages. Answer yes if a person must look at this message now (danger to "
                 "health or safety, fraud, a legal threat, a security or privacy breach, a major outage, or a person "
                 "in crisis). Answer no for routine questions, requests and feedback."),
    "spam": (D.SPAM, ["spam", "ham"],
             "Is this e-mail spam (unwanted advertising, a scam or phishing) or ham (a normal message)? Answer spam or "
             "ham."),
    "topic": (D.TOPIC, ["sports", "politics", "business", "technology", "health"],
              "Give the topic of this news sentence: sports, politics, business, technology or health."),
}
JOBS = list(CLASSIFY) + ["spell", "grammar", "table", "notes", "news"]


def norm(s):
    s = s.strip().strip('"').strip()
    for a, b in (("doesn't", "does not"), ("didn't", "did not"), ("don't", "do not"), ("isn't", "is not"),
                 ("aren't", "are not"), ("wasn't", "was not"), ("weren't", "were not")):
        s = re.sub(r"\b%s\b" % a, b, s, flags=re.I)
    return re.sub(r"\s+", " ", s).rstrip(".").lower()


def jobs(only):
    out = []
    for name, (items, labels, instr) in CLASSIFY.items():
        for text, want in items:
            out.append({"job": name, "input": text, "want": want, "labels": labels, "max_tokens": 5,
                        "prompt": "%s Reply with one word only.\n\n%s" % (instr, text)})
    for name, items, instr in (("spell", D.SPELL, "Correct the spelling mistakes in this sentence. Change nothing else. "
                                "Reply with only the corrected sentence."),
                               ("grammar", D.GRAMMAR, "Correct the grammar of this sentence. Change as little as "
                                "possible. Reply with only the corrected sentence.")):
        for text, want in items:
            out.append({"job": name, "input": text, "want": want, "max_tokens": 60, "prompt": "%s\n\n%s" % (instr, text)})
    for text, header, rows in D.TABLES:
        out.append({"job": "table", "input": text, "want": {"header": header, "rows": rows}, "max_tokens": 200,
                    "prompt": "Turn this text into a Markdown table with the columns: %s. Reply with only the table."
                              "\n\n%s" % (", ".join(header), text)})
    for text in D.NOTES:
        out.append({"job": "notes", "input": text, "want": None, "max_tokens": 300,
                    "prompt": "Clean up these notes. Write them as a short list of clear tasks, one per line, with the "
                              "most urgent task first. Keep every fact.\n\n" + text})
    for text in D.NEWS:
        out.append({"job": "news", "input": text, "want": None, "max_tokens": 80,
                    "prompt": "Write a headline of at most ten words and a one-sentence summary for this news story. "
                              "Format: Headline: ... / Summary: ...\n\n" + text})
    return [j for j in out if not only or j["job"] in only]


def score(j, got):
    g = got.strip()
    if "labels" in j:
        w = re.findall(r"[a-z]+", g.lower())
        pick = next((x for x in w if x in j["labels"]), None)
        return pick == j["want"], pick
    if j["job"] in ("spell", "grammar"):
        wants = [j["want"]] + (["Him and me went to the store.", "He and I went to the store."] if "Me and him" in j["input"] else [])
        line = g.splitlines()[0] if g else ""
        return any(norm(line) == norm(w) for w in wants), line
    if j["job"] == "table":
        rows = [r for r in g.splitlines() if r.strip().startswith("|")]
        body = [r for r in rows[2:] if r.strip("| -:")]
        head = [c.strip().lower() for c in rows[0].strip().strip("|").split("|")] if rows else []
        ok = len(rows) >= 3 and head == [h.lower() for h in j["want"]["header"]] and len(body) == j["want"]["rows"]
        return ok, "%d rows" % len(body)
    return None, None


def main(url, out, model=None, parallel=1, only="", limit=0):
    only = [x for x in only.split(",") if x]
    bad = [x for x in only if x not in JOBS]
    if bad:
        raise SystemExit("unknown job %s (known: %s)" % (", ".join(bad), ", ".join(JOBS)))
    js = jobs(only)
    if limit:
        per = {}
        js = [j for j in js if per.setdefault(j["job"], []).append(1) or len(per[j["job"]]) <= limit]
    t0 = time.time()

    def run(j):
        got, secs, usage = server.chat(url, j["prompt"], j["max_tokens"], temperature=0, model=model, timeout=600)
        ok, parsed = score(j, got)
        return dict(j, output=got, ok=ok, parsed=parsed, secs=secs, usage=usage)

    with cf.ThreadPoolExecutor(parallel) as ex:
        res = list(ex.map(run, js))
    wall = time.time() - t0
    summary = {}
    for r in res:
        s = summary.setdefault(r["job"], {"n": 0, "ok": 0, "secs": 0.0})
        s["n"] += 1
        s["ok"] += bool(r["ok"])
        s["secs"] += r["secs"]
    for k, s in summary.items():
        s["secs"] = round(s["secs"], 2)
        s["mean_secs"] = round(s["secs"] / s["n"], 2)
        print("%-10s %2d/%-3d correct   %.1f s per item" % (k, s["ok"], s["n"], s["mean_secs"]) if k not in ("notes", "news")
              else "%-10s %d examples (read them)   %.1f s per item" % (k, s["n"], s["mean_secs"]))
    print("wall %.0f s for %d items (parallel %d)" % (wall, len(res), parallel))
    with open(out, "w") as f:
        json.dump({"url": piconfig.public_url(server.base(url)), "model": model, "parallel": parallel,
                   "wall_s": round(wall, 1), "summary": summary, "items": res}, f, indent=1)
