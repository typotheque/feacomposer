# FeaComposer

**FeaComposer** is a wrapper around [fontTools.feaLib.ast](https://github.com/fonttools/fonttools/blob/main/Lib/fontTools/feaLib/ast.py) for programmatically **composing** [OpenType Layout rules](https://learn.microsoft.com/en-us/typography/opentype/spec/ttochap1) in the **FEA** syntax (formally known as the “[OpenType feature file](https://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html)”). It’s designed to be a minimal eDSL ([embedded domain-specific language](https://en.wikipedia.org/wiki/Domain-specific_language)) in Python that feels similar to the FEA syntax but is more manageable for complicated situations.

Basic usage:

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
