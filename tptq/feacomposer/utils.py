from collections.abc import Callable, Iterable
from os import PathLike
from typing import TextIO

from fontTools.feaLib.parser import Parser


class GlyphRenamingParser(Parser):
    """
    All glyph names are renamed with the `renamer` function during parsing, before each (new, post-renaming) name is validated against the optional `newNames` iterable.
    """

    def __init__(
        self,
        featurefile: TextIO | PathLike[str] | str,
        renamer: Callable[[str], str],
        *,
        newNames: Iterable[str] = (),
        followIncludes=True,
        includeDir: PathLike[str] | str | None = None,
    ):
        self.renamer = renamer
        self.oldNameToNew = dict[str, str]()
        super().__init__(
            featurefile,
            glyphNames=newNames,
            followIncludes=followIncludes,
            includeDir=includeDir,
        )

    def expect_glyph_(self) -> str:
        old = super().expect_glyph_()
        new = self.oldNameToNew.get(old)
        if not new:
            self.oldNameToNew[old] = new = self.renamer(old)
        return new
