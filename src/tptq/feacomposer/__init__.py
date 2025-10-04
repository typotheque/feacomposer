from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypedDict, overload

from fontTools.feaLib import ast
from fontTools.feaLib.lexer import Lexer

LanguageSystemDict = dict[str, set[str]]
DEFAULT_SCRIPT_TAG = "DFLT"
DEFAULT_LANGUAGE_TAG = "dflt"

StringProcessor = Callable[[str], str]

AnyGlyphClass = ast.GlyphClass | ast.GlyphClassDefinition
NormalizedAnyGlyphClass = ast.GlyphClass | ast.GlyphClassName

AnyGlyph = str | AnyGlyphClass
NormalizedAnyGlyph = ast.GlyphName | NormalizedAnyGlyphClass


@dataclass
class ContextualInput:
    glyph: NormalizedAnyGlyph
    lookups: list[ast.LookupBlock]


class LookupFlagDict(TypedDict, total=False):
    RightToLeft: bool
    IgnoreBaseGlyphs: bool
    IgnoreLigatures: bool
    IgnoreMarks: bool
    MarkAttachmentType: AnyGlyphClass | None
    UseMarkFilteringSet: AnyGlyphClass | None


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
        *,
        languageSystems: LanguageSystemDict,
        glyphNameProcessor: StringProcessor = lambda name: name,
    ) -> None:
        self.languageSystems = languageSystems
        self.glyphNameProcessor = glyphNameProcessor

        self.root = list[ast.Element]()
        self.current = self.root
        self.nextLookupNumber = 1

    def languageSystemStatements(self) -> list[ast.LanguageSystemStatement]:
        return [
            ast.LanguageSystemStatement(k, v)
            for k, v in self._normalizedLanguageSystems(self.languageSystems)
        ]

    def asFeatureFile(self) -> ast.FeatureFile:
        featureFile = ast.FeatureFile()
        featureFile.statements = self.languageSystemStatements() + self.root
        return featureFile

    # Expressions:

    def glyphClass(
        self,
        glyphs: Iterable[AnyGlyph],
    ) -> ast.GlyphClass:
        return ast.GlyphClass([self._normalized(i) for i in glyphs])

    def input(
        self,
        glyph: AnyGlyph,
        *lookups: ast.LookupBlock,
    ) -> ContextualInput:
        return ContextualInput(self._normalized(glyph), [*lookups])

    # Misc statements:

    def raw(
        self,
        text: str,
    ) -> ast.Comment:
        comment = ast.Comment(text)
        self.current.append(comment)
        return comment

    def comment(
        self,
        text: str,
    ) -> ast.Comment:
        return self.raw("# " + text)

    def namedGlyphClass(
        self,
        name: str,
        glyphs: Iterable[AnyGlyph],
    ) -> ast.GlyphClassDefinition:
        assert Lexer.RE_GLYPHCLASS.match(name), name
        definition = ast.GlyphClassDefinition(name, self.glyphClass(glyphs))
        self.current.append(definition)
        return definition

    # Lookup block or reference:

    @contextmanager
    def Lookup(
        self,
        name: str = "",
        *,
        languageSystems: LanguageSystemDict | None = None,
        feature: str = "",
        flags: LookupFlagDict | None = None,
    ) -> Iterator[ast.LookupBlock]:
        if not name:
            name = f"_{self.nextLookupNumber}"
            self.nextLookupNumber += 1
        lookupBlock = ast.LookupBlock(name)
        flags = flags or {}
        lookupBlock.statements.append(
            ast.LookupFlagStatement(
                sum(_LOOKUP_FLAG_NAME_TO_MASK.get(k, 0) for k, v in flags.items() if v),
                markAttachment=self._normalized(flags.get("MarkAttachmentType")),
                markFilteringSet=self._normalized(flags.get("UseMarkFilteringSet")),
            )
        )
        self._addLookup(lookupBlock, feature, languageSystems)

        backup = self.current
        self.current = lookupBlock.statements
        try:
            yield lookupBlock
        finally:
            self.current = backup

    def lookupReference(
        self,
        lookup: ast.LookupBlock,
        feature: str,
        *,
        languageSystems: LanguageSystemDict | None = None,
    ) -> ast.LookupReferenceStatement:
        reference = ast.LookupReferenceStatement(lookup)
        self._addLookup(reference, feature, languageSystems)
        return reference

    # Substitution statements:

    def sub(
        self,
        *glyphs: AnyGlyph | ContextualInput,
        by: AnyGlyph | Iterable[str] | None,
    ) -> (
        ast.SingleSubstStatement
        | ast.MultipleSubstStatement
        | ast.LigatureSubstStatement
        | ast.ChainContextSubstStatement
        | ast.IgnoreSubstStatement
    ):
        prefix = list[NormalizedAnyGlyph]()
        input = list[NormalizedAnyGlyph]()
        lookupLists = list[list[ast.LookupBlock]]()
        suffix = list[NormalizedAnyGlyph]()
        for item in glyphs:
            if isinstance(item, ContextualInput):
                assert not suffix, glyphs
                input.append(item.glyph)
                lookupLists.append(item.lookups)
            elif input:
                suffix.append(self._normalized(item))
            else:
                prefix.append(self._normalized(item))

        if by is None:
            assert input, glyphs
            if any(lookupLists):
                statement = ast.ChainContextSubstStatement(
                    prefix=prefix,
                    glyphs=input,
                    suffix=suffix,
                    lookups=[i or None for i in lookupLists],
                )
            else:
                statement = ast.IgnoreSubstStatement([(prefix, input, suffix)])
        else:
            assert not any(lookupLists), (glyphs, by)
            if input:
                forceChain = True
            else:
                input = prefix
                prefix = []
                forceChain = False
            output = (
                self._normalized(by)
                if isinstance(by, AnyGlyph)
                else [self._normalized(i) for i in by]
            )
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

    def _normalized(self, glyph: AnyGlyph | None) -> NormalizedAnyGlyph | None:
        if isinstance(glyph, str):
            assert not glyph.startswith("@") and " " not in glyph, glyph
            return ast.GlyphName(self.glyphNameProcessor(glyph))
        elif isinstance(glyph, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyph)
        else:
            return glyph

    def _normalizedLanguageSystems(
        self,
        languageSystems: LanguageSystemDict,
    ) -> list[tuple[str, str]]:
        normalized = list[tuple[str, str]]()
        for script, languages in sorted(
            languageSystems.items(),
            key=lambda x: "" if x == DEFAULT_SCRIPT_TAG else x,
        ):
            assert languages, (script, languages)
            for language in sorted(
                languages,
                key=lambda x: "" if x == DEFAULT_LANGUAGE_TAG else x,
            ):
                assert language in self.languageSystems[script], (script, language)
                normalized.append((script, language))
        return normalized

    def _addLookup(
        self,
        lookup: ast.LookupBlock | ast.LookupReferenceStatement,
        feature: str,
        languageSystems: LanguageSystemDict | None,
    ) -> None:
        if feature:
            assert len(feature) == 4, feature
            for languageSystem in self._normalizedLanguageSystems(
                languageSystems or self.languageSystems
            ) or [None]:
                featureBlock = ast.FeatureBlock(feature)
                if languageSystem:
                    script, language = languageSystem
                    featureBlock.statements.append(ast.ScriptStatement(script))
                    featureBlock.statements.append(ast.LanguageStatement(language))
                featureBlock.statements.append(lookup)
                self.current.append(featureBlock)
                if isinstance(lookup, ast.LookupBlock):
                    lookup = ast.LookupReferenceStatement(lookup)
        else:
            assert isinstance(lookup, ast.LookupBlock), lookup
            assert not languageSystems, languageSystems
            self.current.append(lookup)


_LOOKUP_FLAG_NAME_TO_MASK = {
    "RightToLeft": 0x0001,
    "IgnoreBaseGlyphs": 0x0002,
    "IgnoreLigatures": 0x0004,
    "IgnoreMarks": 0x0008,
}
