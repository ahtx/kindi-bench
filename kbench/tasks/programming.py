"""Programming and repair tasks.

Every task names one file for the agent to write (or to fix), a prompt, hidden tests and a reference solution. The
hidden tests run in the work folder after the agent stops and print one line that starts with FAIL for each problem.
The reference solution is used only by `kbench validate`.

We wrote every prompt, test and solution for this benchmark. Some tasks are classic problems (for example LCS,
Dijkstra, an LRU cache and Roman numerals): the problems are well known, but the prompts, files and tests are ours."""

TASKS = []


def task(id, file, tier, prompt, tests, ref, category="programming"):
    TASKS.append({"id": id, "category": category, "tier": tier, "kind": "file", "file": file, "prompt": prompt,
                  "tests": tests, "solution_files": {file: ref}})


# ------------------------------------------------------------------ hard (the first set)
_HARD = [
    {
        "id": "calc",
        "file": "calc.py",
        "prompt": (
            "Create calc.py with a function evaluate(s: str) -> int that evaluates an integer arithmetic expression "
            "with + - * / and parentheses, unary minus (e.g. '-(2+3)', '2*-3'), and arbitrary spaces. / is integer "
            "division that truncates toward zero (so -7/2 == -3). Usual precedence: * and / before + and -, left to "
            "right. Do NOT use eval or exec. Examples: evaluate('1 + 2*3') == 7, evaluate('(1+2)*3') == 9, "
            "evaluate('-7/2') == -3."),
        "tests": r'''
from calc import evaluate
import inspect, calc
cases = [("1 + 2*3", 7), ("(1+2)*3", 9), ("-7/2", -3), ("7/-2", -3), ("2*-3", -6), ("-(2+3)", -5),
         ("10 - 4 - 3", 3), ("100/10/5", 2), (" 2 * ( 3 + 4 ) * 5 ", 70), ("--3", 3), ("((((7))))", 7),
         ("1-(-1)", 2), ("14/3*3", 12), ("2+3*4-5/2", 12), ("-(-(-4))", -4), ("0", 0), ("123456789*1000", 123456789000)]
for s, want in cases:
    try:
        got = evaluate(s)
    except Exception as e:
        got = "error %r" % e
    if got != want:
        print("FAIL evaluate(%r) = %r, expected %r" % (s, got, want))
src = inspect.getsource(calc)
if "eval(" in src.replace("evaluate(", "") or "exec(" in src:
    print("FAIL uses eval/exec")
''',
    },
    {
        "id": "csvline",
        "file": "csvline.py",
        "prompt": (
            "Create csvline.py with a function parse_line(line: str) -> list[str] that splits one CSV line into "
            "fields without using the csv module. Fields are separated by commas. A field may be wrapped in double "
            "quotes; inside a quoted field, commas are literal and a doubled quote \"\" means one quote character. "
            "Unquoted fields are returned as-is (no stripping). An empty line gives ['']. Examples: "
            "parse_line('a,b,c') == ['a','b','c'], parse_line('\"x,y\",z') == ['x,y','z'], "
            "parse_line('\"say \"\"hi\"\"\"') == ['say \"hi\"']."),
        "tests": r'''
from csvline import parse_line
import inspect, csvline
cases = [("a,b,c", ["a", "b", "c"]), ('"x,y",z', ["x,y", "z"]), ('"say ""hi"""', ['say "hi"']), ("", [""]),
         ("a,,b", ["a", "", "b"]), (",", ["", ""]), ('"",x', ["", "x"]), (" a , b ", [" a ", " b "]),
         ('1,"two, three",4', ["1", "two, three", "4"]), ('"a""b",c,"d,e,f"', ['a"b', "c", "d,e,f"]),
         ("x,", ["x", ""]), ('"""quoted"""', ['"quoted"'])]
for s, want in cases:
    try:
        got = parse_line(s)
    except Exception as e:
        got = "error %r" % e
    if got != want:
        print("FAIL parse_line(%r) = %r, expected %r" % (s, got, want))
if "import csv" in inspect.getsource(csvline):
    print("FAIL uses the csv module")
''',
    },
    {
        "id": "lru",
        "file": "lru.py",
        "prompt": (
            "Create lru.py with a class LRUCache(capacity: int) with methods get(key) -> value or -1 if absent, and "
            "put(key, value). get and put both count as a use. When putting a new key into a full cache, first evict "
            "the least recently used key. Putting an existing key updates its value and makes it most recently used. "
            "Also add a method keys() that returns the keys from least to most recently used. Do not use "
            "functools.lru_cache."),
        "tests": r'''
from lru import LRUCache
def check(name, got, want):
    if got != want:
        print("FAIL %s: got %r, expected %r" % (name, got, want))
try:
    c = LRUCache(2)
    c.put(1, 1); c.put(2, 2)
    check("get 1", c.get(1), 1)
    c.put(3, 3)
    check("2 evicted", c.get(2), -1)
    check("keys after 3", c.keys(), [1, 3])
    c.put(1, 10)
    check("update 1", c.get(1), 10)
    c.put(4, 4)
    check("3 evicted", c.get(3), -1)
    check("keys final", c.keys(), [1, 4])
    d = LRUCache(1)
    d.put("a", 1); d.put("b", 2)
    check("cap1 a", d.get("a"), -1); check("cap1 b", d.get("b"), 2)
    e = LRUCache(3)
    for k in range(3): e.put(k, k)
    e.get(0); e.put(3, 3)
    check("evict 1 not 0", e.keys(), [2, 0, 3])
    check("missing", e.get(99), -1)
    check("keys unchanged by miss", e.keys(), [2, 0, 3])
except Exception as ex:
    print("FAIL exception %r" % ex)
''',
    },
    {
        "id": "topo",
        "file": "topo.py",
        "prompt": (
            "Create topo.py with a function order(n: int, deps: list[tuple[int, int]]) -> list[int] | None. Tasks are "
            "numbered 0..n-1. A pair (a, b) means task a must come before task b. Return the lexicographically "
            "smallest valid order (at every step take the smallest-numbered task that is ready), or None if the "
            "dependencies contain a cycle. Example: order(3, [(2, 0)]) == [1, 2, 0]; order(2, [(0, 1), (1, 0)]) is "
            "None."),
        "tests": r'''
from topo import order
cases = [((3, [(2, 0)]), [1, 2, 0]), ((2, [(0, 1), (1, 0)]), None), ((4, []), [0, 1, 2, 3]),
         ((4, [(3, 2), (2, 1), (1, 0)]), [3, 2, 1, 0]), ((5, [(4, 0), (3, 0), (1, 3)]), [1, 2, 3, 4, 0]),
         ((3, [(0, 1), (0, 1)]), [0, 1, 2]), ((1, [(0, 0)]), None), ((6, [(5, 2), (5, 0), (4, 0), (4, 1), (2, 3), (3, 1)]),
         [4, 5, 0, 2, 3, 1]), ((3, [(1, 2), (2, 1)]), None), ((0, []), [])]
for args, want in cases:
    try:
        got = order(*args)
    except Exception as e:
        got = "error %r" % e
    if got != want:
        print("FAIL order%r = %r, expected %r" % (args, got, want))
''',
    },
    {
        "id": "wordbreak",
        "file": "wordbreak.py",
        "prompt": (
            "Create wordbreak.py with a function sentences(s: str, words: list[str]) -> list[str] that returns every "
            "way to split s into a sequence of dictionary words (words may be reused), each as the words joined by "
            "single spaces, sorted alphabetically. Return [] if there is none. It must be fast for s of length 30 "
            "made of 'a's with words ['a','aa','aaa',...] being impossible to finish (e.g. s='a'*30+'b'). Example: "
            "sentences('catsanddog', ['cat','cats','and','sand','dog']) == ['cat sand dog', 'cats and dog']."),
        "tests": r'''
import time
from wordbreak import sentences
cases = [(("catsanddog", ["cat", "cats", "and", "sand", "dog"]), ["cat sand dog", "cats and dog"]),
         (("pineapplepenapple", ["apple", "pen", "applepen", "pine", "pineapple"]),
          ["pine apple pen apple", "pine applepen apple", "pineapple pen apple"]),
         (("catsandog", ["cats", "dog", "sand", "and", "cat"]), []),
         (("", ["a"]), [""]), (("aaa", ["a", "aa"]), ["a a a", "a aa", "aa a"])]
for args, want in cases:
    try:
        got = sentences(*args)
    except Exception as e:
        got = "error %r" % e
    if got != want and not (args[0] == "" and got in ([""], [])):
        print("FAIL sentences%r = %r, expected %r" % (args, got, want))
t = time.time()
try:
    got = sentences("a" * 30 + "b", ["a", "aa", "aaa", "aaaa", "aaaaa"])
    if got != []:
        print("FAIL impossible case returned %r" % got[:3])
except Exception as e:
    print("FAIL impossible case error %r" % e)
if time.time() - t > 2:
    print("FAIL too slow on 'a'*30+'b' (%.1fs)" % (time.time() - t))
''',
    },
    {
        "id": "roman",
        "file": "roman.py",
        "prompt": (
            "Create roman.py with two functions: to_roman(n: int) -> str for 1 <= n <= 3999 using standard subtractive "
            "notation (4 = IV, 9 = IX, 40 = XL, 90 = XC, 400 = CD, 900 = CM), and from_roman(s: str) -> int which "
            "parses a numeral and raises ValueError for anything that is not the canonical numeral of some n in "
            "1..3999 (for example 'IIII', 'IC', 'VX', 'MMMM', '' and 'abc' must raise). Examples: to_roman(1994) == "
            "'MCMXCIV', from_roman('MCMXCIV') == 1994."),
        "tests": r'''
from roman import to_roman, from_roman
for n, s in [(1, "I"), (4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"), (90, "XC"), (400, "CD"), (1994, "MCMXCIV"),
             (3999, "MMMCMXCIX"), (2024, "MMXXIV"), (444, "CDXLIV")]:
    try:
        if to_roman(n) != s:
            print("FAIL to_roman(%d) = %r, expected %r" % (n, to_roman(n), s))
        if from_roman(s) != n:
            print("FAIL from_roman(%r) = %r, expected %d" % (s, from_roman(s), n))
    except Exception as e:
        print("FAIL %d/%s error %r" % (n, s, e))
try:
    bad = [n for n in range(1, 4000) if from_roman(to_roman(n)) != n]
    if bad:
        print("FAIL round trip broken for %d numbers, e.g. %r" % (len(bad), bad[:5]))
except Exception as e:
    print("FAIL round trip error %r" % e)
for s in ["IIII", "IC", "VX", "MMMM", "", "abc", "IIV", "XM", "VV", "LC", "DM", "IXI"]:
    try:
        v = from_roman(s)
        print("FAIL from_roman(%r) returned %r instead of raising ValueError" % (s, v))
    except ValueError:
        pass
    except Exception as e:
        print("FAIL from_roman(%r) raised %r, not ValueError" % (s, e))
''',
    },
    {
        "id": "bigmul",
        "file": "bigmul.py",
        "prompt": (
            "Create bigmul.py with a function multiply(a: str, b: str) -> str that multiplies two integers given as "
            "decimal strings (each may start with '-') and returns the product as a decimal string with no leading "
            "zeros ('0' for zero, never '-0'). You must NOT convert the whole strings with int() - do schoolbook "
            "digit multiplication. Examples: multiply('12', '-34') == '-408', multiply('0', '-5') == '0'."),
        "tests": r'''
import inspect, random, bigmul
from bigmul import multiply
random.seed(7)
cases = [("12", "-34"), ("0", "-5"), ("-0", "7"), ("999", "999"), ("1", "1"), ("-12", "-12"), ("000123", "10"),
         ("123456789", "987654321")]
for _ in range(20):
    a = str(random.randint(-10 ** 40, 10 ** 40)); b = str(random.randint(-10 ** 30, 10 ** 30))
    cases.append((a, b))
for a, b in cases:
    want = str(int(a) * int(b))
    try:
        got = multiply(a, b)
    except Exception as e:
        got = "error %r" % e
    if got != want:
        print("FAIL multiply(%r, %r) = %r, expected %r" % (a, b, got, want))
src = inspect.getsource(bigmul)
if "int(a)" in src or "int(b)" in src:
    print("FAIL converts the whole input with int()")
''',
    },
    {
        "id": "minwindow",
        "file": "minwindow.py",
        "prompt": (
            "Create minwindow.py with a function min_window(s: str, t: str) -> str that returns the shortest "
            "substring of s containing every character of t including duplicates (so t='aab' needs two a's). If "
            "several shortest windows exist return the leftmost one. Return '' if there is none or t is empty. It "
            "must run in O(len(s) + len(t)) time (sliding window). Example: min_window('ADOBECODEBANC', 'ABC') == "
            "'BANC'."),
        "tests": r'''
import time
from minwindow import min_window
cases = [(("ADOBECODEBANC", "ABC"), "BANC"), (("a", "a"), "a"), (("a", "aa"), ""), (("aa", "aa"), "aa"),
         (("", "a"), ""), (("abc", ""), ""), (("ab", "b"), "b"), (("bba", "ab"), "ba"), (("abcabc", "cba"), "abc"),
         (("xaayaa", "aaa"), "aaya"), (("cabwefgewcwaefgcf", "cae"), "cwae")]
for args, want in cases:
    try:
        got = min_window(*args)
    except Exception as e:
        got = "error %r" % e
    if got != want:
        print("FAIL min_window%r = %r, expected %r" % (args, got, want))
s = "ab" * 100000 + "c"
t0 = time.time()
try:
    got = min_window(s, "cab")
    if got != "abc":
        print("FAIL big case = %r" % got[:20])
except Exception as e:
    print("FAIL big case error %r" % e)
if time.time() - t0 > 3:
    print("FAIL too slow on a 200k string (%.1fs)" % (time.time() - t0))
''',
    },
]

