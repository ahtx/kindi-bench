"""kbench breakdown: jobs that mix language and exact work, each done three ways with the same data and the same
exact check:
  agent     the whole job as one prompt to pi (thinking on: the "think" condition of `kbench run`)
  oneshot   the whole job as one chat prompt that holds all the text
  broken    a short program asks the model about one item at a time and does the counting itself (temperature 0)
The data is separate from the text-job items, and every answer is known. We wrote all items; they are fictional."""
import os
import random
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import json

from . import sandbox, server, piconfig
from .runner import CONDS, find_pi, pi_env

_MODEL = None

REVIEWS = [(t, "positive") for t in [
    "The blender is quiet and makes smoothies in seconds. Love it.",
    "Fast delivery and the shoes fit perfectly.",
    "Best coffee I have had from a machine at home.",
    "The staff were friendly and fixed my phone in ten minutes.",
    "Great value. The tent kept us dry all weekend.",
    "I am very happy with this keyboard; typing feels great.",
    "The app is simple and it saves me time every day.",
    "Wonderful hotel, clean rooms and a lovely breakfast."]] + [(t, "negative") for t in [
    "The charger stopped working after two days.",
    "Terrible customer service, nobody answered my emails.",
    "The jacket ripped the first time I wore it.",
    "My order arrived late and the box was crushed.",
    "The battery drains in an hour. Very disappointed.",
    "Rude driver and the food was cold.",
    "The update made the app crash every time I open it."]] + [(t, "neutral") for t in [
    "The package contains one cable and a manual.",
    "The store opens at 9 am on weekdays.",
    "The lamp is available in white and black.",
    "I ordered the medium size.",
    "The table is 120 cm long."]]

EMAILS = [(t, "spam") for t in [
    "You have WON a free cruise! Click here to claim your prize now.",
    "URGENT: your account will be closed. Verify your password at secure-login-check.example.",
    "Cheap watches, 90% off, today only!!!",
    "Make $5000 a week from home with no work. Reply now.",
    "Dear friend, I need your help to move 10 million dollars. You will get 30%.",
    "Your parcel is waiting. Pay the $1.99 fee at bit.ly/pkg-fee to release it.",
    "Lose 10 kg in 7 days with this one pill. Order now.",
    "Congratulations! You are selected for a $1000 gift card. Click to claim."]] + [(t, "ham") for t in [
    "Hi team, the meeting moved to 3 pm in room B.",
    "Mum, I will be home late tonight. Save me some dinner.",
    "Attached is the invoice for September. Let me know if you have questions.",
    "Can you review my pull request before Friday?",
    "Your dentist appointment is confirmed for Tuesday at 10:00.",
    "Thanks for the great presentation yesterday.",
    "The library book you reserved is ready for pickup.",
    "Reminder: the office is closed on Monday for the holiday.",
    "Here are the photos from the trip. The beach one is my favourite.",
    "Could you send me the slides from the workshop?",
    "Your order #4821 has shipped and should arrive Thursday.",
    "Lunch on Wednesday? I found a new Thai place."]]

MESSAGES = [(t, True) for t in [
    "There is a gas smell in the kitchen since your installer left.",
    "Someone used my card for three purchases I did not make.",
    "Your website is down and no customer can pay.",
    "I can see another person's medical records in my account.",
    "My child swallowed one of the small batteries from your toy.",
    "Your letter says I owe money I never borrowed. I will take you to court.",
    "The elevator you serviced stopped between floors with people inside."]] + [(t, False) for t in [
    "How do I change my delivery address?",
    "Do you have this sweater in blue?",
    "Thanks for the quick reply yesterday.",
    "Can I get a paper copy of my invoice?",
    "What time does support open on Saturday?",
    "I would like to cancel my newsletter subscription.",
    "The colour of the cup is a bit darker than the photo.",
    "Please add a dark mode to the app.",
    "Where can I find the user manual?",
    "Is there a student discount?",
    "My password reset email took ten minutes to arrive.",
    "Can I return a gift without the receipt?",
    "Your new logo looks nice."]]

HEADLINES = [(t, "sports") for t in [
    "City win the cup final 2-1 after extra time",
    "Tennis star retires at 34 after twenty years on tour",
    "Marathon record falls in Berlin",
    "National team names new coach before the World Cup",
    "Cyclist wins the mountain stage in heavy rain",
    "Swimmer breaks the 100 m world record"]] + [(t, "business") for t in [
    "Oil prices rise as supply falls",
    "Carmaker reports record profit for the third quarter",
    "Retail chain to close 40 stores"]] + [(t, "politics") for t in [
    "Parliament passes the new budget after a long debate",
    "Prime minister meets regional leaders on trade",
    "Voters head to the polls in the city election"]] + [(t, "technology") for t in [
    "New phone chip doubles battery life",
    "Researchers build a faster quantum processor"]] + [(t, "health") for t in [
    "Doctors report a drop in flu cases this winter"]]

