from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, TypedDict, overload

from fontTools.feaLib import ast

LanguageSystemDict = dict[str | Literal["DFLT"], set[str | Literal["dflt"]]]
StringProcessor = Callable[[str], str]

AnyGlyphClass = ast.GlyphClass | ast.GlyphClassDefinition
AnyGlyph = str | AnyGlyphClass
_NormalizedAnyGlyphClass = ast.GlyphClass | ast.GlyphClassName
_NormalizedAnyGlyph = ast.GlyphName | _NormalizedAnyGlyphClass


class LookupFlagDict(TypedDict, total=False):
    RightToLeft: Literal[True]
    IgnoreBaseGlyphs: Literal[True]
    IgnoreLigatures: Literal[True]
    IgnoreMarks: Literal[True]
    MarkAttachmentType: AnyGlyphClass
    UseMarkFilteringSet: AnyGlyphClass


lookupFlagNameToMask = {
    "RightToLeft": 0x0001,
    "IgnoreBaseGlyphs": 0x0002,
    "IgnoreLigatures": 0x0004,
    "IgnoreMarks": 0x0008,
}


@dataclass
class ContextualInput:
    glyph: _NormalizedAnyGlyph
    lookups: list[ast.LookupBlock]


@dataclass
class FeaComposer:
    languageSystems: LanguageSystemDict
    glyphNameProcessor: StringProcessor
    """Every incoming glyph name is processed with this function. Often useful for renaming glyphs. For example, supply `lambda name: "Deva:" + name` to prefix all glyph names with the Devanagari namespace."""

    root: list[ast.Element]
    current: list[ast.Element]
    nextLookupNumber: int

    def __init__(
        self,
        languageSystems: LanguageSystemDict | None = None,
        glyphNameProcessor: StringProcessor = lambda name: name,
    ) -> None:
        self.languageSystems = {"DFLT": {"dflt"}} if languageSystems is None else languageSystems
        self.glyphNameProcessor = glyphNameProcessor

        self.root = list[ast.Element]()
        self.current = self.root
        self.nextLookupNumber = 1

    def asFeatureFile(self) -> ast.FeatureFile:
        featureFile = ast.FeatureFile()
        featureFile.statements = [
            ast.LanguageSystemStatement(k, i)
            for k, v in sorted(self.languageSystems.items())
            for i in sorted(v)
        ] + self.root
        return featureFile

    # Expressions:

    def glyphClass(self, glyphs: Iterable[AnyGlyph]) -> ast.GlyphClass:
        return ast.GlyphClass([self._normalized(i) for i in glyphs])

    def input(self, glyph: AnyGlyph, *lookups: ast.LookupBlock) -> ContextualInput:
        return ContextualInput(self._normalized(glyph), [*lookups])

    # Comment or raw text:

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    def raw(self, text: str) -> ast.Comment:
        comment = ast.Comment(text)
        self.current.append(comment)
        return comment

    # Misc statements:

    def namedGlyphClass(self, name: str, glyphs: Iterable[AnyGlyph]) -> ast.GlyphClassDefinition:
        definition = ast.GlyphClassDefinition(name, self.glyphClass(glyphs))
        self.current.append(definition)
        return definition

    # Block statements:

    @contextmanager
    def Lookup(
        self,
        name: str = "",
        *,
        languageSystems: LanguageSystemDict | None = None,
        feature: str = "",
        flags: LookupFlagDict | None = None,
    ) -> Iterator[ast.LookupBlock]:
        backup = self.current

        if not name:
            name = f"_{self.nextLookupNumber}"
            self.nextLookupNumber += 1
        lookupBlock = ast.LookupBlock(name)

        if feature:
            assert len(feature) == 4, feature
            featureBlock: ast.FeatureBlock | None = None
            if self.current:
                lastElement = self.current[-1]
                if isinstance(lastElement, ast.FeatureBlock) and lastElement.name == feature:
                    featureBlock = lastElement
            if not featureBlock:
                featureBlock = ast.FeatureBlock(feature)
                self.current.append(featureBlock)
            scriptLanguagePairs = list[tuple[ast.ScriptStatement, ast.LanguageStatement]]()
            if languageSystems is not None:
                assert languageSystems, languageSystems
                for script, languages in sorted(languageSystems.items()):
                    assert languages <= self.languageSystems[script], (script, languages)
                    scriptLanguagePairs.extend(
                        (ast.ScriptStatement(script), ast.LanguageStatement(i))
                        for i in sorted(languages)
                    )
            self.current = featureBlock.statements
            if scriptLanguagePairs:
                self.current.extend(scriptLanguagePairs.pop(0))
            self.current.append(lookupBlock)
            for pair in scriptLanguagePairs:
                self.current.extend(pair)
                self.current.append(ast.LookupReferenceStatement(lookupBlock))
        else:
            assert languageSystems is None, languageSystems
            self.current.append(lookupBlock)

        self.current = lookupBlock.statements
        flags = flags or {}
        self.current.append(
            ast.LookupFlagStatement(
                sum(lookupFlagNameToMask.get(i, 0) for i in flags),
                markAttachment=self._normalized(flags.get("MarkAttachmentType")),
                markFilteringSet=self._normalized(flags.get("UseMarkFilteringSet")),
            )
        )
        try:
            yield lookupBlock
        finally:
            self.current = backup

    # Substitution statements:

    def sub(
        self,
        *glyphs: AnyGlyph | ContextualInput,
        by: AnyGlyph | Iterable[str] | None = None,
    ) -> (
        ast.SingleSubstStatement
        | ast.MultipleSubstStatement
        | ast.LigatureSubstStatement
        | ast.ChainContextSubstStatement
    ):
        prefix = list[_NormalizedAnyGlyph]()
        input = list[_NormalizedAnyGlyph]()
        lookupLists = list[list[ast.LookupBlock]]()
        suffix = list[_NormalizedAnyGlyph]()
        for item in glyphs:
            if isinstance(item, ContextualInput):
                assert not suffix, glyphs
                input.append(item.glyph)
                lookupLists.append(item.lookups)
            elif input:
                suffix.append(self._normalized(item))
            else:
                prefix.append(self._normalized(item))

        if input:
            forceChain = True
        else:
            input = prefix
            prefix = []
            forceChain = False

        output = (
            self._normalized(by)
            if isinstance(by, AnyGlyph | None)
            else [self._normalized(i) for i in by]
        )
        if output is None:
            statement = ast.ChainContextSubstStatement(
                prefix=prefix,
                glyphs=input,
                suffix=suffix,
                lookups=[i or None for i in lookupLists],
            )
        else:
            assert not any(lookupLists), glyphs
            if len(input) == 1:
                if isinstance(output, list):
                    assert isinstance(input[0], ast.GlyphName)
                    statement = ast.MultipleSubstStatement(
                        prefix=prefix,
                        glyph=input[0],
                        suffix=suffix,
                        replacement=output,
                        forceChain=forceChain,
                    )
                else:
                    statement = ast.SingleSubstStatement(
                        glyphs=input,
                        replace=[output],
                        prefix=prefix,
                        suffix=suffix,
                        forceChain=forceChain,
                    )
            else:
                assert isinstance(output, ast.GlyphName)
                statement = ast.LigatureSubstStatement(
                    prefix=prefix,
                    glyphs=input,
                    suffix=suffix,
                    replacement=output,
                    forceChain=forceChain,
                )

        self.current.append(statement)
        return statement

    # Internal:

    @overload
    def _normalized(self, glyph: str) -> ast.GlyphName: ...

    @overload
    def _normalized(self, glyph: ast.GlyphClassDefinition) -> ast.GlyphClassName: ...

    @overload
    def _normalized(self, glyph: ast.GlyphClass) -> ast.GlyphClass: ...

    @overload
    def _normalized(self, glyph: None) -> None: ...

    def _normalized(self, glyph: AnyGlyph | None) -> _NormalizedAnyGlyph | None:
        if isinstance(glyph, str):
            assert not glyph.startswith("@") and " " not in glyph, glyph
            return ast.GlyphName(self.glyphNameProcessor(glyph))
        elif isinstance(glyph, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyph)
        else:
            return glyph
