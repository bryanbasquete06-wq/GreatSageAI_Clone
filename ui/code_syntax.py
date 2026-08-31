"""
Elívea — CodeDock Syntax Highlighter Engine
=====================================================
Highlighter de sintaxe leve (QSyntaxHighlighter) usado pelo editor da Ala de
Programação. As cores seguem a paleta viva do tema ＜Elivea＞ (ui.qt_ui.C),
então o editor muda junto com os 5 temas em tempo real.

Linguagens: Python, Java, Kotlin, C, C++, C#, Rust, Go, SQL, JS, TS, HTML,
CSS, JSON, Shell/Batch, YAML, XML e Markdown.
"""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

# ---------------------------------------------------------------------------
# Detecção de linguagem por extensão
# ---------------------------------------------------------------------------

_EXT_MAP = {
    # Python
    "py": "python", "pyw": "python", "pyi": "python",
    # Web
    "html": "html", "htm": "html", "xhtml": "html",
    "css": "css", "scss": "css", "less": "css",
    "js": "javascript", "mjs": "javascript", "jsx": "javascript", "cjs": "javascript",
    "ts": "typescript", "tsx": "typescript",
    # Java / JVM
    "java": "java", "kt": "kotlin", "kts": "kotlin",
    # Família C
    "c": "c", "h": "c",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp", "hh": "cpp", "hxx": "cpp",
    "cs": "csharp",
    # Rust / Go
    "rs": "rust", "go": "go",
    # Dados / script / markup
    "json": "json", "sql": "sql",
    "sh": "shell", "bash": "shell", "bat": "shell", "cmd": "shell", "ps1": "shell",
    "md": "markdown", "rst": "markdown",
    "yml": "yaml", "yaml": "yaml",
    "xml": "xml",
}

LANG_NAMES = {
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "html": "HTML", "css": "CSS", "java": "Java", "kotlin": "Kotlin", "c": "C",
    "cpp": "C++", "csharp": "C#", "rust": "Rust", "go": "Go", "sql": "SQL",
    "json": "JSON", "shell": "Shell", "markdown": "Markdown", "yaml": "YAML",
    "xml": "XML", "text": "Texto puro",
}


