# FeaComposer

**FeaComposer** is a wrapper around [fontTools.feaLib.ast](https://github.com/fonttools/fonttools/blob/main/Lib/fontTools/feaLib/ast.py) for programmatically **composing** [OpenType Layout rules](https://learn.microsoft.com/en-us/typography/opentype/spec/ttochap1) in the **FEA** syntax (formally known as the “[OpenType feature file](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html)”). It’s designed to be a minimal eDSL ([embedded domain-specific language](https://en.wikipedia.org/wiki/Domain-specific_language)) in Python that feels similar to the FEA syntax but is more manageable for complicated situations.

For the following use cases, you **will not** benefit from this package:

- You just want to write FEA code directly.
  - Read [The (Unofficial) OpenType Cookbook](https://opentypecookbook.com) if you’re a beginner, and the [OpenType Feature File Specification](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html) if you need to learn more about the FEA syntax.
- You want to compose OTL rules in Python code independently from the FEA syntax, and you don’t need static type checking.
  - Try [fontFeatures](https://github.com/simoncozens/fontFeatures), which allows you to work on the syntax tree of OTL rules rather than the syntax tree of FEA code. It still allows you to export FEA code if you want.
- You want some Python logic in FEA code, and you don’t need the usual code editor experience for Python.
  - Try [FeaPyFoFum](https://github.com/typesupply/feaPyFoFum), which provides a template language for embedding Python inside FEA code.

## Basic usage

```py
from tptq.feacomposer import FeaComposer

c = FeaComposer()

with c.Lookup(feature="liga"):
    c.sub(["f", "i"], "fi")

print(c.code())
```

The printed FEA code:

```fea
languagesystem DFLT dflt;
feature liga {
    lookup _1 {
        lookupflag 0;
        sub f i by fi;
    } _1;

} liga;
```

See [test.py](https://github.com/typotheque/feacomposer/blob/main/test.py) for more advanced usage.
