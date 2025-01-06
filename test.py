from tptq.feacomposer import FeaComposer


def test():
    c = FeaComposer(
        languageSystems={
            "DFLT": {"dflt"},
            "deva": {"dflt", "MAR "},
            "dev2": {"dflt", "MAR "},
        },
        glyphNameProcessor=lambda name: "Deva:" + name,
    )

    someClass = c.namedGlyphClass("foo", ["a"])

    with c.Lookup(feature="rphf"):
        c.sub("ra", "virama", by="repha")
        c.sub("a", c.glyphClass(["a"]), someClass, by="b")
        c.sub(c.glyphClass(["a"]), by=c.glyphClass(["a"]))

    with c.Lookup("foo") as lookupFoo:
        pass

    with c.Lookup("bar") as lookupBar:
        pass

    with c.Lookup(
        languageSystems={"dev2": {"dflt", "MAR "}},
        feature="xxxx",
        flags={"MarkAttachmentType": c.glyphClass(["virama"])},
    ):
        c.contextualSub("a", c.input("b"), "c", by="d")
        c.contextualSub("x", c.input("y"), lookupFoo, c.input("z"), lookupBar)

    print(c.asFeatureFile())


if __name__ == "__main__":
    test()
