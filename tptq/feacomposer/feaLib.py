from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal, Protocol, get_args, overload

from fontTools.feaLib import ast

LanguageSystemDict = dict[str | Literal["DFLT"], set[str | Literal["dflt"]]]
LookupFlag = Literal["RightToLeft", "IgnoreBaseGlyphs", "IgnoreLigatures", "IgnoreMarks"]

AnyGlyphClass = ast.GlyphClass | ast.GlyphClassDefinition
AnyGlyph = str | AnyGlyphClass


class GlyphRenamer(Protocol):
    def __call__(self, name: str) -> str: ...


@dataclass
class ContextualInputItem:
    marked: AnyGlyph


@dataclass
class FeaComposer:
    languageSystems: LanguageSystemDict
    glyphRenamer: GlyphRenamer

    root: list[ast.Element]
    current: list[ast.Element]
    nextLookupNumber: int

    def __init__(
        self,
        languageSystems: LanguageSystemDict | None = None,
        glyphRenamer: GlyphRenamer = lambda name: name,
    ) -> None:
        self.languageSystems = {"DFLT": {"dflt"}} if languageSystems is None else languageSystems
        self.glyphRenamer = glyphRenamer

        self.root = list[ast.Element]()
        self.current = self.root
        self.nextLookupNumber = 1

    def code(self) -> str:
        featureFile = ast.FeatureFile()
        featureFile.statements = [
            ast.LanguageSystemStatement(script=k, language=i)
            for k, v in sorted(self.languageSystems.items())
            for i in sorted(v)
        ] + self.root
        return featureFile.asFea()

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
        flags: Iterable[LookupFlag] = (),
        markAttachment: AnyGlyphClass | None = None,
        markFilteringSet: AnyGlyphClass | None = None,
    ) -> Iterator[ast.LookupBlock]:
        backup = self.current

        if not name:
            name = f"_{self.nextLookupNumber}"
            self.nextLookupNumber += 1
        lookupBlock = ast.LookupBlock(name=name)

        if feature:
            lastElement = self.current[-1]
            if isinstance(lastElement, ast.FeatureBlock) and lastElement.name == feature:
                featureBlock = lastElement
            else:
                featureBlock = ast.FeatureBlock(name=feature)
                self.current.append(featureBlock)
            scriptLanguagePairs = list[tuple[ast.ScriptStatement, ast.LanguageStatement]]()
            if languageSystems is not None:
                assert languageSystems, languageSystems
                for script, languages in sorted(languageSystems.items()):
                    assert languages <= self.languageSystems[script], (
                        languageSystems,
                        self.languageSystems,
                    )
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
        if flags or markAttachment or markFilteringSet:
            statement = ast.LookupFlagStatement(
                value=sum(2 ** _lookupFlags.index(i) for i in flags),
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
    def sub(self, input: AnyGlyph, output: str) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: AnyGlyphClass, output: AnyGlyphClass) -> ast.SingleSubstStatement: ...

    @overload
    def sub(self, input: str, output: Iterable[str]) -> ast.MultipleSubstStatement: ...

    @overload
    def sub(self, input: str, output: AnyGlyphClass) -> ast.AlternateSubstStatement: ...

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

        self.current.append(statement)
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

        self.current.append(statement)
        return statement

    # Internal:

    def _normalizedAnyGlyph(self, item: AnyGlyph) -> _NormalizedAnyGlyph:
        if isinstance(item, str):
            return ast.GlyphName(glyph=self.glyphRenamer(item))
        elif isinstance(item, ast.GlyphClassDefinition):
            return ast.GlyphClassName(glyphclass=item)
        else:
            return item


_lookupFlags: tuple[LookupFlag, ...] = get_args(LookupFlag)
_NormalizedAnyGlyph = ast.GlyphName | ast.GlyphClass | ast.GlyphClassName


def _test() -> None:
    c = FeaComposer(
        languageSystems={
            "DFLT": {"dflt"},
            "deva": {"dflt", "MAR "},
            "dev2": {"dflt", "MAR "},
        },
        glyphRenamer=lambda name: "Deva:" + name,
    )

    someClass = c.namedGlyphClass("foo", ["a"])

    with c.Lookup(feature="rphf"):
        c.sub(["ra", "virama"], "repha")
        c.sub(["a", c.glyphClass(["a"]), someClass], "b")

    with c.Lookup("foo") as lookupFoo:
        pass

    with c.Lookup("bar") as lookupBar:
        pass

    with c.Lookup(
        languageSystems={"dev2": {"dflt", "MAR "}},
        feature="xxxx",
        markAttachment=c.glyphClass(["virama"]),
    ):
        c.contextualSub(["a", c.input("b"), "c"], "d")
        c.contextualSub(["x", c.input("y"), lookupFoo, c.input("z"), lookupBar])

    print(c.code())


if __name__ == "__main__":
    _test()