_HARD_SOLUTIONS = {
    'bigmul': r'''def multiply(x, y):
    neg = (x[0] == "-") != (y[0] == "-")
    x = x.lstrip("-"); y = y.lstrip("-")
    r = [0] * (len(x) + len(y))
    for i, p in enumerate(reversed(x)):
        for j, q in enumerate(reversed(y)):
            r[i+j] += (ord(p)-48) * (ord(q)-48)
    for k in range(len(r)-1):
        r[k+1] += r[k] // 10; r[k] %= 10
    s = "".join(map(str, reversed(r))).lstrip("0") or "0"
    return "-" + s if neg and s != "0" else s
''',
    'calc': r'''def evaluate(s):
    s = s.replace(" ", ""); i = [0]
    def peek(): return s[i[0]] if i[0] < len(s) else ""
    def expr():
        v = term()
        while peek() in ("+", "-") and peek():
            op = s[i[0]]; i[0] += 1; r = term(); v = v + r if op == "+" else v - r
        return v
    def term():
        v = unary()
        while peek() in ("*", "/") and peek():
            op = s[i[0]]; i[0] += 1; r = unary()
            if op == "*": v = v * r
            else:
                q = abs(v) // abs(r); v = q if (v >= 0) == (r >= 0) else -q
        return v
    def unary():
        if peek() == "-": i[0] += 1; return -unary()
        if peek() == "(":
            i[0] += 1; v = expr(); i[0] += 1; return v
        j = i[0]
        while peek().isdigit(): i[0] += 1
        return int(s[j:i[0]])
    return expr()
''',
    'csvline': r'''def parse_line(line):
    out, cur, q, i = [], "", False, 0
    while i < len(line):
        c = line[i]
        if q:
            if c == '"':
                if i + 1 < len(line) and line[i+1] == '"': cur += '"'; i += 1
                else: q = False
            else: cur += c
        elif c == '"': q = True
        elif c == ',': out.append(cur); cur = ""
        else: cur += c
        i += 1
    out.append(cur); return out
''',
    'lru': r'''from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity): self.c = capacity; self.d = OrderedDict()
    def get(self, k):
        if k not in self.d: return -1
        self.d.move_to_end(k); return self.d[k]
    def put(self, k, v):
        if k in self.d: self.d.move_to_end(k)
        elif len(self.d) >= self.c: self.d.popitem(last=False)
        self.d[k] = v
    def keys(self): return list(self.d)
''',
    'minwindow': r'''from collections import Counter
def min_window(s, t):
    if not t: return ""
    need = Counter(t); miss = len(t); l = 0; best = (0, 10**18)
    for r, c in enumerate(s):
        if need[c] > 0: miss -= 1
        need[c] -= 1
        while miss == 0:
            if r - l < best[1] - best[0]: best = (l, r)
            need[s[l]] += 1
            if need[s[l]] > 0: miss += 1
            l += 1
    return "" if best[1] == 10**18 else s[best[0]:best[1]+1]
''',
    'roman': r'''V = [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]
def to_roman(n):
    out = ""
    for v, s in V:
        while n >= v: out += s; n -= v
    return out
TABLE = {to_roman(n): n for n in range(1, 4000)}
def from_roman(s):
    if s not in TABLE: raise ValueError(s)
    return TABLE[s]
''',
    'topo': r'''import heapq
def order(n, deps):
    ind = [0]*n; adj = [[] for _ in range(n)]
    for a, b in deps: adj[a].append(b); ind[b] += 1
    h = [i for i in range(n) if ind[i] == 0]; heapq.heapify(h); out = []
    while h:
        x = heapq.heappop(h); out.append(x)
        for y in adj[x]:
            ind[y] -= 1
            if ind[y] == 0: heapq.heappush(h, y)
    return out if len(out) == n else None
''',
    'wordbreak': r'''from functools import lru_cache
def sentences(s, words):
    W = set(words)
    @lru_cache(None)
    def go(i):
        if i == len(s): return [""]
        r = []
        for j in range(i+1, len(s)+1):
            if s[i:j] in W:
                for rest in go(j): r.append(s[i:j] + (" " + rest if rest else ""))
        return r
    return sorted(go(0))
''',
}

