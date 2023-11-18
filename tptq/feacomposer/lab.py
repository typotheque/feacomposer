from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from fontTools.unicodedata.OTTags import DEFAULT_SCRIPT
from ufoLib2 import Font

DEFAULT_LANGUAGE = "dflt"

type Lookup = Callable[[GSUB], tuple[list[str], list[str]]]


def lookup(
    feature: str | None = None,
    script: str | None = None,
    language: str | None = None,
):
    def decorator(lookup: Lookup):
        print(feature, script, language)
        return lookup

    return decorator


def languageSystemsFactory():
    return defaultdict(
        lambda: {DEFAULT_LANGUAGE},  # default value
        {DEFAULT_SCRIPT: {DEFAULT_LANGUAGE}},  # initial content
    )


@dataclass
class GSUB:
    font: Font
    glyphNameFormatter: Callable[[str], str] = lambda x: x
    languageSystems: defaultdict[str, set[str]] = field(default_factory=languageSystemsFactory)

    @lookup("akhn", "latn", "TRK")
    def x(self):
        """
        >>> shape("க்ஷ")
        Taml:kssa
        """
        return ["ka", "virama", "ssa"], ["kssa"]


font = Font()
for char, glyphName in {
    "க": "Taml:ka",
    "்": "Taml:virama",
    "ஷ": "Taml:ssa",
}.items():
    glyph = font.newGlyph(glyphName)
    glyph.unicode = ord(char)

gsub = GSUB(font)
print(gsub.x())


def shape(text: str):
    print(" ".join(["Taml:kssa"]))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
