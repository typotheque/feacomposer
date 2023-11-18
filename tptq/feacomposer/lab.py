from collections import defaultdict
from collections.abc import Callable
from io import BytesIO

import uharfbuzz as hb
from fontTools.feaLib.ast import FeatureBlock, FeatureFile
from fontTools.feaLib.ast import GlyphName as _GlyphName
from fontTools.feaLib.ast import (
    LanguageSystemStatement,
    LigatureSubstStatement,
    LookupBlock,
    LookupReferenceStatement,
    Statement,
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


def GlyphName(shorthand: str) -> _GlyphName:
    return _GlyphName("Taml:" + shorthand)


type Lookup = Callable[[], Statement]
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


@lookup("akhn")
def kssa():
    """
    >>> shape("க்ஷ")
    Taml:kssa
    """

    return LigatureSubstStatement(
        prefix=[],
        glyphs=[GlyphName("ka"), GlyphName("virama"), GlyphName("ssa")],
        suffix=[],
        replacement=GlyphName("kssa"),
        forceChain=False,
    )


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
        lookupBlock.statements.append(lookup())
        for feature in features:
            featureFile.statements.append(x := FeatureBlock(feature))
            x.statements.append(LookupReferenceStatement(lookupBlock))

    ufo.features = featureFile.asFea()
    print(ufo.features)

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
