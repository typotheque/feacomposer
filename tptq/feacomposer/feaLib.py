from collections.abc import Iterable
from dataclasses import dataclass
from typing import overload

from fontTools.feaLib import ast


def glyphClass(items: Iterable[str | ast.GlyphClassDefinition]) -> ast.GlyphClass:
    return ast.GlyphClass(glyphs=[ast.GlyphName(i) if isinstance(i, str) else i for i in items])


GlyphClass = ast.GlyphClass | ast.GlyphClassDefinition


@dataclass
class FeaComposer:
    root: ast.FeatureFile
    current: ast.Block

    def __init__(self, root: ast.FeatureFile | None = None) -> None:
        self.root = root or ast.FeatureFile()
        self.current = self.root

    # def languageSystems(self) -> list[LanguageSystemStatement]:
    #     return [i for i in self.root.statements if isinstance(i, LanguageSystemStatement)]

    def raw(self, text: str) -> ast.Comment:
        element = ast.Comment(text=text)
        self.current.statements.append(element)
        return element

    def comment(self, text: str) -> ast.Comment:
        return self.raw("# " + text)

    @overload
    def sub(self, input: str | GlyphClass, output: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: GlyphClass, output: GlyphClass) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: str, output: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, input: Iterable[str | GlyphClass], output: str) -> ast.LigatureSubstStatement: ...

    def sub(
        self,
        input: str | GlyphClass | Iterable[str | GlyphClass],
        output: str | GlyphClass | Iterable[str],
    ) -> ast.SingleSubstStatement | ast.MultipleSubstStatement | ast.LigatureSubstStatement:
        _input = _normalizeGlyphSequenceShorthand(input)
        _output = _normalizeGlyphSequenceShorthand(output)
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


def _normalizeGlyphSequenceShorthand(
    sequence: str | GlyphClass | Iterable[str | GlyphClass],
) -> list[ast.GlyphName | ast.GlyphClass | ast.GlyphClassName]:
    if isinstance(sequence, str | GlyphClass):
        sequence = [sequence]
    normalized = list[ast.GlyphName | ast.GlyphClass | ast.GlyphClassName]()
    for item in sequence:
        if isinstance(item, str):
            normalized.append(ast.GlyphName(item))
        elif isinstance(item, ast.GlyphClassDefinition):
            normalized.append(ast.GlyphClassName(glyphclass=item))
        else:
            normalized.append(item)
    return normalized
