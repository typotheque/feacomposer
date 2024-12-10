# FeaComposer

FeaComposer is a wrapper around [fontTools.feaLib.ast](https://github.com/fonttools/fonttools/blob/main/Lib/fontTools/feaLib/ast.py) for programmatically **composing** code in the **FEA** format (officially the “[OpenType feature file](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html)”).

> API stability between [minor versions](https://semver.org) is not guaranteed before version 2.

> Users are expected to use the fontTools.feaLib.ast classes directly for functionalities that are not yet covered by the FeaComposer API.

The API is designed to be close to the FEA syntax for familiarity, but is tightened up to be more manageable for complicated projects. On the other hand, as an [embedded domain-specific language](https://en.wikipedia.org/wiki/Domain-specific_language) (eDSL) it allows you to take full advantage of Python, especially static type checking.

## Do you need this?

For the following use cases, you **will not** benefit from this package:

- You just want to write FEA code directly.
  - Read [The (Unofficial) OpenType Cookbook](https://opentypecookbook.com) if you’re a beginner, and the [OpenType Feature File Specification](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html) if you need to learn more about the FEA format.
- You want to compose [OpenType Layout](https://learn.microsoft.com/en-us/typography/opentype/spec/ttochap1) (OTL) rules in Python code independently from the FEA format. You don’t need static type checking.
  - Try [fontFeatures](https://github.com/simoncozens/fontFeatures), which allows you to work on the syntax tree of OTL rules rather than the FEA code. It still allows you to export FEA code if you want.
- You want some Python logic in FEA code. You don’t need the usual code editor experience for Python, or you care about how the FEA code is formatted.
  - Try [FeaPyFoFum](https://github.com/typesupply/feaPyFoFum), which provides a template language for embedding Python inside FEA code.

## Getting started

Install from PyPI:

```sh
pip install tptq.feacomposer
```

Compose FEA code in Python:

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
