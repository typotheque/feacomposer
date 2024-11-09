from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import overload

from fontTools.feaLib import ast


class Name(ast.GlyphName):
    glyph: str
    feaComposer: FeaComposer

    def __init__(self, name: str, feaComposer: FeaComposer):
        super().__init__(glyph=name)
        self.feaComposer = feaComposer

    def asFea(self, indent=""):
        if renamer := self.feaComposer.renamer:
            ast.asFea(renamer(self.glyph))
        else:
            return super().asFea(indent)


Class = ast.GlyphClass | ast.GlyphClassDefinition


@dataclass
class FeaComposer:
    root: ast.FeatureFile
    current: ast.Block

    renamer: Callable[[str], str] | None = None

    def __init__(self, root: ast.FeatureFile | None = None) -> None:
        self.root = root or ast.FeatureFile()
        self.current = self.root

    # Expressions:

    def inlineClass(
        self,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClass:
        return ast.GlyphClass(glyphs=[Name(i, self) if isinstance(i, str) else i for i in items])

    # Statements:

    def namedClass(
        self,
        name: str,
        items: Iterable[str | ast.GlyphClassDefinition],
    ) -> ast.GlyphClassDefinition:
        statement = ast.GlyphClassDefinition(name, self.inlineClass(items))
        self.current.statements.append(statement)
        return statement

    def raw(self, text: str) -> ast.Comment:
        element = ast.Comment(text=text)
        self.current.statements.append(element)
        return element

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

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
        _input = self._normalizeSequenceShorthand(input)
        _output = self._normalizeSequenceShorthand(output)
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

    def _languageSystems(self) -> list[ast.LanguageSystemStatement]:
        return [i for i in self.root.statements if isinstance(i, ast.LanguageSystemStatement)]

    def _normalizeSequenceShorthand(
        self,
        sequence: str | Class | Iterable[str | Class],
    ) -> list[Name | ast.GlyphClass | ast.GlyphClassName]:
        if isinstance(sequence, str | Class):
            sequence = [sequence]
        normalized = list[Name | ast.GlyphClass | ast.GlyphClassName]()
        for item in sequence:
            if isinstance(item, str):
                normalized.append(Name(item, self))
            elif isinstance(item, ast.GlyphClassDefinition):
                normalized.append(ast.GlyphClassName(glyphclass=item))
            else:
                normalized.append(item)
        return normalized
