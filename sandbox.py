from tptq.feacomposer import FeaComposer

c = FeaComposer(languageSystems={"latn": {"dflt"}})

with c.Lookup(feature="liga"):
    c.sub("f", "i", by="f_i")

print(c.asFeatureFile())
