from collections.abc import Callable, Iterable
from os import PathLike
from typing import TextIO

from fontTools.feaLib.parser import Parser


class GlyphRenamingParser(Parser):
    """
    All glyph names are renamed with the `renamer` function during parsing, before each (new, post-renaming) name is validated against the optional `newGlyphNames` iterable.
    """

    def __init__(
        self,
        featurefile: TextIO | PathLike[str] | str,
        renamer: Callable[[str], str],
        *,
        newGlyphNames: Iterable[str] = (),
        followIncludes=True,
        includeDir: PathLike[str] | str | None = None
    ):
        self.renamer = renamer
        super().__init__(
            featurefile,
            glyphNames=newGlyphNames,
            followIncludes=followIncludes,
            includeDir=includeDir,
        )

    def expect_glyph_(self):
        return self.renamer(super().expect_glyph_())
