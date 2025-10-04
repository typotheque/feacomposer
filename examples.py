from pathlib import Path

from fontTools.feaLib.ast import BaseAxis, TableBlock

from tptq.feacomposer import FeaComposer

reference = (Path.cwd() / "examples.fea").read_text()


def test() -> None:
    c = FeaComposer(
        languageSystems={"dev2": {"dflt", "NEP "}},
        glyphNameProcessor=insertNamespace,
    )

    c.comment("Hello and, again, welcome to the Aperture Science computer-aided enrichment center.")

    with c.Lookup(
        languageSystems={"dev2": {"NEP "}},
        feature="locl",
    ):
        mapping = {i: i + ".north" for i in ["one", "five", "eight"]}
        c.sub(
            c.glyphClass(mapping.keys()),
            by=c.glyphClass(mapping.values()),
        )

    with c.Lookup(feature="rphf"):
        c.sub("ra", "virama", by="repha")

    with c.Lookup(
        feature="rkrf",
        flags={
            "UseMarkFilteringSet": c.glyphClass(["virama"]),
        },
    ):
        c.sub("ka", "virama", "ra", by="kRa")

    with c.Lookup(feature="half"):
        for onset in ["k", "th", "dh", "r", "kR"]:
            c.sub(onset + "a", "virama", by=onset)

    classThaLike = c.namedGlyphClass(
        "thaLike",
        ["tha", "dha"],
    )

    with c.Lookup() as lookupCompact:
        for original in ["kRa", "usign"]:
            c.sub(original, by=original + ".compact")

    with c.Lookup(feature="pres"):
        c.sub(classThaLike, c.input("repha"), by="repha.tha")

        c.sub("k", c.input("kRa"), by=None)
        c.sub(
            c.input("kRa", lookupCompact),
            c.input("usign", lookupCompact),
            by=None,
        )

    table = TableBlock("BASE")
    table.statements.append(
        BaseAxis(
            bases=["ideo"],
            scripts=[("hani", "ideo", [-120])],
            vertical=False,
        )
    )
    c.current.append(table)

    assert c.asFeatureFile().asFea() == reference


def insertNamespace(name: str) -> str:
    head, sep, tail = name.partition(".")
    return head + "-deva" + sep + tail