for _p in _HARD:
    task(_p["id"], _p["file"], "hard", _p["prompt"], _p["tests"], _HARD_SOLUTIONS[_p["id"]])

# ------------------------------------------------------------------ easy
task("clamp", "clamp.py", "easy",
     "Create clamp.py with clamp(x, lo, hi) that returns x limited to the range [lo, hi]. If lo > hi raise ValueError. "
     "Examples: clamp(5, 0, 3) == 3, clamp(-1, 0, 3) == 0, clamp(2, 0, 3) == 2.",
     r'''
from clamp import clamp
for a, w in [((5, 0, 3), 3), ((-1, 0, 3), 0), ((2, 0, 3), 2), ((3, 3, 3), 3), ((2.5, 0, 1), 1)]:
    try:
        g = clamp(*a)
    except Exception as e:
        g = repr(e)
    if g != w: print("FAIL clamp%r = %r, expected %r" % (a, g, w))
try:
    clamp(1, 5, 0); print("FAIL clamp(1, 5, 0) did not raise ValueError")
except ValueError: pass
except Exception as e: print("FAIL clamp(1, 5, 0) raised %r, not ValueError" % e)
''', "def clamp(x, lo, hi):\n    if lo > hi: raise ValueError\n    return max(lo, min(hi, x))\n")

task("fizz", "fizz.py", "easy",
     "Create fizz.py with fizzbuzz(n) that returns a list of strings for 1..n: 'Fizz' for multiples of 3, 'Buzz' "
     "for multiples of 5, 'FizzBuzz' for both, otherwise the number as a string. Example: fizzbuzz(5) == "
     "['1', '2', 'Fizz', '4', 'Buzz'].",
     r'''
from fizz import fizzbuzz
w = ["1","2","Fizz","4","Buzz","Fizz","7","8","Fizz","Buzz","11","Fizz","13","14","FizzBuzz","16"]
g = fizzbuzz(16)
if g != w: print("FAIL fizzbuzz(16) = %r" % (g,))
if fizzbuzz(0) != []: print("FAIL fizzbuzz(0) = %r, expected []" % (fizzbuzz(0),))
''', "def fizzbuzz(n):\n    return ['FizzBuzz' if i%15==0 else 'Fizz' if i%3==0 else 'Buzz' if i%5==0 else str(i) for i in range(1,n+1)]\n")

