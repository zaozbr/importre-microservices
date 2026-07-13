import base64
print(base64.b64encode(b'&''&def _normalize_stem_for_fuzzy(stem):
    s = stem
    s = re.sub(r"\\[=[A-Z]+[-]?\\s+?\]?", '', s, flags=re.I)
    s = re.sub(r"\(Track \d+\)", '', s, flags=re.I)
    s = re.sub(r"\(v?\d+(?:\.\d+)?(?:[a-z]?)\)", '', s, flags=re.I)
    s = re.sub(r"\([A-Za-z]{1,8}(?:, [A-Za-z]{2,8})*\)", '', s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ._-\t\r")

='''&).decode())