def detect_language(filename: str) -> str:
    """Devolve a chave de linguagem a partir do nome de um arquivo."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _EXT_MAP.get(ext, "text")


# ---------------------------------------------------------------------------
# Palavras-chave e builtins por linguagem
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, set[str]] = {
    "python": {
        "False", "None", "True", "and", "as", "assert", "async", "await", "break",
        "class", "continue", "def", "del", "elif", "else", "except", "finally",
        "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
        "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "match", "case", "type",
    },
    "javascript": {
        "async", "await", "break", "case", "catch", "class", "const", "continue",
        "debugger", "default", "delete", "do", "else", "enum", "export", "extends",
        "false", "finally", "for", "function", "get", "if", "import", "in",
        "instanceof", "let", "new", "null", "of", "return", "set", "static",
        "super", "switch", "this", "throw", "true", "try", "typeof", "undefined",
        "var", "void", "while", "with", "yield",
    },
    "typescript": {
        "abstract", "any", "as", "async", "await", "boolean", "break", "case",
        "catch", "class", "const", "continue", "debugger", "declare", "default",
        "delete", "do", "else", "enum", "export", "extends", "false", "finally",
        "for", "from", "function", "get", "if", "implements", "import", "in",
        "infer", "instanceof", "interface", "is", "keyof", "let", "namespace",
        "never", "new", "null", "number", "object", "of", "readonly", "record",
        "return", "satisfies", "set", "static", "string", "super", "switch",
        "symbol", "this", "throw", "true", "try", "type", "typeof", "undefined",
        "unique", "unknown", "var", "void", "while", "with", "yield",
    },
    "java": {
        "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
        "class", "const", "continue", "default", "do", "double", "else", "enum",
        "extends", "final", "finally", "float", "for", "goto", "if", "implements",
        "import", "instanceof", "int", "interface", "long", "native", "new",
        "null", "package", "private", "protected", "public", "record", "return",
        "sealed", "short", "static", "strictfp", "super", "switch", "synchronized",
        "this", "throw", "throws", "transient", "true", "false", "try", "var",
        "void", "volatile", "while", "yield",
    },
    "kotlin": {
        "abstract", "actual", "annotation", "as", "break", "by", "catch", "class",
        "companion", "const", "constructor", "continue", "crossinline", "data",
        "do", "else", "enum", "expect", "external", "false", "final", "finally",
        "for", "fun", "get", "if", "import", "in", "init", "inline", "inner",
        "interface", "internal", "is", "lateinit", "noinline", "null", "object",
        "open", "operator", "out", "override", "package", "private", "protected",
        "public", "reified", "return", "sealed", "set", "super", "suspend",
        "tailrec", "this", "throw", "true", "try", "typealias", "typeof", "val",
        "var", "vararg", "when", "where", "while",
    },
    "c": {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
        "unsigned", "void", "volatile", "while", "true", "false",
    },
    "cpp": {
        "alignas", "alignof", "and", "asm", "auto", "bool", "break", "case",
        "catch", "char", "class", "concept", "const", "consteval", "constexpr",
        "constinit", "const_cast", "continue", "co_await", "co_return", "co_yield",
        "decltype", "default", "delete", "do", "double", "dynamic_cast", "else",
        "enum", "explicit", "export", "extern", "false", "float", "for", "friend",
        "goto", "if", "inline", "int", "long", "mutable", "namespace", "new",
        "noexcept", "not", "nullptr", "operator", "or", "private", "protected",
        "public", "register", "reinterpret_cast", "requires", "return", "short",
        "signed", "sizeof", "static", "static_assert", "static_cast", "struct",
        "switch", "template", "this", "thread_local", "throw", "true", "try",
        "typedef", "typeid", "typename", "union", "unsigned", "using", "virtual",
        "void", "volatile", "wchar_t", "while", "xor",
    },
    "csharp": {
        "abstract", "as", "async", "await", "base", "bool", "break", "byte",
        "case", "catch", "char", "checked", "class", "const", "continue",
        "decimal", "default", "delegate", "do", "double", "else", "enum", "event",
        "explicit", "extern", "false", "finally", "fixed", "float", "for",
        "foreach", "goto", "if", "implicit", "in", "init", "int", "interface",
        "internal", "is", "lock", "long", "namespace", "new", "null", "object",
        "operator", "out", "override", "params", "private", "protected", "public",
        "readonly", "record", "ref", "return", "sealed", "short", "sizeof",
        "stackalloc", "static", "string", "struct", "switch", "this", "throw",
        "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort",
        "using", "virtual", "void", "volatile", "while",
    },
    "rust": {
        "as", "async", "await", "break", "const", "continue", "crate", "dyn",
        "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in", "let",
        "loop", "match", "mod", "move", "mut", "pub", "ref", "return", "self",
        "Self", "static", "struct", "super", "trait", "true", "try", "type",
        "union", "unsafe", "use", "where", "while",
        "Option", "Result", "String", "Vec", "Some", "None", "Ok", "Err",
    },
    "go": {
        "break", "case", "chan", "const", "continue", "default", "defer", "else",
        "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
        "map", "package", "range", "return", "select", "struct", "switch", "type",
        "var", "true", "false", "nil",
    },
    "sql": {
        "select", "from", "where", "insert", "into", "values", "update", "set",
        "delete", "create", "alter", "drop", "table", "index", "view", "join",
        "inner", "outer", "left", "right", "full", "cross", "on", "as", "and",
        "or", "not", "null", "is", "in", "exists", "between", "like", "order",
        "by", "group", "having", "limit", "offset", "distinct", "case", "when",
        "then", "else", "end", "union", "all", "primary", "key", "foreign",
        "references", "constraint", "default", "check", "unique", "auto_increment",
        "commit", "rollback", "begin", "transaction", "grant", "revoke", "with",
    },
    "json": set(),
    "shell": {
        "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done",
        "case", "esac", "in", "return", "break", "continue", "echo", "read",
        "export", "set", "unset", "source", "shift", "local", "exit", "true",
        "false", "function", "select", "cd", "pwd", "ls", "cp", "mv", "rm", "mkdir",
        "touch", "cat", "grep", "sed", "awk", "find", "sudo", "git", "python",
        "pip", "pip3", "node", "npm", "npx",
    },
    "yaml": {"true", "false", "null", "yes", "no", "on", "off"},
}

_BUILTINS: dict[str, set[str]] = {
    "python": {
        "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
        "bytes", "callable", "chr", "classmethod", "compile", "complex", "delattr",
        "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter", "float",
        "format", "frozenset", "getattr", "globals", "hasattr", "hash", "help",
        "hex", "id", "input", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "pow", "print", "property", "range", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
        "str", "sum", "super", "tuple", "type", "vars", "zip", "__import__",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "AssertionError", "StopIteration", "RuntimeError",
    },
    "javascript": {
        "console", "Math", "JSON", "Promise", "Set", "Map", "Object", "Array",
        "Number", "String", "Boolean", "Date", "parseInt", "parseFloat", "isNaN",
        "fetch", "setTimeout", "setInterval",
    },
    "typescript": {
        "console", "Math", "JSON", "Promise", "Set", "Map", "Object", "Array",
        "Number", "String", "Boolean", "Date", "fetch", "Record", "Partial",
        "Pick", "Omit", "Readonly",
    },
    "rust": {"std", "println!", "vec!", "format!", "panic!"},
}

# Comentários em bloco (se houver) e comentários de linha
_BLOCK_COMMENTS: dict[str, tuple[str, str]] = {
    "javascript": ("/*", "*/"), "typescript": ("/*", "*/"), "java": ("/*", "*/"),
    "kotlin": ("/*", "*/"), "cpp": ("/*", "*/"), "c": ("/*", "*/"),
    "csharp": ("/*", "*/"), "rust": ("/*", "*/"), "go": ("/*", "*/"),
    "sql": ("/*", "*/"), "css": ("/*", "*/"),
    "html": ("<!--", "-->"), "xml": ("<!--", "-->"),
}

_LINE_COMMENTS: dict[str, str] = {
    "python": "#", "javascript": "//", "typescript": "//", "java": "//",
    "kotlin": "//", "cpp": "//", "c": "//", "csharp": "//", "rust": "//",
    "go": "//", "sql": "--", "shell": "#", "yaml": "#",
}

_TRIPLE_STRINGS: dict[str, tuple[str, str]] = {
    "python": ('"""', "'''"),
}