task("rle", "rle.py", "easy",
     "Create rle.py with encode(s) and decode(s) for run-length encoding: each run becomes the character followed "
     "by its count, e.g. encode('aaabcc') == 'a3b1c2' and decode('a3b1c2') == 'aaabcc'. Counts can be more than "
     "one digit (encode('x'*12) == 'x12'). Characters are letters only. encode('') == ''.",
     r'''
from rle import encode, decode
for s, e in [("aaabcc", "a3b1c2"), ("", ""), ("x"*12, "x12"), ("abc", "a1b1c1"), ("zzzzzzzzzzy", "z10y1")]:
    try:
        if encode(s) != e: print("FAIL encode(%r) = %r, expected %r" % (s, encode(s), e))
        if decode(e) != s: print("FAIL decode(%r) = %r, expected %r" % (e, decode(e), s))
    except Exception as ex: print("FAIL %r: %r" % (s, ex))
''', "import re\ndef encode(s):\n    return ''.join(m.group(1)+str(len(m.group(0))) for m in re.finditer(r'([a-zA-Z])\\1*', s))\ndef decode(s):\n    return ''.join(c*int(n) for c,n in re.findall(r'([a-zA-Z])(\\d+)', s))\n")

task("flatten", "flatten.py", "easy",
     "Create flatten.py with flatten(x) that flattens arbitrarily nested lists into one flat list, keeping order. "
     "Non-list items (including strings and tuples) are kept as they are. Example: flatten([1, [2, [3, [4]]], 5]) "
     "== [1, 2, 3, 4, 5].",
     r'''
from flatten import flatten
for a, w in [([1, [2, [3, [4]]], 5], [1, 2, 3, 4, 5]), ([], []), ([[[]]], []), (["ab", ["c"]], ["ab", "c"]),
             ([(1, 2), [3]], [(1, 2), 3]), ([[1], [[2, 3]], 4], [1, 2, 3, 4])]:
    try: g = flatten(a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL flatten(%r) = %r, expected %r" % (a, g, w))
''', "def flatten(x):\n    out=[]\n    for i in x:\n        out.extend(flatten(i)) if isinstance(i,list) else out.append(i)\n    return out\n")

task("anagram", "anagram.py", "easy",
     "Create anagram.py with group_anagrams(words) that groups words that are anagrams of each other (same letters, "
     "case-sensitive). Return a list of groups; each group sorted alphabetically, and the groups sorted by their "
     "first word. Example: group_anagrams(['eat','tea','tan','ate','nat','bat']) == "
     "[['ate','eat','tea'], ['bat'], ['nat','tan']].",
     r'''
from anagram import group_anagrams
for a, w in [(["eat","tea","tan","ate","nat","bat"], [["ate","eat","tea"],["bat"],["nat","tan"]]), ([], []),
             (["a"], [["a"]]), (["ab","ba","ab"], [["ab","ab","ba"]]), (["Ab","bA","ab"], [["Ab","bA"],["ab"]])]:
    try: g = group_anagrams(a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL group_anagrams(%r) = %r, expected %r" % (a, g, w))
''', "def group_anagrams(words):\n    d={}\n    for w in words: d.setdefault(''.join(sorted(w)),[]).append(w)\n    return sorted((sorted(g) for g in d.values()), key=lambda g:g[0])\n")

task("wordfreq", "wordfreq.py", "easy",
     "Create wordfreq.py with top_words(text, k) that returns the k most common words as (word, count) tuples. "
     "Words are runs of letters (a-z, A-Z) compared in lowercase. Sort by count descending, then alphabetically. "
     "Example: top_words('The cat and the hat. THE end!', 2) == [('the', 3), ('and', 1)].",
     r'''
from wordfreq import top_words
for a, w in [(("The cat and the hat. THE end!", 2), [("the", 3), ("and", 1)]), (("", 3), []),
             (("b a b a c", 5), [("a", 2), ("b", 2), ("c", 1)]), (("it's it's", 2), [("it", 2), ("s", 2)])]:
    try: g = top_words(*a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL top_words%r = %r, expected %r" % (a, g, w))
''', "import re\nfrom collections import Counter\ndef top_words(text,k):\n    c=Counter(w.lower() for w in re.findall('[A-Za-z]+',text))\n    return sorted(c.items(), key=lambda x:(-x[1],x[0]))[:k]\n")

task("countlines", "countlines.sh", "easy",
     "Create an executable bash script countlines.sh that takes one file path argument and prints the number of "
     "non-empty lines in it (lines that contain at least one non-whitespace character). If the file does not "
     "exist, print 'no such file' to stderr and exit with status 1.",
     r'''
import subprocess, os, tempfile
d = tempfile.mkdtemp()
f = os.path.join(d, "t.txt")
open(f, "w").write("a\n\n  \nb\n\tc\n")
r = subprocess.run(["bash", "countlines.sh", f], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
if r.stdout.strip() != "3": print("FAIL countlines.sh on a 3-line file printed %r" % r.stdout)
r = subprocess.run(["bash", "countlines.sh", os.path.join(d, "missing")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
if r.returncode != 1: print("FAIL missing file: exit status %d, expected 1" % r.returncode)
if "no such file" not in r.stderr: print("FAIL missing file: stderr was %r" % r.stderr)
''', "#!/bin/bash\n[ -f \"$1\" ] || { echo 'no such file' >&2; exit 1; }\ngrep -c '[^[:space:]]' \"$1\"\n")

task("slugify", "slugify.js", "easy",
     "Create slugify.js (Node.js, CommonJS) that exports a function slugify(s) via module.exports = slugify. It "
     "lowercases, turns every run of characters that are not a-z or 0-9 into a single '-', and trims '-' from both "
     "ends. Example: slugify('  Hello, World! ') === 'hello-world'.",
     r'''
import subprocess, json
cases = [["  Hello, World! ", "hello-world"], ["", ""], ["A--B__C", "a-b-c"], ["100% Pure", "100-pure"], ["---", ""]]
js = "const s=require(process.cwd()+'/slugify.js');const c=%s;for(const [a,w] of c){let g;try{g=s(a)}catch(e){g=String(e)}if(g!==w)console.log('FAIL slugify('+JSON.stringify(a)+') = '+JSON.stringify(g)+', expected '+JSON.stringify(w))}" % json.dumps(cases)
r = subprocess.run(["node", "-e", js], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=20)
print(r.stdout.strip()) if r.stdout.strip() else None
if r.returncode: print("FAIL node exited %d" % r.returncode)
''', "module.exports = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');\n")

