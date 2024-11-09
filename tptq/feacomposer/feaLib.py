from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import overload

from fontTools.feaLib import ast

Class = ast.GlyphClass | ast.GlyphClassDefinition


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

    def inlineClass(
        self,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClass:
        return ast.GlyphClass(
            glyphs=[
                self.FormattedName(i) if isinstance(i, str) else ast.GlyphClassName(glyphclass=i)
                for i in items
            ]
        )

    # Statements:

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
    def sub(self, input: str | Class, output: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: Class, output: Class) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: str, output: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, input: Iterable[str | Class], output: str) -> ast.LigatureSubstStatement: ...

    def sub(
        self,
        input: str | Class | Iterable[str | Class],
        output: str | Class | Iterable[str],
    ) -> ast.SingleSubstStatement | ast.MultipleSubstStatement | ast.LigatureSubstStatement:
        _input = [*_normalizedSequenceShorthand(input, self.FormattedName)]
        _output = [*_normalizedSequenceShorthand(output, self.FormattedName)]
        assert _input and _output, (_input, _output)

        if len(_input) == 1:
            if len(_output) == 1:
                statement = ast.SingleSubstStatement(
                    glyphs=_input, replace=_output, prefix=[], suffix=[], forceChain=False
                )
            else:
                statement = ast.MultipleSubstStatement(
                    prefix=[], glyph=_input[0], suffix=[], replacement=_output
                )
        elif len(_output) == 1:
            statement = ast.LigatureSubstStatement(
                prefix=[], glyphs=_input, suffix=[], replacement=_output[0], forceChain=False
            )
        else:
            raise ValueError(_input, _output)

        self.current.statements.append(statement)
        return statement

    def subMap(
        self, mapping: Mapping[str, str] | Iterable[tuple[str, str]]
    ) -> ast.SingleSubstStatement:
        mapping = dict(mapping)
        return self.sub(
            input=self.inlineClass(mapping.keys()),
            output=self.inlineClass(mapping.values()),
        )


def _normalizedSequenceShorthand(
    sequence: str | Class | Iterable[str | Class],
    FormattedName: type[BaseFormattedName],
) -> Iterator[ast.GlyphName | ast.GlyphClass | ast.GlyphClassName]:
    if isinstance(sequence, str | Class):
        sequence = [sequence]
    for item in sequence:
        if isinstance(item, str):
            yield FormattedName(item)
        elif isinstance(item, ast.GlyphClassDefinition):
            yield ast.GlyphClassName(glyphclass=item)
        else:
            yield item