ORDERS = [
    ("Order 1182: two notebooks and a pen. I paid $14.50 by card.", 14.50),
    ("Hi, for order 2290 (3 items) the total charged was $42.00.", 42.00),
    ("Thanks! Order 3315 arrived. My receipt says the total was $7.25.", 7.25),
    ("Order 4021: one desk lamp, total paid $36.99, delivery on day 12.", 36.99),
    ("I paid 19.90 dollars for order 5108, which had 2 mugs.", 19.90),
    ("Order 6234 total: $120.00 for the chair (model 77).", 120.00),
    ("For order 7001 I was charged $8.40, room 305.", 8.40),
    ("Order 8150: 4 cables at $2.50 each, total $10.00.", 10.00),
    ("My card was charged $55.55 for order 9020 on 3 May.", 55.55),
    ("Order 9911, 1 backpack, total amount $64.30.", 64.30)]

rng = random.Random(20261019)
for lst in (REVIEWS, EMAILS, MESSAGES, HEADLINES, ORDERS):
    rng.shuffle(lst)
MSG_IDS = ["M%02d" % (i + 1) for i in range(len(MESSAGES))]
MAIL_NAMES = ["mail%02d.txt" % (i + 1) for i in range(len(EMAILS))]

ESC_RULES = ("You triage customer messages. Answer yes if a person must look at this message now (danger to health or "
             "safety, fraud, a legal threat, a security or privacy breach, a major outage, or a person in crisis). "
             "Answer no for routine questions, requests and feedback.")


def lines(rows):
    return "".join(t + "\n" for t, _ in rows)


def nums(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))]


# ---------------------------------------------------------------------------------------------------- the jobs
def setup_files(job, wd):
    if job == "tally":
        open(os.path.join(wd, "reviews.txt"), "w").write(lines(REVIEWS))
    elif job == "spam":
        os.makedirs(os.path.join(wd, "inbox"))
        for name, (t, _) in zip(MAIL_NAMES, EMAILS):
            open(os.path.join(wd, "inbox", name), "w").write(t + "\n")
    elif job == "urgent":
        open(os.path.join(wd, "messages.txt"), "w").write("".join("%s: %s\n" % (i, t) for i, (t, _) in zip(MSG_IDS, MESSAGES)))
    elif job == "topic":
        open(os.path.join(wd, "headlines.txt"), "w").write(lines(HEADLINES))
    elif job == "orders":
        open(os.path.join(wd, "orders.txt"), "w").write(lines(ORDERS))


TRUTH = {
    "tally": {k: sum(1 for _, v in REVIEWS if v == k) for k in ("positive", "negative", "neutral")},
    "spam": sorted(n for n, (_, v) in zip(MAIL_NAMES, EMAILS) if v == "spam"),
    "urgent": sorted(i for i, (_, v) in zip(MSG_IDS, MESSAGES) if v),
    "topic": ("sports", sum(1 for _, v in HEADLINES if v == "sports")),
    "orders": round(sum(v for _, v in ORDERS), 2),
}

TASK = {
    "tally": "reviews.txt has one customer review per line. Count how many reviews are positive, negative and neutral "
             "(a neutral review states facts with no opinion). Write answer.txt with three lines: positive N, "
             "negative N, neutral N.",
    "spam": "The inbox folder has one e-mail per file. Move every spam e-mail (advertising, scams, phishing) into a "
            "folder named spam. Leave the normal e-mails in inbox.",
    "urgent": "messages.txt has one customer message per line, each with an ID such as M01. Write answer.txt with the "
              "IDs of the messages that a person must see now (danger to health or safety, fraud, a legal threat, a "
              "security or privacy breach, a major outage), one per line, sorted.",
    "topic": "headlines.txt has one news headline per line. Each headline is about one topic: sports, politics, "
             "business, technology or health. Find the topic with the most headlines and write it and its count to "
             "answer.txt, for example: health 2",
    "orders": "orders.txt has one customer e-mail per line about an order. Find the total amount that was paid in each "
              "e-mail, add the amounts, and write the sum to answer.txt with two decimals, for example 12.34",
}


