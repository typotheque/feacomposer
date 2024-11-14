from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import TextIO

from fontTools.feaLib.ast import FeatureFile
from fontTools.feaLib.parser import Parser

from . import GlyphRenamer


def renameGlyphsInCode(code: str, renamer: GlyphRenamer) -> FeatureFile:
    with StringIO(code) as f:
        parser = GlyphRenamingParser(f, renamer)
    return parser.parse()


class GlyphRenamingParser(Parser):
    """
    All glyph names are renamed with the `renamer` function during parsing, before each (new, post-renaming) name is validated against the optional `newNames` iterable.
    """

    renamer: GlyphRenamer

    def __init__(
        self,
        file: TextIO,
        renamer: GlyphRenamer,
        *,
        newNames: Iterable[str] = (),
        followIncludes: bool = True,
        includeDir: Path | None = None,
    ) -> None:
        self.renamer = renamer
        super().__init__(
            featurefile=file,
            glyphNames=newNames,
            followIncludes=followIncludes,
            includeDir=includeDir,
        )

    def expect_glyph_(self) -> str:
        old = super().expect_glyph_()
        return self.renamer(old)
