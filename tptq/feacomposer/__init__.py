from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import NamedTuple

from fontTools.unicodedata.OTTags import DEFAULT_SCRIPT

DEFAULT_LANGUAGE = "dflt"


@dataclass
class GDEFManager:
    unassigned: set[str] = field(default_factory=set)
    bases: set[str] = field(default_factory=set)
    ligatures: set[str] = field(default_factory=set)
    marks: set[str] = field(default_factory=set)
    components: set[str] = field(default_factory=set)

    @property
    def class_to_glyphs(self) -> dict[int, set[str]]:
        return {
            0: self.unassigned,
            1: self.bases,
            2: self.ligatures,
            3: self.marks,
            4: self.components,
        }


def glyph_class(members: Iterable[str]) -> str:
    return "[" + " ".join(members) + "]"


def target(targeted: str) -> str:
    return targeted + "'"


def lookup(name: str) -> str:
    return f"lookup {name}"


@dataclass
class FeaComposer:
    cmap: dict[int, str] = field(default_factory=dict)
    glyphs: list[str] = field(default_factory=list)
    units_per_em: float = 1000

    # States:

    glyph_classes: dict[str, set[str]] = field(default_factory=dict)

    locales: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(
            lambda: {DEFAULT_LANGUAGE},  # default value
            {DEFAULT_SCRIPT: {DEFAULT_LANGUAGE}},  # initial content
        )
    )

    lookups: list[str] = field(default_factory=list)
    unnamed_lookup_count: int = 0

    gdef_override: GDEFManager = field(default_factory=GDEFManager)

    _root: list[Statement] = field(default_factory=list)
    _current: list[Statement] = field(default_factory=list)

    def __post_init__(self):
        self._current = self._root

    def code(self, *, generate_languagesystems: bool = True) -> str:
        statements = self._root.copy()
        if generate_languagesystems:
            statements = [
                InlineStatement.from_fields("languagesystem", script, language)
                for script, languages in sorted(self.locales.items())
                for language in sorted(languages)
            ] + statements

        lines = list[str]()
        for statement in statements:
            if isinstance(statement, str):
                lines.append(statement)
            else:
                lines.extend(statement.lines(wrap_with_empty_lines=True))

        for index in [0, -1]:
            if not lines[index]:
                lines.pop(index)

        return "".join(i + "\n" for i in lines).replace("\n" * 3, "\n" * 2)

    def append(self, statement: Statement):
        self._current.append(statement)

    def raw(self, line: str):
        self.append(InlineStatement(line))  # HACK

    def comment(self, line: str):
        self.raw("# " + line)

    # Inline statements:

    def inline_statement(self, *fields: str):
        self.append(InlineStatement.from_fields(*fields))

    def glyph_class(self, name: str, members: Iterable[str]) -> str:
        if not name.startswith("@"):
            raise ValueError(f"glyph class name must start with @: {name}")
        if name in self.glyph_classes:
            raise ValueError(f"duplicated glyph class name: {name}")

        self.inline_statement(name, "=", glyph_class(members))

        glyphs = self.glyph_classes[name] = set[str]()
        for member in members:
            if member.startswith("@"):
                glyphs |= self.glyph_classes[member]
            elif "[" in member:  # class literal
                raise NotImplementedError
            else:
                glyphs.add(member)

        return name

    def languagesystem(self, script: str = DEFAULT_SCRIPT, language: str = DEFAULT_LANGUAGE):
        self.inline_statement("languagesystem", script, language)

    def locale(self, script: str = DEFAULT_SCRIPT, language: str = DEFAULT_LANGUAGE):
        self.inline_statement("script", script)
        self.inline_statement("language", language)
        self.locales[script].add(language)

    def sub(self, target: str | Iterable[str], replacement: str | Iterable[str] | None = None):
        if isinstance(target, str):
            target = target.split()

        if replacement is None:
            # `by NULL` cannot be always added because “omitting the `by` clause is equivalent to adding `by NULL`” is only applicable to GSUB type 1 (single substitution) and 8 (reverse chaining single substitution): https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html#5-glyph-substitution-gsub-rules
            self.inline_statement("sub", *target)
        else:
            if isinstance(replacement, str):
                replacement = replacement.split()
            self.inline_statement("sub", *target, "by", *replacement)

    substitute = sub

    def ignore_sub(self, target: str | Iterable[str]):
        if isinstance(target, str):
            target = target.split()
        self.inline_statement("ignore", "sub", *target)

    ignore_substitute = ignore_sub

    def lookup(self, name: str, /):
        if name not in self.lookups:
            raise ValueError(f"unknown lookup name: {name}")
        self.inline_statement("lookup", name)

    # Block statements:

    @contextmanager
    def BlockStatement(self, keyword: str, /, value: str | None = None):
        block = BlockStatement.from_struct(keyword, value, children=[])
        self.append(block)

        parent = self._current  # backup
        try:
            self._current = block.children  # switch
            yield
        finally:
            self._current = parent  # restore

    @contextmanager
    def Lookup(self, name: str | None = None, /, *, flags: Iterable[str] | None = None):
        """
        possible values for `flags`:
        https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html#4d-lookupflag
        """

        if not name:
            self.unnamed_lookup_count += 1
            name = f"anonymous.{self.unnamed_lookup_count}"  # cannot start with a digit
        if name in self.lookups:
            raise ValueError(f"duplicated lookup name: {name}")
        self.lookups.append(name)

        with self.BlockStatement("lookup", name):
            if flags := list(flags or []):
                self.inline_statement("lookupflag", *flags)

            yield name

            if flags:
                self.inline_statement("lookupflag", "0")

    @contextmanager
    def Feature(self, tag: str, /, *, name: str | None = None):
        with self.BlockStatement("feature", tag):
            if name is not None:
                with self.BlockStatement("featureNames"):
                    self.inline_statement("name", f'"{name}"')
            yield