def check(job, answer, wd=None):
    """-> (passed, what was found). answer: the text of answer.txt (or of the model's reply)."""
    a = (answer or "").lower()
    if job == "tally":
        got = {}
        for k in TRUTH["tally"]:
            m = re.search(k + r"\D{0,12}(\d+)", a)
            got[k] = int(m.group(1)) if m else None
        return got == TRUTH["tally"], got
    if job == "spam":
        if wd is not None:
            sp = sorted(os.listdir(os.path.join(wd, "spam"))) if os.path.isdir(os.path.join(wd, "spam")) else []
            left = sorted(os.listdir(os.path.join(wd, "inbox"))) if os.path.isdir(os.path.join(wd, "inbox")) else []
            ok = sp == TRUTH["spam"] and sorted(sp + left) == sorted(MAIL_NAMES)
            return ok, sp
        got = sorted(set(re.findall(r"mail\d\d\.txt", a)))
        return got == TRUTH["spam"], got
    if job == "urgent":
        got = sorted(set(re.findall(r"m\d\d", a)))
        return got == [x.lower() for x in TRUTH["urgent"]], got
    if job == "topic":
        m = re.search(r"(sports|politics|business|technology|health)\D{0,12}(\d+)", a)
        got = (m.group(1), int(m.group(2))) if m else None
        return got == TRUTH["topic"], got
    if job == "orders":
        n = nums(a)
        got = n[-1] if n else None
        return got is not None and abs(got - TRUTH["orders"]) < 0.005, got



# ---------------------------------------------------------------------------------------------------- the model
def chat(url, prompt, max_tokens, temperature=None):
    out, secs, _ = server.chat(url, prompt, max_tokens, temperature=temperature, model=_MODEL, timeout=1800)
    return out, secs


def one_word(text, words):
    """The allowed word that comes first in the reply ("Ham. It is not spam." -> ham), or None."""
    hits = [(m.start(), w) for w in words for m in [re.search(r"\b%s\b" % w, text.lower())] if m]
    return min(hits)[1] if hits else None


# The per-item prompts for the two jobs whose first prompt failed. "first" = the prompts of the first K420 run:
# "Reply with one word: spam or ham." made the model call most normal e-mails spam, and "for example 12.34" made it
# copy "12." into its answers. "tested" = the fixed prompts (the spam prompt of the text jobs; no example number).
PROMPTS = {
    "first": {"spam": "Is this e-mail spam (unwanted advertising, a scam or phishing) or ham (a normal message)? "
                      "Reply with one word: spam or ham.\n\n",
              "orders": "This e-mail is about one order. What is the total amount that was paid? Reply with the "
                        "number only, for example 12.34.\n\n"},
    "tested": {"spam": "Is this e-mail spam (unwanted advertising, a scam or phishing) or ham (a normal message)? "
                       "Answer spam or ham.\n\n",
               "orders": "This e-mail is about one order. What is the total amount that was paid? Reply with the "
                         "number only.\n\n"},
}
USE = "tested"

# Held-out items, written after the prompt fix, so that the fix is not scored only on the items that showed the problem.
HELD_SPAM = [(t, "spam") for t in [
    "Claim your free iPhone now, only 3 left! Click the link.",
    "Your bank account is locked. Log in at secure-bank-verify.example to unlock it.",
    "Earn 300 dollars a day from your sofa. No experience needed.",
    "FINAL NOTICE: your car warranty expires today. Call now."]] + [(t, "ham") for t in [
    "The plumber will come on Thursday between 9 and 11.",
    "Here is the agenda for tomorrow's call.",
    "Your flight to Denver is confirmed. Seat 14C.",
    "Can we move our 1:1 to Friday morning?",
    "The school trip form is due on Monday.",
    "Thanks for lending me the drill, I will bring it back tonight."]]
HELD_ORDERS = [
    ("Order 3401: three shirts, total paid $58.20, size M.", 58.20),
    ("I paid $9.99 for order 7720 (1 phone case).", 9.99),
    ("For order 1210 the card was charged $134.75 on 12 June.", 134.75),
    ("Order 5555, 2 lamps at $20.00 each, total $40.00.", 40.00),
    ("Receipt for order 8080: total amount 23.10 dollars, 4 items.", 23.10),
    ("Order 6600 arrived in box 2 of 2. Total charged: $71.45.", 71.45)]