# ------------------------------------------------------------------ medium
task("firstge", "firstge.py", "medium",
     "Create firstge.py with first_ge(arr, x) that, for a sorted list arr, returns the index of the first element "
     ">= x, or len(arr) if there is none. Use binary search (O(log n)); do not import bisect. Example: "
     "first_ge([1, 3, 3, 5], 3) == 1.",
     r'''
import time, inspect, firstge
from firstge import first_ge
import bisect, random
random.seed(3)
for _ in range(300):
    a = sorted(random.randint(0, 20) for _ in range(random.randint(0, 12))); x = random.randint(-2, 22)
    if first_ge(a, x) != bisect.bisect_left(a, x): print("FAIL first_ge(%r, %r) = %r, expected %r" % (a, x, first_ge(a, x), bisect.bisect_left(a, x))); break
big = list(range(0, 2000000, 2)); t = time.time()
for _ in range(2000): first_ge(big, 1234567)
if time.time() - t > 1: print("FAIL not O(log n): 2000 lookups took %.1fs" % (time.time() - t))
if "import bisect" in inspect.getsource(firstge) or "from bisect" in inspect.getsource(firstge): print("FAIL imports bisect")
''', "def first_ge(a,x):\n    lo,hi=0,len(a)\n    while lo<hi:\n        m=(lo+hi)//2\n        if a[m]<x: lo=m+1\n        else: hi=m\n    return lo\n")

task("spiral", "spiral.py", "medium",
     "Create spiral.py with spiral(matrix) that returns the elements of a 2-D list in clockwise spiral order, "
     "starting top-left. Works for non-square and empty matrices. Example: spiral([[1,2,3],[4,5,6],[7,8,9]]) == "
     "[1,2,3,6,9,8,7,4,5].",
     r'''
from spiral import spiral
for a, w in [([[1,2,3],[4,5,6],[7,8,9]], [1,2,3,6,9,8,7,4,5]), ([], []), ([[1]], [1]), ([[1,2,3,4]], [1,2,3,4]),
             ([[1],[2],[3]], [1,2,3]), ([[1,2],[3,4],[5,6]], [1,2,4,6,5,3]), ([[1,2,3],[4,5,6]], [1,2,3,6,5,4])]:
    try: g = spiral([r[:] for r in a])
    except Exception as e: g = repr(e)
    if g != w: print("FAIL spiral(%r) = %r, expected %r" % (a, g, w))
''', "def spiral(m):\n    out=[]\n    m=[r[:] for r in m]\n    while m:\n        out+=m.pop(0)\n        m=[list(r) for r in zip(*m)][::-1]\n    return out\n")

task("brackets", "brackets.py", "medium",
     "Create brackets.py with balanced(s) that returns True if the brackets ()[]{} in s are balanced and correctly "
     "nested; other characters are ignored. Example: balanced('a(b[c]{d}e)f') is True, balanced('(]') is False.",
     r'''
from brackets import balanced
for a, w in [("a(b[c]{d}e)f", True), ("(]", False), ("", True), ("((", False), ("))((", False), ("{[()()]}", True),
             ("x", True), ("([)]", False), ("}", False), ("(((())))", True)]:
    try: g = balanced(a)
    except Exception as e: g = repr(e)
    if g is not w: print("FAIL balanced(%r) = %r, expected %r" % (a, g, w))
''', "def balanced(s):\n    st=[];p={')':'(',']':'[','}':'{'}\n    for c in s:\n        if c in '([{': st.append(c)\n        elif c in p:\n            if not st or st.pop()!=p[c]: return False\n    return not st\n")

task("merge", "merge.py", "medium",
     "Create merge.py with merge(intervals) that merges overlapping or touching closed intervals given as [start, "
     "end] lists, in any order, and returns them sorted. Example: merge([[8,10],[1,3],[2,6],[15,18]]) == "
     "[[1,6],[8,10],[15,18]]; merge([[1,4],[4,5]]) == [[1,5]].",
     r'''
from merge import merge
for a, w in [([[8,10],[1,3],[2,6],[15,18]], [[1,6],[8,10],[15,18]]), ([[1,4],[4,5]], [[1,5]]), ([], []),
             ([[1,10],[2,3]], [[1,10]]), ([[5,5]], [[5,5]]), ([[3,4],[1,2]], [[1,2],[3,4]])]:
    try: g = merge([x[:] for x in a])
    except Exception as e: g = repr(e)
    if g != w: print("FAIL merge(%r) = %r, expected %r" % (a, g, w))
''', "def merge(iv):\n    out=[]\n    for s,e in sorted(iv):\n        if out and s<=out[-1][1]: out[-1][1]=max(out[-1][1],e)\n        else: out.append([s,e])\n    return out\n")

task("rpn", "rpn.py", "medium",
     "Create rpn.py with rpn(expr) that evaluates a space-separated Reverse Polish Notation expression of integers "
     "and + - * /. Division truncates toward zero. Raise ValueError for a malformed expression (too few operands, "
     "leftover operands, or an unknown token). Example: rpn('3 4 + 2 *') == 14, rpn('7 -2 /') == -3.",
     r'''
from rpn import rpn
for a, w in [("3 4 + 2 *", 14), ("7 -2 /", -3), ("5", 5), ("2 3 4 * +", 14), ("10 3 -", 7), ("-7 2 /", -3)]:
    try: g = rpn(a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL rpn(%r) = %r, expected %r" % (a, g, w))
for a in ["+", "1 2", "1 +", "1 2 x", ""]:
    try:
        g = rpn(a); print("FAIL rpn(%r) returned %r instead of raising ValueError" % (a, g))
    except ValueError: pass
    except Exception as e: print("FAIL rpn(%r) raised %r, not ValueError" % (a, e))
''', "def rpn(e):\n    st=[]\n    for t in e.split():\n        if t in '+-*/' :\n            if len(st)<2: raise ValueError\n            b=st.pop();a=st.pop()\n            st.append(a+b if t=='+' else a-b if t=='-' else a*b if t=='*' else (abs(a)//abs(b))*(1 if (a>=0)==(b>=0) else -1))\n        else:\n            try: st.append(int(t))\n            except ValueError: raise ValueError(t)\n    if len(st)!=1: raise ValueError\n    return st[0]\n")