class InlineStatement(str):
    @classmethod
    def from_fields(cls, *fields: str) -> InlineStatement:
        return cls(" ".join(fields) + ";")


class BlockStatement(NamedTuple):
    prefix: str
    children: list[Statement]
    suffix: str

    @classmethod
    def from_struct(
        cls, keyword: str, /, value: str | None = None, *, children: list[Statement]
    ) -> BlockStatement:
        if value:
            prefix = keyword + " " + value + " {"
            suffix = "} " + value + ";"
        else:
            prefix = keyword + " {"
            suffix = "};"
        return cls(prefix, children, suffix)

    def lines(
        self, indentation: str = " " * 4, wrap_with_empty_lines: bool = False
    ) -> Iterator[str]:
        if wrap_with_empty_lines:
            yield ""

        yield self.prefix
        for statement in self.children:
            if isinstance(statement, str):
                yield indentation + statement
            else:
                for line in statement.lines(wrap_with_empty_lines=wrap_with_empty_lines):
                    if line:
                        line = indentation + line
                    yield line
        yield self.suffix

        if wrap_with_empty_lines:
            yield ""


Statement = InlineStatement | BlockStatement


@dataclass
class Option:
    stylistic_set: tuple[int, str] | None = None
    """number (1 to 20) and name"""

    locales: dict[str, set[str]] = field(default_factory=dict)
    """OpenType script tag to language tags"""

    lookups: set[str] = field(default_factory=set)
    """lookup names"""


@dataclass(frozen=True)
class OptionManager:
    options: list[Option]

    def __post_init__(self):
        numbers = set[int]()  # validate stylistic set numbers
        for option in self.options:
            if stylistic_set := option.stylistic_set:
                number, _ = stylistic_set
                if number not in range(1, 20 + 1):
                    raise ValueError(f"stylistic set number is out of the range [1, 20]: {number}")
                elif number in numbers:
                    raise ValueError(f"stylistic set number is duplicated: {number}")
                else:
                    numbers.add(number)

    def locale_to_lookups(self) -> dict[tuple[str, str], set[str]]:
        locales = defaultdict[str, set[str]](set)
        for option in self.options:
            for script, languages in option.locales.items():
                locales[script].update(languages)

        locale_to_lookups = dict[tuple[str, str], set[str]]()
        for script, languages in locales.items():
            for language in languages:
                locale_to_lookups[script, language] = {
                    j
                    for i in self.options
                    if language in i.locales.get(script, [])
                    for j in i.lookups
                }

        return locale_to_lookups