def held_out(url):
    """The broken-down spam and order jobs on the held-out items, with the current prompts."""
    right = sum((one_word(chat(url, PROMPTS[USE]["spam"] + t, 5, 0)[0], ["spam", "ham"]) or "ham") == want
                for t, want in HELD_SPAM)
    tot, ok = 0.0, 0
    for t, want in HELD_ORDERS:
        n = nums(chat(url, PROMPTS[USE]["orders"] + t, 10, 0)[0])
        v = n[0] if n else 0.0
        tot += v
        ok += abs(v - want) < 0.005
    truth = round(sum(v for _, v in HELD_ORDERS), 2)
    return {"spam": {"passed": right == len(HELD_SPAM), "items_right": right, "items": len(HELD_SPAM)},
            "orders": {"passed": abs(tot - truth) < 0.005, "got": round(tot, 2), "truth": truth, "items_right": ok,
                       "items": len(HELD_ORDERS)}}


def broken(job, url):
    """The program walks the items; Kindi answers one short question per item; the program counts."""
    calls, items = [], []
    if job == "tally":
        got = {"positive": 0, "negative": 0, "neutral": 0}
        for t, want in REVIEWS:
            out, s = chat(url, "Classify the sentiment of this customer review as positive, negative or neutral. A "
                               "neutral review states facts with no opinion. Reply with one word.\n\n" + t, 5, 0)
            w = one_word(out, ["positive", "negative", "neutral"]) or "neutral"
            got[w] += 1; calls.append(s); items.append(w == want)
        answer = "".join("%s %d\n" % (k, v) for k, v in got.items())
    elif job == "spam":
        sp = []
        for name, (t, want) in zip(MAIL_NAMES, EMAILS):
            out, s = chat(url, PROMPTS[USE]["spam"] + t, 5, 0)
            w = one_word(out, ["spam", "ham"]) or "ham"
            if w == "spam":
                sp.append(name)
            calls.append(s); items.append(w == want)
        answer = "\n".join(sp)
    elif job == "urgent":
        ids = []
        for i, (t, want) in zip(MSG_IDS, MESSAGES):
            out, s = chat(url, ESC_RULES + " When you are not sure, answer yes. Reply with one word only.\n\n" + t, 5, 0)
            yes = one_word(out, ["yes", "no"]) != "no"
            if yes:
                ids.append(i)
            calls.append(s); items.append(yes == want)
        answer = "\n".join(sorted(ids))
    elif job == "topic":
        cnt = {}
        for t, want in HEADLINES:
            out, s = chat(url, "Give the topic of this news headline: sports, politics, business, technology or "
                               "health. Reply with one word.\n\n" + t, 5, 0)
            w = one_word(out, ["sports", "politics", "business", "technology", "health"]) or "other"
            cnt[w] = cnt.get(w, 0) + 1; calls.append(s); items.append(w == want)
        top = max(cnt.items(), key=lambda kv: kv[1])
        answer = "%s %d" % top
    elif job == "orders":
        tot = 0.0
        for t, want in ORDERS:
            out, s = chat(url, PROMPTS[USE]["orders"] + t, 10, 0)
            n = nums(out)
            v = n[0] if n else 0.0
            tot += v; calls.append(s); items.append(abs(v - want) < 0.005)
        answer = "%.2f" % tot
    ok, got = check(job, answer)
    return {"passed": ok, "got": got, "answer": answer, "calls": len(calls), "secs": round(sum(calls), 1),
            "items_right": sum(items), "items": len(items)}


def oneshot(job, url):
    """All the text in one prompt; the model must give the final answer itself."""
    if job == "tally":
        data = "reviews.txt:\n" + lines(REVIEWS)
    elif job == "spam":
        data = "".join("%s:\n%s\n\n" % (n, t) for n, (t, _) in zip(MAIL_NAMES, EMAILS))
    elif job == "urgent":
        data = "messages.txt:\n" + "".join("%s: %s\n" % (i, t) for i, (t, _) in zip(MSG_IDS, MESSAGES))
    elif job == "topic":
        data = "headlines.txt:\n" + lines(HEADLINES)
    else:
        data = "orders.txt:\n" + lines(ORDERS)
    task = TASK[job].replace("Write answer.txt with", "Reply with").replace("write it and its count to answer.txt",
                                                                            "reply with it and its count")
    task = task.replace("and write the sum to answer.txt", "and reply with the sum")
    if job == "spam":
        task = "Here are e-mails, one per file. List the file names of the spam e-mails (advertising, scams, phishing)."
    out, s = chat(url, task + "\n\n" + data, 400)
    ok, got = check(job, out)
    return {"passed": ok, "got": got, "answer": out[-400:], "secs": round(s, 1)}