task("ini", "ini.py", "medium",
     "Create ini.py with parse_ini(text) that parses INI text into a dict of sections, each a dict of key -> value "
     "strings. Section lines look like [name]. Key lines look like key = value (strip spaces around key and "
     "value). Ignore blank lines and lines starting with ; or #. Keys before any section go in section ''. Example: "
     "parse_ini('a=1\\n[s]\\nb = 2\\n') == {'': {'a': '1'}, 's': {'b': '2'}}.",
     r'''
from ini import parse_ini
for a, w in [("a=1\n[s]\nb = 2\n", {"": {"a": "1"}, "s": {"b": "2"}}), ("", {}), ("; c\n# d\n[x]\n", {"x": {}}),
             ("[a]\nk = v = w\n", {"a": {"k": "v = w"}}), ("[a]\nk=1\n[a]\nj=2\n", {"a": {"k": "1", "j": "2"}})]:
    try: g = parse_ini(a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL parse_ini(%r) = %r, expected %r" % (a, g, w))
''', "def parse_ini(t):\n    d={};cur=''\n    for l in t.splitlines():\n        s=l.strip()\n        if not s or s[0] in ';#': continue\n        if s.startswith('[') and s.endswith(']'): cur=s[1:-1]; d.setdefault(cur,{}); continue\n        k,_,v=s.partition('='); d.setdefault(cur,{})[k.strip()]=v.strip()\n    return d\n")

task("minstack", "minstack.py", "medium",
     "Create minstack.py with a class MinStack with push(x), pop() (returns the value), top(), and get_min(), all "
     "O(1). pop, top and get_min on an empty stack raise IndexError.",
     r'''
from minstack import MinStack
s = MinStack()
try:
    for x in [5, 3, 7, 3, 1]: s.push(x)
    ok = [s.get_min() == 1, s.pop() == 1, s.get_min() == 3, s.pop() == 3, s.get_min() == 3, s.top() == 7, s.pop() == 7, s.pop() == 3, s.get_min() == 5]
    if not all(ok): print("FAIL wrong values in push/pop/get_min sequence: %r" % ok)
    s.pop()
    for m in ("pop", "top", "get_min"):
        try:
            getattr(s, m)(); print("FAIL %s on empty stack did not raise IndexError" % m)
        except IndexError: pass
except Exception as e: print("FAIL exception %r" % e)
''', "class MinStack:\n    def __init__(self): self.s=[]\n    def push(self,x): self.s.append((x, min(x,self.s[-1][1]) if self.s else x))\n    def pop(self):\n        if not self.s: raise IndexError\n        return self.s.pop()[0]\n    def top(self):\n        if not self.s: raise IndexError\n        return self.s[-1][0]\n    def get_min(self):\n        if not self.s: raise IndexError\n        return self.s[-1][1]\n")

task("deepmerge", "deepmerge.js", "medium",
     "Create deepmerge.js (Node.js, CommonJS) exporting deepMerge(a, b) via module.exports = deepMerge. It returns a "
     "NEW object: keys of both; where both values are plain objects (not arrays, not null) merge them recursively, "
     "otherwise b's value wins. Arrays are replaced, not merged. Neither input may be modified.",
     r'''
import subprocess
js = r"""
const m=require(process.cwd()+'/deepmerge.js');
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const t=(n,g,w)=>{if(!eq(g,w))console.log('FAIL '+n+': got '+JSON.stringify(g)+' expected '+JSON.stringify(w))};
const a={x:1,o:{p:1,q:{r:1}},arr:[1,2],n:null};const b={y:2,o:{q:{s:2},z:3},arr:[3],n:{k:1}};
const A=JSON.stringify(a),B=JSON.stringify(b);
let g;try{g=m(a,b)}catch(e){console.log('FAIL threw '+e);process.exit(0)}
t('merge',g,{x:1,o:{p:1,q:{r:1,s:2},z:3},arr:[3],n:{k:1},y:2});
if(JSON.stringify(a)!==A||JSON.stringify(b)!==B)console.log('FAIL an input was modified');
t('empty',m({}, {}),{});t('override',m({a:{b:1}},{a:5}),{a:5});
"""
r = subprocess.run(["node", "-e", js], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=20)
print(r.stdout.strip()) if r.stdout.strip() else None
if r.returncode: print("FAIL node exited %d" % r.returncode)
''', "const isObj=(v)=>v!==null&&typeof v==='object'&&!Array.isArray(v);\nfunction deepMerge(a,b){const o={...a};for(const k of Object.keys(b)){o[k]=isObj(a[k])&&isObj(b[k])?deepMerge(a[k],b[k]):b[k]}return o}\nmodule.exports=deepMerge;\n")

task("sumargs", "sumargs.sh", "medium",
     "Create a bash script sumargs.sh that prints the sum of all its integer arguments (they may be negative). With "
     "no arguments print 0. If any argument is not an integer, print 'not an integer: X' (X = that argument) to "
     "stderr and exit with status 2. Example: bash sumargs.sh 1 2 -5 prints -2.",
     r'''
import subprocess
def run(*a):
    return subprocess.run(["bash", "sumargs.sh"] + list(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
for a, w in [(("1", "2", "-5"), "-2"), ((), "0"), (("40",), "40"), (("-1", "-1"), "-2")]:
    r = run(*a)
    if r.stdout.strip() != w: print("FAIL sumargs.sh %s printed %r, expected %r" % (" ".join(a), r.stdout.strip(), w))
r = run("3", "x4")
if r.returncode != 2: print("FAIL non-integer: exit status %d, expected 2" % r.returncode)
if "not an integer: x4" not in r.stderr: print("FAIL non-integer: stderr %r" % r.stderr)
''', "#!/bin/bash\ns=0\nfor a in \"$@\"; do [[ $a =~ ^-?[0-9]+$ ]] || { echo \"not an integer: $a\" >&2; exit 2; }; s=$((s+a)); done\necho $s\n")

task("dedupe", "dedupe.py", "medium",
     "Create dedupe.py with dedupe_files(folder) that finds files with identical content anywhere under folder "
     "(recursively) and returns a list of groups. Each group is a sorted list of paths relative to folder (use '/' "
     "separators) with 2 or more files; the groups are sorted by their first path. Empty files count as content.",
     r'''
import os, tempfile
from dedupe import dedupe_files
d = tempfile.mkdtemp()
def w(p, c):
    f = os.path.join(d, p); os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "w").write(c)
w("a.txt", "hello"); w("sub/b.txt", "hello"); w("c.txt", "other"); w("sub/deep/d.txt", "other"); w("e.txt", "unique"); w("x/e1", ""); w("x/e2", "")
try: g = dedupe_files(d)
except Exception as e: g = repr(e)
want = [["a.txt", "sub/b.txt"], ["c.txt", "sub/deep/d.txt"], ["x/e1", "x/e2"]]
if g != want: print("FAIL dedupe_files = %r, expected %r" % (g, want))
''', "import os,hashlib\ndef dedupe_files(folder):\n    g={}\n    for r,_,fs in os.walk(folder):\n        for f in fs:\n            p=os.path.join(r,f); g.setdefault(hashlib.sha256(open(p,'rb').read()).hexdigest(),[]).append(os.path.relpath(p,folder).replace(os.sep,'/'))\n    return sorted((sorted(v) for v in g.values() if len(v)>1), key=lambda v:v[0])\n")

