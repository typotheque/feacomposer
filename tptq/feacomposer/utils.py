from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import IO

from fontTools.feaLib.parser import Parser

from . import StringProcessor


class GlyphNameProcessingParser(Parser):
    """
    All glyph names go through the `processor` function during parsing, before the returned new name is validated against the optional set of `newNames`.
    """

    processor: StringProcessor

    def __init__(
        self,
        code: str | IO[str],
        processor: StringProcessor,
        *,
        newNames: Iterable[str] = (),
        followIncludes: bool = True,
        includeDir: Path | None = None,
    ) -> None:
        self.processor = processor
        with StringIO(code) if isinstance(code, str) else code as f:
            super().__init__(
                featurefile=f,
                glyphNames=newNames,
                followIncludes=followIncludes,
                includeDir=includeDir,
            )

    def expect_glyph_(self) -> str:
        old = super().expect_glyph_()
        return self.processor(old)
