from pathlib import Path

from parsimonious.grammar import Grammar as ParsimoniousGrammar

from mls_roster_profiles.pypdf.enum import DelimiterGlyph, FontWeight

_BASE_RULES = f"""
# Attributes
attr_light = attr_open coordinates light attr_close end_object
attr_regular = attr_open coordinates regular attr_close end_object
attr_bold = attr_open coordinates bold attr_close end_object
coordinates = digit+ separator digit+ separator digit+ separator

# Font weights
light = "{FontWeight.LIGHT}"
regular = "{FontWeight.REGULAR}"
bold = "{FontWeight.BOLD}"

# Characters
digit = ~r"[0-9]"
comma = ","
dot = "."
slash = "/"
space = " "
character = ~r"[^{repr(DelimiterGlyph.END_OBJECT.value).replace("'", "")}{DelimiterGlyph.TAB}{DelimiterGlyph.PRECEDES}{DelimiterGlyph.RETURN}{DelimiterGlyph.ATTRIBUTES_OPEN}{DelimiterGlyph.ATTRIBUTES_CLOSE}]"

# Delimiters
separator = "|"
end_object = "{repr(DelimiterGlyph.END_OBJECT.value).replace("'", "")}"
tab = "{DelimiterGlyph.TAB}"
precedes = "{DelimiterGlyph.PRECEDES}"
return = "{DelimiterGlyph.RETURN}"
attr_open = "{DelimiterGlyph.ATTRIBUTES_OPEN}"
attr_close = "{DelimiterGlyph.ATTRIBUTES_CLOSE}"
"""


class Grammar(ParsimoniousGrammar):
    def __init__(self, rules: Path) -> None:
        with open(rules) as f:
            rules_content = f.read()
            rules_content += _BASE_RULES

        super().__init__(rules_content)