# ------------------------------------------------------------------ hard
task("dijkstra", "dijkstra.py", "hard",
     "Create dijkstra.py with shortest_path(graph, start, goal) where graph is a dict mapping a node to a list of "
     "(neighbor, weight) pairs with non-negative weights. Return (distance, path) with path a list of nodes from "
     "start to goal, or (None, []) if goal is unreachable. If several shortest paths exist, any is fine. "
     "shortest_path(g, a, a) == (0, [a]).",
     r'''
from dijkstra import shortest_path
g = {"a": [("b", 1), ("c", 4)], "b": [("c", 2), ("d", 5)], "c": [("d", 1)], "d": [], "e": [("a", 1)]}
def check(s, t, wd):
    try: d, p = shortest_path(g, s, t)
    except Exception as e: print("FAIL %s->%s raised %r" % (s, t, e)); return
    if d != wd: print("FAIL %s->%s distance %r, expected %r" % (s, t, d, wd)); return
    if wd is None:
        if p != []: print("FAIL unreachable path should be [], got %r" % p)
        return
    if not p or p[0] != s or p[-1] != t: print("FAIL %s->%s path %r does not go from start to goal" % (s, t, p)); return
    cost = 0
    for u, v in zip(p, p[1:]):
        ws = [w for n, w in g.get(u, []) if n == v]
        if not ws: print("FAIL path %r uses a missing edge %s->%s" % (p, u, v)); return
        cost += min(ws)
    if cost != wd: print("FAIL path %r costs %r, not %r" % (p, cost, wd))
check("a", "d", 4); check("a", "a", 0); check("d", "a", None); check("e", "d", 5); check("b", "d", 3)
''', "import heapq\ndef shortest_path(g,s,t):\n    dist={s:0};prev={};pq=[(0,s)]\n    while pq:\n        d,u=heapq.heappop(pq)\n        if u==t:\n            p=[t]\n            while p[-1]!=s: p.append(prev[p[-1]])\n            return d,p[::-1]\n        if d>dist.get(u,1e18): continue\n        for v,w in g.get(u,[]):\n            if d+w<dist.get(v,1e18): dist[v]=d+w;prev[v]=u;heapq.heappush(pq,(d+w,v))\n    return None,[]\n")

task("lcs", "lcs.py", "hard",
     "Create lcs.py with lcs(a, b) that returns one longest common subsequence of strings a and b (characters in "
     "order, not necessarily contiguous). It must be O(len(a)*len(b)) - dynamic programming - and handle strings "
     "of length 2000 in a few seconds. Example: len(lcs('ABCBDAB', 'BDCABA')) == 4.",
     r'''
import time
from lcs import lcs
def is_sub(s, t):
    it = iter(t); return all(c in it for c in s)
for a, b, n in [("ABCBDAB", "BDCABA", 4), ("", "abc", 0), ("abc", "abc", 3), ("abc", "def", 0), ("aaaa", "aa", 2)]:
    try: g = lcs(a, b)
    except Exception as e: print("FAIL lcs(%r, %r) raised %r" % (a, b, e)); continue
    if len(g) != n or not is_sub(g, a) or not is_sub(g, b): print("FAIL lcs(%r, %r) = %r (need a common subsequence of length %d)" % (a, b, g, n))
import random; random.seed(1)
a = "".join(random.choice("ACGT") for _ in range(2000)); b = "".join(random.choice("ACGT") for _ in range(2000))
t = time.time()
try:
    g = lcs(a, b)
    if not (is_sub(g, a) and is_sub(g, b)) or len(g) < 1200: print("FAIL big case: result is not a long common subsequence (len %d)" % len(g))
except Exception as e: print("FAIL big case raised %r" % e)
if time.time() - t > 20: print("FAIL too slow on 2000x2000 (%.1fs)" % (time.time() - t))
''', "def lcs(a,b):\n    n,m=len(a),len(b)\n    L=[[0]*(m+1) for _ in range(n+1)]\n    for i in range(n-1,-1,-1):\n        for j in range(m-1,-1,-1):\n            L[i][j]=L[i+1][j+1]+1 if a[i]==b[j] else max(L[i+1][j],L[i][j+1])\n    i=j=0;o=[]\n    while i<n and j<m:\n        if a[i]==b[j]: o.append(a[i]);i+=1;j+=1\n        elif L[i+1][j]>=L[i][j+1]: i+=1\n        else: j+=1\n    return ''.join(o)\n")

# ------------------------------------------------------------------ fix-a-bug (editing an existing file)
task("fixavg", "stats.py", "medium",
     "stats.py in the working folder has a bug: mean([]) crashes and median() is wrong for even-length lists. Fix "
     "it so mean([]) returns None, median([]) returns None, and median of an even-length list is the average of the "
     "two middle values (median([1, 2, 3, 4]) == 2.5). Keep the function names.",
     r'''
from stats import mean, median
for f, a, w in [(mean, [], None), (mean, [1, 2, 3], 2), (median, [], None), (median, [3, 1, 2], 2), (median, [1, 2, 3, 4], 2.5), (median, [4, 1], 2.5), (median, [5], 5)]:
    try: g = f(a)
    except Exception as e: g = repr(e)
    if g != w: print("FAIL %s(%r) = %r, expected %r" % (f.__name__, a, g, w))
''', "def mean(xs):\n    return sum(xs) / len(xs) if xs else None\n\ndef median(xs):\n    if not xs: return None\n    s = sorted(xs); n = len(s)\n    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2\n")

task("fixcsvsum", "report.py", "medium",
     "report.py in the working folder should print the total of the 'amount' column of sales.csv (also in the "
     "folder), but it crashes. Fix report.py (do not change sales.csv) so that python3 report.py prints just the "
     "total, formatted with two decimals, e.g. 12.50.",
     r'''
import subprocess
r = subprocess.run(["python3", "report.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
if r.stdout.strip() != "1234.56": print("FAIL python3 report.py printed %r (stderr %r), expected '1234.56'" % (r.stdout.strip(), r.stderr.strip()[-200:]))
''', "import csv\nwith open('sales.csv') as f:\n    print('%.2f' % sum(float(r['amount']) for r in csv.DictReader(f)))\n")