def _make_fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class CodeHighlighter(QSyntaxHighlighter):
    """Highlighter multi-linguagem com cores do tema do Elívea.

    Estados por bloco: 1 → dentro de comentário em bloco (/* */ ou <!-- -->);
    2 → dentro de string tripla ('''''').

    """

    _S_COMMENT = 1
    _S_TRIPLE = 2

    def __init__(self, document, language: str = "python"):
        super().__init__(document)
        self.language = language
        self.rules: list = []
        self._comment_start = ""
        self._comment_end = ""
        self._line_mark: str | None = None
        self._triples: tuple[str, str] | None = None
        self._comment_fmt = _make_fmt("#888888", italic=True)
        self._string_fmt = _make_fmt("#7dff9e")
        self.refresh_theme()

    # ------------------------------------------------------------------ cores

    @staticmethod
    def _theme_colors() -> dict:
        """Paleta viva do Elívea (lazy import para evitar ciclos)."""
        try:
            from ui.qt_ui import C
        except Exception:
            C = None
        if C is None:
            return {
                "text": "#dff4ff", "comment": "#5f88ad", "string": "#7dff9e",
                "keyword": "#4fd8ff", "builtin": "#aef0ff", "number": "#ffd76a",
                "func": "#22b8f0", "class": "#aef0ff", "attr": "#ffd76a",
            }
        return {
            "text": C.TEXT, "comment": C.TEXT_DIM, "string": C.GREEN,
            "keyword": C.PRI, "builtin": C.ACC, "number": C.GOLD,
            "func": C.ACC2, "class": C.ACC, "attr": C.GOLD,
        }

    def refresh_theme(self):
        """Recompila as regras com as cores atuais do tema."""
        p = self._theme_colors()
        self.rules = []
        lang = self.language

        kws = _KEYWORDS.get(lang, set())
        if kws:
            pat = r"\b(" + "|".join(sorted(kws, key=len, reverse=True)) + r")\b"
            self.rules.append((re.compile(pat), _make_fmt(p["keyword"], bold=True)))

        built = _BUILTINS.get(lang, set())
        if built:
            pat = r"\b(" + "|".join(sorted(built, key=len, reverse=True)) + r")\b"
            self.rules.append((re.compile(pat), _make_fmt(p["builtin"])))

        if lang not in ("html", "css"):
            self.rules.append((
                re.compile(r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|"
                           r"\d[\d_]*(?:\.[\d_]+)?(?:[eE][+-]?\d+)?)\b"),
                _make_fmt(p["number"])))

        # strings de uma linha
        if lang in ("python", "javascript", "typescript", "java", "kotlin",
                    "c", "cpp", "csharp", "rust", "go", "json", "yaml"):
            str_pat = r"""(["\'])(?:\\.|[^\\\n])*?\1"""
            self.rules.append((re.compile(str_pat), _make_fmt(p["string"])))

        # assinaturas nomeadas
        if lang == "python":
            self.rules.append((re.compile(r"\b(def|class)\s+(\w+)"),
                               _make_fmt(p["func"], bold=True)))
            self.rules.append((re.compile(r"@[\w.]+[()]?"), _make_fmt(p["attr"])))
        elif lang in ("javascript", "typescript"):
            self.rules.append((re.compile(r"\b(function|class)\s+(\w+)"),
                               _make_fmt(p["func"], bold=True)))
        elif lang == "go":
            self.rules.append((re.compile(r"\b(func|type|struct|interface)\s+(\w+)"),
                               _make_fmt(p["func"], bold=True)))
        elif lang in ("c", "cpp", "csharp", "java", "kotlin"):
            self.rules.append((re.compile(r"\b(class|struct|enum|interface|record)\s+(\w+)"),
                               _make_fmt(p["class"], bold=True)))
        elif lang == "rust":
            self.rules.append((re.compile(r"\b(fn|struct|enum|trait)\s+(\w+)"),
                               _make_fmt(p["func"], bold=True)))

        if lang in ("html", "xml"):
            self.rules.append((re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*"),
                               _make_fmt(p["func"], bold=True)))
            self.rules.append((re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:.-]*(?==)"),
                               _make_fmt(p["attr"])))

        self._comment_fmt = _make_fmt(p["comment"], italic=True)
        self._string_fmt = _make_fmt(p["string"])
        self._line_mark = _LINE_COMMENTS.get(lang)
        block = _BLOCK_COMMENTS.get(lang)
        self._comment_start, self._comment_end = block if block else ("", "")
        self._triples = _TRIPLE_STRINGS.get(lang)

    def set_language(self, language: str):
        if language != self.language:
            self.language = language
            self.refresh_theme()
            self.rehighlight()

    # ------------------------------------------------------------------ core

    def highlightBlock(self, text: str):
        # 1) regras simples (keywords, números, strings curtas, assinaturas)
        for pat, fmt in getattr(self, "rules", []):
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        # 2) comentário de linha — força por cima das regras genéricas
        if self._line_mark:
            idx = text.find(self._line_mark)
            if idx != -1:
                self.setFormat(idx, len(text) - idx, self._comment_fmt)

        # 3) estado de comentários em bloco / string tripla (multi-linha)
        self._apply_block_states(text)

    def _apply_block_states(self, text: str):
        prev = self.previousBlockState()
        state = (self._S_COMMENT if prev == self._S_COMMENT
                 else self._S_TRIPLE if prev == self._S_TRIPLE else 0)
        n = len(text)
        i = 0

        while i < n:
            if state == self._S_COMMENT and self._comment_start:
                end = text.find(self._comment_end, i)
                if end == -1:
                    self.setFormat(i, n - i, self._comment_fmt)
                    self.setCurrentBlockState(self._S_COMMENT)
                    return
                self.setFormat(i, end - i + len(self._comment_end), self._comment_fmt)
                i = end + len(self._comment_end)
                state = 0
            elif state == self._S_TRIPLE and self._triples:
                close = self._triples[0]  # """ (preferência por aspas duplas)
                end = text.find(close, i)
                if end == -1:
                    self.setFormat(i, n - i, self._string_fmt)
                    self.setCurrentBlockState(self._S_TRIPLE)
                    return
                self.setFormat(i, end - i + len(close), self._string_fmt)
                i = end + len(close)
                state = 0
            else:
                # procura o próximo início (bloco-comentário ou string tripla)
                starts: list[tuple[int, str]] = []
                if self._comment_start:
                    pos = text.find(self._comment_start, i)
                    if pos != -1:
                        starts.append((pos, "c"))
                if self._triples:
                    for marker in self._triples:
                        pos = text.find(marker, i)
                        if pos != -1:
                            starts.append((pos, "t"))
                if not starts:
                    break
                starts.sort(key=lambda x: x[0])
                pos, kind = starts[0]

                if kind == "c":
                    end = text.find(self._comment_end, pos + len(self._comment_start))
                    if end == -1:
                        self.setFormat(pos, n - pos, self._comment_fmt)
                        self.setCurrentBlockState(self._S_COMMENT)
                        return
                    self.setFormat(pos, end - pos + len(self._comment_end), self._comment_fmt)
                    i = end + len(self._comment_end)
                else:
                    marker = self._triples[0]
                    end = text.find(marker, pos + len(marker))
                    if end == -1:
                        self.setFormat(pos, n - pos, self._string_fmt)
                        self.setCurrentBlockState(self._S_TRIPLE)
                        return
                    self.setFormat(pos, end - pos + len(marker), self._string_fmt)
                    i = end + len(marker)

        self.setCurrentBlockState(0)