def limits():
    """preexec_fn: a new session (so the watchdog can find and kill all of it), files of up to 100 MB."""
    os.setsid()
    sandbox.limit(100 << 20)


def watchdog(sid, stop, limit_kb=2 << 20, max_procs=200):
    """Kill the agent's whole session if its processes use more than 2 GB together or more than 200 processes."""
    page_kb = os.sysconf("SC_PAGE_SIZE") // 1024
    while not stop.wait(2):
        rss, n = 0, 0
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                st = open("/proc/%s/stat" % d).read().rsplit(")", 1)[1].split()
                if int(st[3]) != sid:
                    continue
                n += 1
                rss += int(st[21]) * page_kb
            except (OSError, IndexError, ValueError):
                pass
        if rss > limit_kb or n > max_procs:
            try:
                os.killpg(sid, signal.SIGKILL)
            except OSError:
                pass
            return


def agent(job, run, url, pi, agent_dir, work, timeout):
    wd = os.path.join(work, "%s-%d" % (job, run))
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)
    setup_files(job, wd)
    prompt = "Work in the folder %s. %s" % (wd, TASK[job])
    env = pi_env(pi, agent_dir)
    c = CONDS["think"]
    t0 = time.time()
    p = subprocess.Popen([pi, "-p", "--no-session", "--provider", piconfig.provider_name("think"), "--model", _MODEL,
                          "--thinking", c["thinking"], prompt], cwd=wd, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=limits)
    stop = threading.Event()
    threading.Thread(target=watchdog, args=(p.pid, stop), daemon=True).start()
    try:
        out = p.communicate(timeout=timeout)[0].decode("utf-8", "replace")
        timed_out = False
    except subprocess.TimeoutExpired:
        out, timed_out = "", True
    stop.set()
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    if timed_out:
        p.communicate()
    sandbox.sweep(wd)
    ans = os.path.join(wd, "answer.txt")
    text = open(ans, errors="replace").read()[:2000] if os.path.exists(ans) else ""
    ok, got = check(job, text, wd if job == "spam" else None)
    res = {"passed": ok, "got": got, "answer": text[:400], "secs": round(time.time() - t0, 1), "timed_out": timed_out,
           "nofile": job != "spam" and not os.path.exists(ans), "last": out[-600:]}
    shutil.rmtree(wd, ignore_errors=True)
    return res


def main(url, out, model, agent_runs=3, api_runs=3, only="", pi=None, work="~/kbench-work", timeout=900,
         prompts="tested"):
    global _MODEL, USE
    _MODEL = model
    USE = prompts
    jobs = [j for j in TASK if not only or j in only.split(",")]
    if not jobs:
        raise SystemExit("unknown job (known: %s)" % ", ".join(TASK))
    R = {"model": model, "url": piconfig.public_url(server.base(url)), "prompts": prompts, "truth": TRUTH, "jobs": {}}
    tmp = None
    if agent_runs:
        if not model:
            raise SystemExit("the agent mode needs --model (the server's model id)")
        pi = find_pi(pi)
        base = os.path.realpath(os.path.expanduser(work))
        os.makedirs(base, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="breakdown-", dir=base)
        agent_dir = piconfig.write(os.path.join(tmp, "pi-agent"), server.base(url), model, {"think": CONDS["think"]})
    try:
        for job in jobs:
            r = R["jobs"][job] = {"broken": broken(job, url)}
            print(job, "broken", r["broken"]["passed"], r["broken"]["got"], flush=True)
            r["oneshot"] = [oneshot(job, url) for _ in range(api_runs)]
            print(job, "oneshot", [x["passed"] for x in r["oneshot"]], flush=True)
            r["agent"] = []
            for k in range(agent_runs):
                r["agent"].append(agent(job, k + 1, url, pi, agent_dir, tmp, timeout))
                print(job, "agent", k + 1, r["agent"][-1]["passed"], r["agent"][-1]["got"], r["agent"][-1]["secs"],
                      flush=True)
            with open(out, "w") as f:
                json.dump(R, f, indent=1, default=str)
        if {"spam", "orders"} & set(jobs):
            R["held_out"] = held_out(url)
            print("held-out", {k: v["passed"] for k, v in R["held_out"].items()}, flush=True)
            with open(out, "w") as f:
                json.dump(R, f, indent=1, default=str)
    finally:
        if tmp:
            sandbox.sweep(tmp)
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                os.rmdir(os.path.dirname(tmp))           # the work folder, only when it is empty
            except OSError:
                pass
    print("done", flush=True)
