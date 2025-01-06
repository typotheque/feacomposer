from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, TypedDict, overload

from fontTools.feaLib import ast

LanguageSystemDict = dict[str | Literal["DFLT"], set[str | Literal["dflt"]]]
StringProcessor = Callable[[str], str]

AnyGlyphClass = ast.GlyphClass | ast.GlyphClassDefinition
AnyGlyph = str | AnyGlyphClass


class LookupFlagDict(TypedDict, total=False):
    RightToLeft: Literal[True]
    IgnoreBaseGlyphs: Literal[True]
    IgnoreLigatures: Literal[True]
    IgnoreMarks: Literal[True]
    MarkAttachmentType: AnyGlyphClass
    UseMarkFilteringSet: AnyGlyphClass


@dataclass
class ContextualInputItem:
    marked: AnyGlyph


_NormalizedAnyGlyph = ast.GlyphName | ast.GlyphClass | ast.GlyphClassName


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

    def input(self, item: AnyGlyph) -> ContextualInputItem:
        return ContextualInputItem(item)

    # Comment or raw text:

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    def raw(self, text: str) -> ast.Comment:
        comment = ast.Comment(text=text)
        self.current.append(comment)
        return comment

    # Misc statements:

    def namedGlyphClass(
        self,
        name: str,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClassDefinition:
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
                markAttachment=flags.get("MarkAttachmentType"),
                markFilteringSet=flags.get("UseMarkFilteringSet"),
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
    def sub(self, input: AnyGlyph, /, *, by: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: AnyGlyphClass, /, *, by: AnyGlyphClass) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: str, /, *, by: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, input: str, /, *, by: AnyGlyphClass) -> ast.AlternateSubstStatement: ...

    @overload
    def sub(self, *inputs: AnyGlyph, by: str) -> ast.LigatureSubstStatement: ...

    def sub(
        self,
        *inputs: AnyGlyph,
        by: AnyGlyph | Iterable[str],
    ) -> (
        ast.SingleSubstStatement
        | ast.MultipleSubstStatement
        | ast.AlternateSubstStatement
        | ast.LigatureSubstStatement
    ):
        input = [self._normalizedAnyGlyph(i) for i in inputs]
        output = (
            self._normalizedAnyGlyph(by)
            if isinstance(by, AnyGlyph)
            else [self._normalizedAnyGlyph(i) for i in by]
        )

        if len(input) == 1:
            if isinstance(output, list):
                statement = ast.MultipleSubstStatement(
                    prefix=[], glyph=input[0], suffix=[], replacement=output
                )
            elif isinstance(output, ast.GlyphName):
                statement = ast.SingleSubstStatement(
                    glyphs=input, replace=[output], prefix=[], suffix=[], forceChain=False
                )
            else:
                statement = ast.AlternateSubstStatement(
                    prefix=[], glyph=input, suffix=[], replacement=[output]
                )
        else:
            statement = ast.LigatureSubstStatement(
                prefix=[], glyphs=input, suffix=[], replacement=output, forceChain=False
            )

        self.current.append(statement)
        return statement

    def contextualSub(
        self,
        *items: AnyGlyph | ContextualInputItem | ast.LookupBlock,
        by: AnyGlyph | None = None,
    ) -> ast.SingleSubstStatement | ast.LigatureSubstStatement | ast.ChainContextSubstStatement:
        prefix = list[_NormalizedAnyGlyph]()
        input = list[_NormalizedAnyGlyph]()
        nestedLookups = list[list[ast.LookupBlock]]()
        suffix = list[_NormalizedAnyGlyph]()
        for item in items:  # TODO: Validate relative order between different types
            if isinstance(item, ast.LookupBlock):
                nestedLookups[-1].append(item)
            elif isinstance(item, ContextualInputItem):
                input.append(self._normalizedAnyGlyph(item.marked))
                nestedLookups.append([])
            else:
                (suffix if input else prefix).append(self._normalizedAnyGlyph(item))

        if by:
            assert not any(nestedLookups), nestedLookups
            output = self._normalizedAnyGlyph(by)
            if len(input) == 1:
                statement = ast.SingleSubstStatement(
                    glyphs=input,
                    replace=[output],
                    prefix=prefix,
                    suffix=suffix,
                    forceChain=True,
                )
            else:
                statement = ast.LigatureSubstStatement(
                    prefix=prefix,
                    glyphs=input,
                    suffix=suffix,
                    replacement=output,
                    forceChain=True,
                )
        else:
            statement = ast.ChainContextSubstStatement(
                prefix=prefix,
                glyphs=input,
                suffix=suffix,
                lookups=[i or None for i in nestedLookups],
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
