from collections import defaultdict
from collections.abc import Callable
from io import BytesIO

import uharfbuzz as hb
from fontTools.feaLib.ast import (
    FeatureBlock,
    FeatureFile,
    GlyphName,
    LanguageSystemStatement,
    LigatureSubstStatement,
    LookupBlock,
    LookupReferenceStatement,
)
from fontTools.ttLib import TTFont
from fontTools.unicodedata.OTTags import DEFAULT_SCRIPT
from ufo2ft import compileTTF
from ufoLib2 import Font

DEFAULT_LANGUAGE = "dflt"

languageSystems = defaultdict(
    lambda: {DEFAULT_LANGUAGE},  # default value
    {DEFAULT_SCRIPT: {DEFAULT_LANGUAGE}},  # initial content
)
languageSystems["taml"]


def GlyphNameFormatter(shorthand: str) -> GlyphName:
    return GlyphName("Taml:" + shorthand)


type Lookup = Callable[[], list[LigatureSubstStatement]]
lookupToFeatures: dict[Lookup, set[str]] = {}


def lookup(
    feature: str | set[str] | None = None,
    script: str = DEFAULT_SCRIPT,
    language: str = DEFAULT_LANGUAGE,
):
    def decorator(lookup: Lookup):
        if feature:
            lookupToFeatures[lookup] = {feature} if isinstance(feature, str) else feature
        return lookup

    return decorator


def ligate(input: list[str], output: str) -> LigatureSubstStatement:
    return LigatureSubstStatement(
        prefix=[],
        glyphs=[GlyphNameFormatter(i) for i in input],
        suffix=[],
        replacement=GlyphNameFormatter(output),
        forceChain=False,
    )


@lookup("akhn")
def kssa():
    """
    >>> shape("க்ஷ")
    Taml:kssa
    """

    return [
        ligate(["ka", "virama", "ssa"], "kssa"),
    ]


ufo = Font()
for glyphName, char in {
    "Taml:ka": "க",
    "Taml:virama": "்",
    "Taml:ssa": "ஷ",
    "Taml:kssa": None,
}.items():
    glyph = ufo.newGlyph(glyphName)
    if char:
        glyph.unicode = ord(char)


def makeHbFont(ufo: Font) -> hb.Font:  # type:ignore
    featureFile = FeatureFile()
    featureFile.statements.extend(
        LanguageSystemStatement(k, i) for k, v in languageSystems.items() for i in sorted(v)
    )
    for lookup, features in lookupToFeatures.items():
        featureFile.statements.append(lookupBlock := LookupBlock(lookup.__name__))
        lookupBlock.statements.extend(lookup())
        for feature in features:
            featureFile.statements.append(x := FeatureBlock(feature))
            x.statements.append(LookupReferenceStatement(lookupBlock))

    ufo.features = featureFile.asFea()
    ttf: TTFont = compileTTF(ufo)

    with BytesIO() as f:
        ttf.save(f)
        data = f.getvalue()

    return hb.Font(hb.Face(data))  # type:ignore


hbFont = makeHbFont(ufo)


def shape(text: str):
    buffer = hb.Buffer()  # type: ignore
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hbFont, buffer)  # type: ignore
    glyphNames: list[str] = []
    for info in buffer.glyph_infos:
        glyphNames.append(hbFont.glyph_to_string(info.codepoint))
    print(" ".join(glyphNames))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
