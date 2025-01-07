from tptq.feacomposer import FeaComposer


def test():
    def insertNamespace(name: str) -> str:
        head, sep, tail = name.partition(".")
        return head + "-deva" + sep + tail

    c = FeaComposer(
        languageSystems={
            "DFLT": {"dflt"},
            "dev2": {"dflt", "NEP "},
        },
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
        flags={"UseMarkFilteringSet": c.glyphClass(["virama"])},
    ):
        c.sub("ka", "virama", "ra", by="kRa")

    thaLike = c.namedGlyphClass("thaLike", ["tha", "dha", "sha"])

    with c.Lookup() as compact:
        for original in ["kRa", "usign"]:
            c.sub(original, by=original + ".compact")

    with c.Lookup(feature="pres"):
        c.contextualSub(thaLike, c.input("repha"), by="repha.tha")
        c.contextualSub(
            c.input("kRa", compact),
            c.input("usign", compact),
        )

    print(c.asFeatureFile())


if __name__ == "__main__":
    test()
