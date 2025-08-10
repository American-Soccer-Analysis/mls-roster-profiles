from enum import Enum, EnumMeta, StrEnum


class Entry(StrEnum):
    """Enumerator for top-level entries in a PDF file."""

    RESOURCES = "/Resources"
    FONT = "/Font"


class FontEntry(StrEnum):
    """Enumerator for font entries in a PDF file."""

    TYPE = "/Type"
    SUBTYPE = "/Subtype"
    BASE_FONT = "/BaseFont"
    FIRST_CHARACTER = "/FirstChar"
    LAST_CHARACTER = "/LastChar"
    WIDTHS = "/Widths"
    FONT_DESCRIPTOR = "/FontDescriptor"
    ENCODING = "/Encoding"
    TO_UNICODE = "/ToUnicode"


class FontWeight(StrEnum):
    """Enumerator for recognized font weights."""

    LIGHT = "light"
    REGULAR = "regular"
    BOLD = "bold"


class DelimiterGlyph(StrEnum):
    """
    Enumerator for delimiter glyphs injected during text extraction.

    Attributes:
        END_OBJECT: Represents the end of a text object in the PDF structure.
        TAB: Represents a tab character.
        PRECEDES: Represents when a section of text appears after the preceding section of text within the content stream
            (scoped to a single text object), but is actually displayed to the left of it when the PDF is rendered.
        RETURN: Represents a line break within a text object.
        ATTRIBUTES_OPEN: Represents the opening of comma-separated attributes (e.g., x-coordinates, font weights, etc.)
            printed at the end of a text object.
        ATTRIBUTES_CLOSE: Represents the closing of comma-separated attributes (e.g., x-coordinates, font weights, etc.)
            printed at the end of a text object.

    """

    END_OBJECT = "\n"

    TAB = "⇥"
    PRECEDES = "⇤"
    RETURN = "↩"

    ATTRIBUTES_OPEN = "《"
    ATTRIBUTES_CLOSE = "》"


class BytesEnumMeta(EnumMeta):
    """Metaclass for byte enumerators that allows iteration and membership testing based
    on the byte values of the enum members."""

    def __iter__(cls):
        return (member.value for member in cls.__members__.values())

    def __contains__(cls, item):
        if isinstance(item, bytes):
            return any(item == member.value for member in cls.__members__.values())
        return False


class BytesEnum(bytes, Enum, metaclass=BytesEnumMeta):
    """Base class for byte enumerators that allows iteration and membership testing
    based on the byte values of the enum members."""

    pass


class Operator(BytesEnum):
    """Enumerator for PDF operators used in content streams."""

    END_TEXT_OBJECT = b"ET"
    SAVE_GRAPHICS_STATE = b"q"
    RESTORE_GRAPHICS_STATE = b"Q"
    MOVE_TEXT_POSITION = b"Td"
    SET_FONT = b"Tf"
    SHOW_TEXT_STRING = b"Tj"
    SHOW_TEXT_STRINGS = b"TJ"
