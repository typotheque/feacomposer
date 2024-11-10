from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, get_args, overload

from fontTools.feaLib import ast

LanguageSystemDict = dict[str | Literal["DFLT"], set[str | Literal["dflt"]]]
LookupFlag = Literal["RightToLeft", "IgnoreBaseGlyphs", "IgnoreLigatures", "IgnoreMarks"]

AnyClass = ast.GlyphClass | ast.GlyphClassDefinition
AnyGlyph = str | AnyClass


class BaseFormattedName(ast.GlyphName):
    glyph: str

    def asFea(self, indent="") -> str:
        return ast.asFea(self.formatted())

    def formatted(self) -> str:
        return self.glyph


@dataclass
class ContextualInputItem:
    marked: AnyGlyph


@dataclass
class FeaComposer:
    root: ast.FeatureFile
    current: ast.Block
    FormattedName: type[BaseFormattedName]

    def __init__(
        self,
        root: ast.FeatureFile | None = None,
        *,
        languageSystems: LanguageSystemDict | None = None,
        FormattedName: type[BaseFormattedName] = BaseFormattedName,
    ) -> None:
        self.root = root or ast.FeatureFile()
        self.current = self.root

        languageSystems = {"DFLT": {"dflt"}} if languageSystems is None else languageSystems
        self.current.statements.extend(
            ast.LanguageSystemStatement(script=k, language=i)
            for k, v in sorted(languageSystems.items())
            for i in sorted(v)
        )

        self.FormattedName = FormattedName

    # Expressions:

    def inlineClass(self, items: Iterable[AnyGlyph]) -> ast.GlyphClass:
        return ast.GlyphClass(glyphs=[self._normalizedAnyGlyph(i) for i in items])

    def input(self, item: AnyGlyph) -> ContextualInputItem:
        return ContextualInputItem(item)

    # Comment or raw text:

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    def raw(self, text: str) -> ast.Comment:
        comment = ast.Comment(text=text)
        self.current.statements.append(comment)
        return comment

    # Misc statements:

    def namedClass(
        self,
        name: str,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClassDefinition:
        definition = ast.GlyphClassDefinition(name, self.inlineClass(items))
        self.current.statements.append(definition)
        return definition

    # Block statements:

    @contextmanager
    def Lookup(
        self,
        name: str = "",
        *,
        languageSystems: LanguageSystemDict | None = None,
        feature: str = "",
        flags: Iterable[LookupFlag] = (),
        markAttachment: AnyClass | None = None,
        markFilteringSet: AnyClass | None = None,
    ) -> Iterator[ast.LookupBlock]:
        scriptLanguagePairs = list[tuple[ast.ScriptStatement, ast.LanguageStatement]]()
        if feature:
            assert len(feature) == 4, feature
            lastStatement = self.current.statements[-1]
            if isinstance(lastStatement, ast.FeatureBlock) and lastStatement.name == feature:
                parent = lastStatement
            else:
                parent = ast.FeatureBlock(name=feature)
                self.current.statements.append(parent)
            if languageSystems is not None:
                assert languageSystems, languageSystems
                globalLanguageSystems = LanguageSystemDict()
                for element in self.root.statements:
                    if isinstance(element, ast.LanguageSystemStatement):
                        globalLanguageSystems.setdefault(element.script, set()).add(
                            element.language
                        )
                for script, languages in sorted(languageSystems.items()):
                    assert languages <= globalLanguageSystems[script], (
                        languageSystems,
                        globalLanguageSystems,
                    )
                    for language in languages:
                        scriptLanguagePairs.append(
                            (
                                ast.ScriptStatement(script=script),
                                ast.LanguageStatement(language=language),
                            )
                        )
        else:
            assert languageSystems is None, languageSystems
            parent = self.current

        if not name:
            prefix = "_"
            maxNumber = 0
            for element in _iterDescendants(self.root):
                if isinstance(element, ast.LookupBlock) and element.name.startswith(prefix):
                    try:
                        number = int(element.name.removeprefix(prefix))
                    except ValueError:
                        continue
                    maxNumber = max(maxNumber, number)
            name = prefix + str(maxNumber + 1)
        lookupBlock = ast.LookupBlock(name=name)

        if scriptLanguagePairs:
            parent.statements.extend(scriptLanguagePairs.pop(0))
        parent.statements.append(lookupBlock)
        for pair in scriptLanguagePairs:
            parent.statements.extend(pair)
            parent.statements.append(ast.LookupReferenceStatement(lookup=lookupBlock))

        if flags or markAttachment or markFilteringSet:
            statement = ast.LookupFlagStatement(
                value=sum(2 ** _lookupFlags.index(i) for i in flags),
                markAttachment=markAttachment,
                markFilteringSet=markFilteringSet,
            )
        else:
            statement = ast.LookupFlagStatement(value=0)
        lookupBlock.statements.append(statement)

        backup = self.current
        self.current = lookupBlock
        try:
            yield lookupBlock
        finally:
            self.current = backup

    # Substitution statements:

    @overload
    def sub(self, input: AnyGlyph, output: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: AnyClass, output: AnyClass) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: str, output: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, input: str, output: AnyClass) -> ast.AlternateSubstStatement: ...

    @overload
    def sub(self, input: Iterable[AnyGlyph], output: str) -> ast.LigatureSubstStatement: ...

    def sub(
        self,
        input: AnyGlyph | Iterable[AnyGlyph],
        output: AnyGlyph | Iterable[str],
    ) -> (
        ast.SingleSubstStatement
        | ast.MultipleSubstStatement
        | ast.AlternateSubstStatement
        | ast.LigatureSubstStatement
    ):
        # Type checking instead of list length checking, so the overload signatures are accurate.

        _input = (
            self._normalizedAnyGlyph(input)
            if isinstance(input, AnyGlyph)
            else [self._normalizedAnyGlyph(i) for i in input]
        )
        _output = (
            self._normalizedAnyGlyph(output)
            if isinstance(output, AnyGlyph)
            else [self._normalizedAnyGlyph(i) for i in output]
        )

        if isinstance(_input, list):
            assert not isinstance(_output, list), (_input, _output)
            statement = ast.LigatureSubstStatement(
                prefix=[], glyphs=_input, suffix=[], replacement=_output, forceChain=False
            )
        elif isinstance(_output, list):
            statement = ast.MultipleSubstStatement(
                prefix=[], glyph=_input, suffix=[], replacement=_output
            )
        elif isinstance(_output, ast.GlyphName):
            statement = ast.SingleSubstStatement(
                glyphs=[_input], replace=[_output], prefix=[], suffix=[], forceChain=False
            )
        else:
            statement = ast.AlternateSubstStatement(
                prefix=[], glyph=[_input], suffix=[], replacement=[_output]
            )

        self.current.statements.append(statement)
        return statement

    def contextualSub(
        self,
        context: Iterable[AnyGlyph | ContextualInputItem | ast.LookupBlock],
        output: AnyGlyph | None = None,
    ) -> ast.SingleSubstStatement | ast.LigatureSubstStatement | ast.ChainContextSubstStatement:
        prefix = list[_NormalizedAnyGlyph]()
        input = list[_NormalizedAnyGlyph]()
        nestedLookups = list[list[ast.LookupBlock]]()
        suffix = list[_NormalizedAnyGlyph]()
        for item in context:  # TODO: Validate relative order between different types
            if isinstance(item, ast.LookupBlock):
                nestedLookups[-1].append(item)
            elif isinstance(item, ContextualInputItem):
                input.append(self._normalizedAnyGlyph(item.marked))
                nestedLookups.append([])
            else:
                (suffix if input else prefix).append(self._normalizedAnyGlyph(item))

        if output:
            assert not any(len(i) for i in nestedLookups), (nestedLookups, output)
            _output = self._normalizedAnyGlyph(output)
            if len(input) == 1:
                statement = ast.SingleSubstStatement(
                    glyphs=input,
                    replace=[_output],
                    prefix=prefix,
                    suffix=suffix,
                    forceChain=True,
                )
            else:
                statement = ast.LigatureSubstStatement(
                    prefix=prefix,
                    glyphs=input,
                    suffix=suffix,
                    replacement=_output,
                    forceChain=True,
                )
        else:
            statement = ast.ChainContextSubstStatement(
                prefix=prefix,
                glyphs=input,
                suffix=suffix,
                lookups=[i or None for i in nestedLookups],
            )

        self.current.statements.append(statement)
        return statement

    # Internal:

    def _normalizedAnyGlyph(self, item: AnyGlyph) -> _NormalizedAnyGlyph:
        if isinstance(item, str):
            return self.FormattedName(item)
        elif isinstance(item, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyphclass=item)
        else:
            return item


_lookupFlags: tuple[LookupFlag, ...] = get_args(LookupFlag)
_NormalizedAnyGlyph = ast.GlyphName | ast.GlyphClass | ast.GlyphClassName


def _iterDescendants(block: ast.Block) -> Iterator[ast.Element]:
    element: ast.Element
    for element in block.statements:
        yield element
        if isinstance(element, ast.Block):
            yield from _iterDescendants(element)
