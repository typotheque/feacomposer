from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import overload

from fontTools.feaLib import ast

AnyClass = ast.GlyphClass | ast.GlyphClassDefinition
AnyGlyph = str | AnyClass


@dataclass
class MarkedInputItem:
    marked: AnyGlyph


NormalizedAnyGlyph = ast.GlyphName | ast.GlyphClass | ast.GlyphClassName


class BaseFormattedName(ast.GlyphName):
    glyph: str

    def asFea(self, indent=""):
        ast.asFea(self.formatted())

    def formatted(self) -> str:
        return self.glyph


@dataclass
class FeaComposer:
    root: ast.FeatureFile
    current: ast.Block

    FormattedName: type[BaseFormattedName]

    def __init__(
        self,
        root: ast.FeatureFile | None = None,
        FormattedName=BaseFormattedName,
    ) -> None:
        self.root = root or ast.FeatureFile()
        self.current = self.root

        self.FormattedName = FormattedName

    # Expressions:

    def inlineClass(self, items: Iterable[AnyGlyph]) -> ast.GlyphClass:
        return ast.GlyphClass(glyphs=[self._normalizedAnyGlyph(i) for i in items])

    def input(self, item: AnyGlyph) -> MarkedInputItem:
        return MarkedInputItem(item)

    def _normalizedAnyGlyph(self, item: AnyGlyph) -> NormalizedAnyGlyph:
        if isinstance(item, str):
            return self.FormattedName(item)
        elif isinstance(item, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyphclass=item)
        else:
            return item

    # Statement-like elements:

    def raw(self, text: str) -> ast.Comment:
        element = ast.Comment(text=text)
        self.current.statements.append(element)
        return element

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    def namedClass(
        self,
        name: str,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClassDefinition:
        statement = ast.GlyphClassDefinition(name, self.inlineClass(items))
        self.current.statements.append(statement)
        return statement

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
        context: Iterable[AnyGlyph | MarkedInputItem | ast.LookupBlock],
        output: AnyGlyph | None = None,
    ):
        prefix = list[NormalizedAnyGlyph]()
        input = list[NormalizedAnyGlyph]()
        nestedLookups = list[list[ast.LookupBlock]]()
        suffix = list[NormalizedAnyGlyph]()
        for item in context:
            if isinstance(item, ast.LookupBlock):
                nestedLookups[-1].append(item)
            elif isinstance(item, MarkedInputItem):
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
