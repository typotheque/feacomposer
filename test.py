from tptq.feacomposer import FeaComposer


def testFeaComposer() -> FeaComposer:
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

    return c


if __name__ == "__main__":
    print(testFeaComposer().asFeatureFile())
