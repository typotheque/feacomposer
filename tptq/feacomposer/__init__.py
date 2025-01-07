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


@dataclass
class ContextualInputItem:
    marked: _NormalizedAnyGlyph
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
            ast.LanguageSystemStatement(script=k, language=i)
            for k, v in sorted(self.languageSystems.items())
            for i in sorted(v)
        ] + self.root
        return featureFile

    # Expressions:

    def glyphClass(self, items: Iterable[AnyGlyph]) -> ast.GlyphClass:
        return ast.GlyphClass(glyphs=[self._normalizedAnyGlyph(i) for i in items])

    def input(self, item: AnyGlyph, *lookups: ast.LookupBlock) -> ContextualInputItem:
        return ContextualInputItem(self._normalizedAnyGlyph(item), [*lookups])

    # Comment or raw text:

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    def raw(self, text: str) -> ast.Comment:
        comment = ast.Comment(text=text)
        self.current.append(comment)
        return comment

    # Misc statements:

    def namedGlyphClass(self, name: str, items: Iterable[AnyGlyph]) -> ast.GlyphClassDefinition:
        definition = ast.GlyphClassDefinition(name, self.glyphClass(items))
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
        lookupBlock = ast.LookupBlock(name=name)

        if feature:
            featureBlock: ast.FeatureBlock | None = None
            if self.current:
                lastElement = self.current[-1]
                if isinstance(lastElement, ast.FeatureBlock) and lastElement.name == feature:
                    featureBlock = lastElement
            if not featureBlock:
                featureBlock = ast.FeatureBlock(name=feature)
                self.current.append(featureBlock)
            scriptLanguagePairs = list[tuple[ast.ScriptStatement, ast.LanguageStatement]]()
            if languageSystems is not None:
                assert languageSystems, languageSystems
                for script, languages in sorted(languageSystems.items()):
                    assert languages <= self.languageSystems[script], (script, languages)
                    scriptLanguagePairs.extend(
                        (
                            ast.ScriptStatement(script=script),
                            ast.LanguageStatement(language=i),
                        )
                        for i in sorted(languages)
                    )
            self.current = featureBlock.statements
            if scriptLanguagePairs:
                self.current.extend(scriptLanguagePairs.pop(0))
            self.current.append(lookupBlock)
            for pair in scriptLanguagePairs:
                self.current.extend(pair)
                self.current.append(ast.LookupReferenceStatement(lookup=lookupBlock))
        else:
            assert languageSystems is None, languageSystems
            self.current.append(lookupBlock)

        self.current = lookupBlock.statements
        if flags:
            if markAttachment := flags.get("MarkAttachmentType"):
                markAttachment = self._normalizedAnyGlyph(markAttachment)
            if markFilteringSet := flags.get("UseMarkFilteringSet"):
                markFilteringSet = self._normalizedAnyGlyph(markFilteringSet)
            statement = ast.LookupFlagStatement(
                value=sum(
                    {
                        "RightToLeft": 1,
                        "IgnoreBaseGlyphs": 2,
                        "IgnoreLigatures": 4,
                        "IgnoreMarks": 8,
                    }.get(i, 0)
                    for i in flags
                ),
                markAttachment=markAttachment,
                markFilteringSet=markFilteringSet,
            )
        else:
            statement = ast.LookupFlagStatement(value=0)
        self.current.append(statement)

        try:
            yield lookupBlock
        finally:
            self.current = backup

    # Substitution statements:

    @overload
    def sub(self, item: AnyGlyph, /, *, by: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, item: AnyGlyphClass, /, *, by: AnyGlyphClass) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, item: str, /, *, by: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, *items: AnyGlyph, by: str) -> ast.LigatureSubstStatement: ...

    def sub(
        self,
        *items: AnyGlyph,
        by: AnyGlyph | Iterable[str],
    ) -> ast.SingleSubstStatement | ast.MultipleSubstStatement | ast.LigatureSubstStatement:
        inputs = [self._normalizedAnyGlyph(i) for i in items]
        outputs = (
            self._normalizedAnyGlyph(by)
            if isinstance(by, AnyGlyph)
            else [self._normalizedAnyGlyph(i) for i in by]
        )

        if len(inputs) == 1:
            if isinstance(outputs, list):
                assert isinstance(inputs[0], ast.GlyphName)
                statement = ast.MultipleSubstStatement(
                    prefix=[], glyph=inputs[0], suffix=[], replacement=outputs
                )
            else:
                statement = ast.SingleSubstStatement(
                    glyphs=inputs, replace=[outputs], prefix=[], suffix=[], forceChain=False
                )
        else:
            assert isinstance(outputs, ast.GlyphName)
            statement = ast.LigatureSubstStatement(
                prefix=[], glyphs=inputs, suffix=[], replacement=outputs, forceChain=False
            )

        self.current.append(statement)
        return statement

    def contextualSub(
        self,
        *items: ContextualInputItem | AnyGlyph,
        by: AnyGlyph | None = None,
    ) -> ast.SingleSubstStatement | ast.LigatureSubstStatement | ast.ChainContextSubstStatement:
        prefixes = list[_NormalizedAnyGlyph]()
        inputs = list[_NormalizedAnyGlyph]()
        lookupLists = list[list[ast.LookupBlock]]()
        suffixes = list[_NormalizedAnyGlyph]()
        for item in items:
            if isinstance(item, ContextualInputItem):
                inputs.append(item.marked)
                lookupLists.append(item.lookups)
            else:
                (suffixes if inputs else prefixes).append(self._normalizedAnyGlyph(item))

        if by:
            assert not any(lookupLists), (items, by)
            output = self._normalizedAnyGlyph(by)
            if len(inputs) == 1:
                statement = ast.SingleSubstStatement(
                    glyphs=inputs,
                    replace=[output],
                    prefix=prefixes,
                    suffix=suffixes,
                    forceChain=True,
                )
            else:
                statement = ast.LigatureSubstStatement(
                    prefix=prefixes,
                    glyphs=inputs,
                    suffix=suffixes,
                    replacement=output,
                    forceChain=True,
                )
        else:
            statement = ast.ChainContextSubstStatement(
                prefix=prefixes,
                glyphs=inputs,
                suffix=suffixes,
                lookups=[i or None for i in lookupLists],
            )

        self.current.append(statement)
        return statement

    # Internal:

    @overload
    def _normalizedAnyGlyph(self, item: str) -> ast.GlyphName: ...

    @overload
    def _normalizedAnyGlyph(self, item: ast.GlyphClassDefinition) -> ast.GlyphClassName: ...

    @overload
    def _normalizedAnyGlyph(self, item: ast.GlyphClass) -> ast.GlyphClass: ...

    def _normalizedAnyGlyph(self, item: AnyGlyph) -> _NormalizedAnyGlyph:
        if isinstance(item, str):
            return ast.GlyphName(glyph=self.glyphNameProcessor(item))
        elif isinstance(item, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyphclass=item)
        else:
            return item
