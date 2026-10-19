"""Short questions: what does this Python program print? The answers are compared as stripped strings.

results/quiz.json counts how many of these 12 questions the model answered right with each method. This release
has no runner for the quiz; the questions are here so that the result can be checked."""

QUESTIONS = [
    ("x = [1, 2, 3]\ny = x\ny.append(4)\nprint(len(x))", "4"),
    ("print(sum(i * i for i in range(1, 6) if i % 2))", "35"),
    ("s = 'banana'\nprint(s.count('an') + s.find('n'))", "4"),
    ("def f(n):\n    return 1 if n < 2 else f(n - 1) + f(n - 2)\nprint(f(10))", "89"),
    ("a = [3, 1, 2]\nb = sorted(a)\na.reverse()\nprint(a[0] * 10 + b[0])", "21"),
    ("d = {}\nfor w in 'the cat the hat the'.split():\n    d[w] = d.get(w, 0) + 1\nprint(max(d.values()) * len(d))", "9"),
    ("print(-7 // 2 + 7 % -3)", "-6"),
    ("x = 0\nfor i in range(5):\n    for j in range(i):\n        x += j\nprint(x)", "10"),
    ("print(len(set('mississippi')) * len('mississippi'))", "44"),
    ("n = 100\nc = 0\nwhile n > 1:\n    n = n // 2 if n % 2 == 0 else 3 * n + 1\n    c += 1\nprint(c)", "25"),
    ("print(int('101', 2) + int('ff', 16) + int('17', 8))", "275"),
    ("a = [[0] * 3] * 3\na[0][0] = 1\nprint(sum(map(sum, a)))", "3"),
]