task("fixjs", "counter.js", "medium",
     "counter.js in the working folder exports countWords(text), which should return an object mapping each "
     "lowercase word to its count (words are runs of letters a-z, any case). It has bugs. Fix them.",
     r'''
import subprocess, json
js = r"""
const c=require(process.cwd()+'/counter.js');
const t=(a,w)=>{let g;try{g=c(a)}catch(e){g=String(e)}const s=x=>JSON.stringify(Object.keys(x||{}).sort().map(k=>[k,x[k]]));if(typeof g!=='object'||s(g)!==s(w))console.log('FAIL countWords('+JSON.stringify(a)+') = '+JSON.stringify(g)+', expected '+JSON.stringify(w))};
t('The the THE cat',{the:3,cat:1});t('',{});t('a-b a',{a:2,b:1});t('hasOwnProperty x',{hasownproperty:1,x:1});
"""
r = subprocess.run(["node", "-e", js], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=20)
print(r.stdout.strip()) if r.stdout.strip() else None
''', "function countWords(text){const o={};for(const w of (text.toLowerCase().match(/[a-z]+/g)||[]))o[w]=(o[w]||0)+1;return o}\nmodule.exports=countWords;\n")

task("largest", "largest.sh", "medium",
     "Create a bash script largest.sh that takes a folder and prints the 3 largest regular files anywhere under it "
     "(recursively), largest first, one per line as: <size in bytes> <path relative to the folder>. If there are "
     "fewer than 3 files, print all of them. Example line: 2048 logs/app.log",
     r'''
import subprocess, os, tempfile
d = tempfile.mkdtemp()
for p, n in [("a.bin", 300), ("x/b.bin", 5000), ("x/y/c.bin", 1200), ("d.txt", 10), ("x/e.log", 4000)]:
    f = os.path.join(d, p); os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "wb").write(b"z" * n)
r = subprocess.run(["bash", "largest.sh", d], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
want = ["5000 x/b.bin", "4000 x/e.log", "1200 x/y/c.bin"]
got = [l.strip().replace("./", "", 1) if l.strip().split(" ", 1)[-1].startswith("./") else l.strip() for l in r.stdout.strip().splitlines()]
got = [" ".join([g.split(" ", 1)[0], g.split(" ", 1)[1][2:] if g.split(" ", 1)[1].startswith("./") else g.split(" ", 1)[1]]) if " " in g else g for g in got]
if got != want: print("FAIL largest.sh printed %r, expected %r" % (r.stdout.strip().splitlines(), want))
e = tempfile.mkdtemp(); open(os.path.join(e, "only"), "w").write("hi")
r = subprocess.run(["bash", "largest.sh", e], stdout=subprocess.PIPE, universal_newlines=True, timeout=20)
if r.stdout.split() != ["2", "only"]: print("FAIL one-file folder printed %r" % r.stdout)
''', "#!/bin/bash\ncd \"$1\" && find . -type f -printf '%s %P\n' | sort -rn | head -3\n")

# files that are in the work folder before the agent starts (the repair tasks)
_SETUP_FILES = {
    "fixavg": {"stats.py": "def mean(xs):\n    return sum(xs) / len(xs)\n\n\ndef median(xs):\n    s = sorted(xs)\n    return s[len(s) // 2]\n"},
    "fixcsvsum": {"report.py": "import csv\n\ntotal = 0\nwith open('sales.csv') as f:\n    for row in csv.reader(f):\n        total += row['amount']\nprint(total)\n",
                  "sales.csv": "date,item,amount\n2026-01-01,widget,1000.00\n2026-01-02,gadget,200.50\n2026-01-03,gizmo,34.06\n"},
    "fixjs": {"counter.js": "function countWords(text) {\n  const counts = {};\n  for (const w of text.split(' ')) {\n    counts[w] = counts[w] + 1;\n  }\n  return counts;\n}\nmodule.exports = countWords;\n"},
}

for _t in TASKS:
    if _t["id"] in _SETUP_FILES:
        _t["category"] = "repair"
        _t["setup_files"] = _SETUP_FILES[_t["id"]]

WHAT = {
    "calc": "Python: evaluate an arithmetic expression with precedence and parentheses, without eval().",
    "csvline": "Python: split one CSV line into fields, with quotes and escaped quotes.",
    "lru": "Python: an LRU cache with get, put and keys.",
    "topo": "Python: the smallest valid order for tasks with dependencies, or None for a cycle.",
    "wordbreak": "Python: every way to split a string into words from a dictionary.",
    "roman": "Python: convert numbers to Roman numerals and back, and reject bad input.",
    "bigmul": "Python: multiply two very large integers given as strings, without int().",
    "minwindow": "Python: the shortest substring that contains all the characters of another string.",
    "clamp": "Python: limit a number to a range; reject a range whose ends are in the wrong order.",
    "fizz": "Python: the FizzBuzz list for 1 to n.",
    "rle": "Python: run-length encode and decode a string.",
    "flatten": "Python: flatten lists nested to any depth, in order.",
    "anagram": "Python: group words that are anagrams of each other.",
    "wordfreq": "Python: the k most common words in a text, with their counts.",
    "countlines": "Shell: a script that prints the number of non-empty lines in a file.",
    "slugify": "JavaScript: turn a title into a lowercase URL slug.",
    "firstge": "Python: binary search for the first element that is not less than x.",
    "spiral": "Python: the elements of a matrix in clockwise spiral order.",
    "brackets": "Python: check that the brackets ()[]{} in a string match and nest correctly.",
    "merge": "Python: merge intervals that overlap or touch.",
    "rpn": "Python: evaluate a Reverse Polish Notation expression.",
    "ini": "Python: parse INI text into sections of keys and values.",
    "minstack": "Python: a stack that also returns its minimum in constant time.",
    "deepmerge": "JavaScript: merge two nested objects; the values of the second object win.",
    "sumargs": "Shell: a script that prints the sum of its integer arguments and rejects bad arguments.",
    "dedupe": "Python: find files with the same content anywhere under a folder.",
    "dijkstra": "Python: the shortest path in a weighted graph, or None.",
    "lcs": "Python: one longest common subsequence of two strings.",
    "fixavg": "Repair: fix a crash on an empty list and a wrong median in a statistics module.",
    "fixcsvsum": "Repair: fix a script that adds up the amount column of a CSV file.",
    "fixjs": "Repair (JavaScript): fix a word counter that should count lowercase words.",
    "largest": "Shell: a script that prints the 3 largest files under a folder.",
}

REQUIRES = {"slugify": ["node"], "deepmerge": ["node"], "fixjs": ["node"], "countlines": ["bash"], "sumargs": ["bash"],
            "largest": ["bash", "find"]}
