# -*- coding: utf-8 -*-
"""Convert the small LaTeX subset used in the book sources to Unicode text,
and split math strings into (text, script) segments for Word runs."""

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "Theta": "Θ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "Lambda": "Λ", "mu": "μ",
    "nu": "ν", "xi": "ξ", "Xi": "Ξ", "pi": "π", "Pi": "Π", "rho": "ρ",
    "sigma": "σ", "Sigma": "Σ", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ",
    "Delta": "Δ", "omega": "ω", "Omega": "Ω",
}

SYMBOLS = {
    "in": "∈", "notin": "∉", "ni": "∋", "subseteq": "⊆", "subset": "⊂",
    "supseteq": "⊇", "supset": "⊃", "cup": "∪", "cap": "∩",
    "bigcup": "⋃", "bigcap": "⋂", "setminus": "∖", "backslash": "∖",
    "times": "×", "cdot": "·", "cdots": "⋯", "ldots": "…", "dots": "…",
    "circ": "∘", "sim": "∼", "simeq": "≃", "approx": "≈", "equiv": "≡", "cong": "≅",
    "neq": "≠", "ne": "≠", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "to": "→", "rightarrow": "→", "longrightarrow": "⟶", "mapsto": "↦",
    "Rightarrow": "⇒", "Longrightarrow": "⟹", "Leftarrow": "⇐",
    "leftrightarrow": "↔", "Leftrightarrow": "⇔", "Longleftrightarrow": "⟺",
    "iff": "⟺", "forall": "∀", "exists": "∃", "nexists": "∄",
    "neg": "¬", "lnot": "¬", "wedge": "∧", "land": "∧", "vee": "∨",
    "lor": "∨", "models": "⊨", "vdash": "⊢", "mid": " | ",
    "langle": "⟨", "rangle": "⟩", "llbracket": "⟦", "rrbracket": "⟧",
    "upharpoonright": "↾", "restriction": "↾", "infty": "∞",
    "varnothing": "∅", "emptyset": "∅", "wp": "℘", "ell": "ℓ",
    "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫",
    "rightharpoonup": "⇀", "rightleftharpoons": "⇌", "hookrightarrow": "↪",
    "bigwedge": "⋀", "bigvee": "⋁", "top": "⊤", "bot": "⊥",
    "sqcup": "⊔", "sqcap": "⊓", "downarrow": "↓", "uparrow": "↑",
    "star": "⋆", "bullet": "•", "oplus": "⊕", "otimes": "⊗",
    "propto": "∝", "perp": "⊥", "parallel": "∥", "angle": "∠",
    "triangle": "△", "square": "□", "checkmark": "✓",
    "quad": "  ", "qquad": "    ", ",": " ", ";": " ", ":": " ",
    "!": "", " ": " ",
    "left": "", "right": "", "bigl": "", "bigr": "", "Bigl": "", "Bigr": "",
    "big": "", "Big": "", "bigg": "", "Bigg": "", "Bigm": "", "bigm": "",
    "displaystyle": "", "textstyle": "", "limits": "",
    "ker": "ker", "sup": "sup", "inf": "inf", "log": "log", "ln": "ln",
    "sin": "sin", "cos": "cos", "tan": "tan", "max": "max", "min": "min",
    "det": "det", "dim": "dim", "lim": "lim", "Pr": "Pr",
}

SPECIAL = {
    "\\not\\sim": "≁", "\\not\\in": "∉", "\\not=": "≠", "\\neq": "≠",
    "\\not\\models": "⊭", "\\not\\equiv": "≢",
    "\\{": "{", "\\}": "}", "\\%": "%", "\\&": "&", "\\#": "#",
    "\\_": "_", "\\$": "$", "\\\\": " ",
}


def _group(s, i):
    """s[i] == '{'; return (content, index after matching '}')."""
    depth = 1
    j = i + 1
    start = j
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:j], j + 1
        j += 1
    return s[start:], len(s)


def tex_to_unicode(s):
    for k, v in SPECIAL.items():
        s = s.replace(k, v)
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        # backslash
        if i + 1 >= n:
            out.append("\\")
            break
        nxt = s[i + 1]
        if nxt in "{}%$#&_":
            out.append(nxt)
            i += 2
            continue
        j = i + 1
        while j < n and s[j].isalpha():
            j += 1
        if j == i + 1:
            # e.g. "\ " handled in SPECIAL already
            out.append(nxt)
            i += 2
            continue
        name = s[i + 1:j]
        if name in ("mathrm", "mathbf", "mathbb", "mathit", "mathcal", "text", "operatorname", "xrightarrow", "xRightarrow", "overline"):
            k = j
            while k < n and s[k] == " ":
                k += 1
            if k < n and s[k] == "{":
                arg, k2 = _group(s, k)
                if name in ("xrightarrow", "xRightarrow"):
                    lab = tex_to_unicode(arg).strip()
                    arr = "→" if name == "xrightarrow" else "⇒"
                    out.append(("—" + lab + arr) if lab else arr)
                elif name == "mathbb":
                    out.append({"N": "ℕ", "R": "ℝ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ"}.get(
                        arg.strip(), tex_to_unicode(arg)))
                elif name == "overline":
                    out.append(tex_to_unicode(arg) + "\u0304")
                else:
                    out.append(tex_to_unicode(arg))
                i = k2
                continue
            i = j
            continue
        if name in SYMBOLS:
            out.append(SYMBOLS[name])
        elif name in GREEK:
            out.append(GREEK[name])
        else:
            out.append(name)
        i = j
    return "".join(out)


# Characters that are fine to italicise when they appear alone.
GREEK_CHARS = set("αβγδεζηθικλμνξπρστυφχψω")


def math_segments(s):
    """Split a math string into [(text, mode)] where mode in {'n','sub','sup'}.

    The input may still contain LaTeX commands; they are converted per chunk.
    """
    segs = []
    buf = []
    i = 0
    n = len(s)

    def flush():
        if buf:
            segs.append((tex_to_unicode("".join(buf)), "n"))
            buf.clear()

    while i < n:
        c = s[i]
        if c in "_^":
            flush()
            mode = "sub" if c == "_" else "sup"
            i += 1
            if i < n and s[i] == "{":
                arg, i = _group(s, i)
            elif i < n and s[i] == "\\":
                j = i + 1
                while j < n and s[j].isalpha():
                    j += 1
                arg = s[i:j]
                i = j
            elif i < n:
                arg = s[i]
                i += 1
            else:
                arg = ""
            segs.append((tex_to_unicode(arg), mode))
        else:
            buf.append(c)
            i += 1
    flush()
    return segs


def split_italic(text):
    """Split text into runs [(chunk, italic)] for single Latin/Greek letters."""
    runs = []
    buf = []
    for ch in text:
        is_letter = (ch.isascii() and ch.isalpha()) or (ch in GREEK_CHARS)
        if is_letter:
            buf.append(ch)
        else:
            if buf:
                word = "".join(buf)
                runs.append((word, len(word) == 1))
                buf.clear()
            runs.append((ch, False))
    if buf:
        word = "".join(buf)
        runs.append((word, len(word) == 1))
    # merge adjacent same-italic chunks
    merged = []
    for chunk, it in runs:
        if merged and merged[-1][1] == it:
            merged[-1] = (merged[-1][0] + chunk, it)
        else:
            merged.append((chunk, it))
    return merged
