from __future__ import annotations

import math
from functools import cached_property
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from pypdf import PageObject
from pypdf._cmap import _parse_to_unicode
from pypdf.generic import DictionaryObject, EncodedStreamObject, IndirectObject, NameObject

from mls_roster_profiles.pypdf.enum import DelimiterGlyph, Entry, FontEntry, FontWeight


class Type1FontDictionary(BaseModel):
    """
    Represents a Type 1 font dictionary in a PDF file.

    Attributes:
        type_ (Literal[Entry.FONT]): Type of the dictionary. Must always be "/Font".
        subtype (Literal["/Type1", "/TrueType"]): Subtype of the font. Must always be "/Type1" or "/TrueType".
        base_font (str): Base font name, which is the name of the font resource.
        first_character (int): The first character code in the font.
        last_character (int): The last character code in the font.
        widths (list[int]): List of widths for each character in the font, indexed by character code.
        font_descriptor (DictionaryObject): Optional font descriptor dictionary containing additional font properties.
        encoding (str | DictionaryObject | None): Optional encoding name for the font, if not specified, the font uses a default encoding.
        to_unicode (EncodedStreamObject): Optional ToUnicode CMap for mapping character codes to Unicode values.

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type_: Literal[Entry.FONT] = Field(
        default=Entry.FONT,
        validation_alias=FontEntry.TYPE,
        serialization_alias="type",
        description='Type of the dictionary. Must always be "/Font".',
    )
    subtype: Literal["/Type1", "/TrueType"] = Field(
        default=...,
        validation_alias=FontEntry.SUBTYPE,
        description='Subtype of the font. Must always be "/Type1" or "/TrueType".',
    )
    base_font: str = Field(
        default=...,
        validation_alias=FontEntry.BASE_FONT,
        description="Base font name, which is the name of the font resource.",
    )
    first_character: int = Field(
        default=...,
        validation_alias=FontEntry.FIRST_CHARACTER,
        description="The first character code in the font.",
    )
    last_character: int = Field(
        default=...,
        validation_alias=FontEntry.LAST_CHARACTER,
        description="The last character code in the font.",
    )
    widths: list[int] = Field(
        default=...,
        validation_alias=FontEntry.WIDTHS,
        description="List of widths for each character in the font, indexed by character code.",
    )
    font_descriptor: DictionaryObject = Field(
        default=...,
        validation_alias=FontEntry.FONT_DESCRIPTOR,
        description="Optional font descriptor dictionary containing additional font properties.",
    )
    encoding: str | DictionaryObject | None = Field(
        default=None,
        validation_alias=FontEntry.ENCODING,
        description="Optional encoding name for the font, if not specified, the font uses a default encoding.",
    )
    to_unicode: EncodedStreamObject = Field(
        default=...,
        validation_alias=FontEntry.TO_UNICODE,
        description="Optional ToUnicode CMap for mapping character codes to Unicode values.",
    )

    @field_validator("subtype", mode="before")
    def validate_subtype(cls, value) -> str:
        """Converts the subtype to a string if it is passed as a `NameObject`."""
        if isinstance(value, NameObject):
            return str(value)


class Font(BaseModel):
    """
    Contains font properties, corresponding to the operands of the "Tf" operator.
    (See Table 58 - Entries in a Graphics State Parameter Dictionary in the PDF specification.)

    Attributes:
        font (str): Indirect reference to a font dictionary.
        size (float): Font size, expressed in text space units.
        font_dictionary (IndirectObject): Dictionary object representing the font, containing properties like type, subtype, base font, etc.
        weight (FontWeight): Computed font weight based on the font name.
        characters (dict[int, str]): Mapping of character codes to their corresponding glyphs.
        widths (dict[int, int]): Mapping of character codes to their corresponding widths in the font.

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    font: str = Field(
        default=...,
        description="Indirect reference to a font dictionary.",
    )
    size: float = Field(
        default=...,
        description="Font size, expressed in text space units.",
    )

    font_dictionary: IndirectObject = Field(
        default=...,
        description="Dictionary object representing the font, containing properties like type, subtype, base font, etc.",
    )

    @computed_field
    @cached_property
    def weight(self) -> FontWeight:
        if FontWeight.BOLD in self.font.lower():
            return FontWeight.BOLD
        elif FontWeight.LIGHT in self.font.lower():
            return FontWeight.LIGHT
        return FontWeight.REGULAR

    @staticmethod
    def raise_overlapping_glyphs(characters: list[str]) -> None:
        """
        Raises a ValueError if any of the characters in the provided list overlap with
        delimiter glyphs.

        This is to ensure that delimiter glyphs are not used in the font, as they are
        reserved for internal use.

        """
        overlapping_glyphs = list(set(characters) & set(DelimiterGlyph))
        if overlapping_glyphs:
            overlapping_glyphs_str = '", "'.join(overlapping_glyphs)
            raise ValueError(f'Delimiter glyphs "{overlapping_glyphs_str}" are not allowed in the font.')  # noqa: TRY003

    @computed_field
    @cached_property
    def characters(self) -> dict[int, str]:
        """
        Parses the ToUnicode CMap from the font dictionary and returns a mapping of
        character codes to their corresponding glyphs. Validates that the ToUnicode CMap
        exists and does not contain overlapping glyphs with delimiter glyphs.

        The last character in the mapping is removed, as it is reserved for internal use by `pypdf` and therefore not needed.

        Returns:
            dict[int, str]: A dictionary mapping character codes (int) to their corresponding glyphs (str).

        Raises:
            ValueError: If the ToUnicode CMap is missing or if any of the characters overlap with delimiter glyphs.

        """
        characters, _ = _parse_to_unicode(self.font_dictionary)
        characters.pop(-1)

        self.raise_overlapping_glyphs(list(characters.values()))

        return {ord(key): value for key, value in characters.items()}

    @computed_field
    @cached_property
    def widths(self) -> dict[int, int]:
        """
        Computes the widths of characters in the font based on the font dictionary.

        Returns:
            dict[int, int]: A dictionary mapping character codes (int) to their corresponding widths (int).

        Raises:
            ValueError: If the font dictionary does not contain the required properties for width calculation.

        """
        font_dictionary = Type1FontDictionary(**self.font_dictionary)

        widths = {}
        for idx in range(font_dictionary.first_character, font_dictionary.last_character + 1):
            if idx in self.characters:
                widths[idx] = font_dictionary.widths[idx - font_dictionary.first_character]

        return widths

    @classmethod
    def from_operands(cls, operands: list[str | float], page: PageObject) -> Font:
        """
        Creates a Font instance from the operands of the "Tf" operator.

        Args:
            operands (list[str | float]): An array of length 2, where the first element is the
                font name (string) and the second element is the font size (float).
            page (PageObject): The page object from which to retrieve the font dictionary.

        Returns:
            Font: An instance of the Font class initialized with the provided operands and page.

        Raises:
            ValueError: If the operands do not contain exactly two elements or if the font name is not found in the page resources.

        """
        if len(operands) != 2:
            raise ValueError("Operands must contain exactly two elements: font name (str) and size (float).")  # noqa: TRY003

        font, size = operands

        resources: dict = page.get(Entry.RESOURCES)
        fonts: dict = resources.get(Entry.FONT)
        font_dictionary: IndirectObject = fonts.get(font)

        return cls(
            font=font_dictionary[FontEntry.BASE_FONT],
            size=size,
            font_dictionary=font_dictionary,
        )

    def decode(self, byte_string: bytes) -> tuple[str, int]:
        """
        Decodes a byte string into its corresponding content and width using the font's
        character mapping.

        Args:
            byte_string (bytes): A byte string representing character codes in the font.

        Returns:
            tuple[str, int]: A tuple containing the decoded content (str) and the total width (int) of the content.

        """
        content = ""
        width = 0

        for char_idx in byte_string:
            content += self.characters[char_idx]
            width += self.widths[char_idx]

        return content, width


class BoundingBox(BaseModel):
    """
    Represents a bounding box defined by its minimum x and y coordinates, width, and
    height.

    Attributes:
        x_min (int): Minimum x-coordinate of the bounding box.
        y_min (int): Minimum y-coordinate of the bounding box.
        width (int): Width of the bounding box.
        height (int): Height of the bounding box. Currently unused.
        x_max (int): Maximum x-coordinate of the bounding box, calculated as `x_min + width`.
        y_max (int): Maximum y-coordinate of the bounding box, calculated as `y_min + height`. Currently unused.
        x_center (int): X-coordinate of the center of the bounding box, calculated as `x_min + width / 2`.
        y_center (int): Y-coordinate of the center of the bounding box, calculated as `y_min + height / 2`. Currently unused.

    """

    model_config = ConfigDict(validate_assignment=True)

    x_min: int = Field(
        default=0,
        description="Minimum x-coordinate of the bounding box.",
    )
    y_min: int = Field(
        default=0,
        description="Minimum y-coordinate of the bounding box.",
    )
    width: int = Field(
        default=0,
        description="Width of the bounding box.",
    )
    height: int = Field(
        default=0,
        description="Height of the bounding box. Currently unused.",
    )

    @field_validator("x_min", "y_min", "width", "height", mode="before")
    def ceiling(cls, value):
        if isinstance(value, float):
            return math.ceil(value)
        return value

    @property
    def x_max(self) -> int:
        """Maximum x-coordinate of the bounding box."""
        return self.x_min + self.width

    @property
    def y_max(self) -> int:
        """
        Maximum y-coordinate of the bounding box.

        Currently unused.

        """
        return self.y_min + self.height

    @property
    def x_center(self) -> int:
        """X-coordinate of the center of the bounding box."""
        return math.ceil(self.x_min + self.width / 2)

    @property
    def y_center(self) -> int:
        """
        Y-coordinate of the center of the bounding box.

        Currently unused.

        """
        return math.ceil(self.y_min + self.height / 2)


class TextObject(BaseModel):
    """
    Stores text object properties.

    Attributes:
        content (str): The text contained in the object.
        font (Font | None): Font used for the text object, containing font name and size.
        bounding_box (BoundingBox | None): Bounding box of the text object, defined by its minimum x and y coordinates, width, and height.

    """

    model_config = ConfigDict(validate_assignment=True)

    content: str = Field(
        default="",
        description="The text contained in the object.",
    )
    font: Font | None = Field(
        default=None,
        description="Font used for the text object, containing font name and size.",
    )
    bounding_box: BoundingBox | None = Field(
        default=None,
        description="Bounding box of the text object, defined by its minimum x and y coordinates, width, and height.",
    )

    def serialize(self) -> str:
        """
        Serializes the text object into a string output.

        Includes the decoded content, with attributes such as select bounding box coordinates and font weight enclosed in
        a pair of delimiters and appended (e.g., "<content><attributes><x_min>|<x_center>|<x_max>|<font_weight></attributes>").

        Raises:
            ValueError: If the font or bounding box is not set before serialization.

        """
        if self.font is None or self.bounding_box is None:
            raise ValueError("Font and bounding box must be set before serialization.")  # noqa: TRY003

        content = self.content
        x_coordinates = [self.bounding_box.x_min, self.bounding_box.x_center, self.bounding_box.x_max]
        font_weight = self.font.weight

        object_attributes = DelimiterGlyph.ATTRIBUTES_OPEN
        object_attributes += "|".join(str(attr).strip() for attr in [*x_coordinates, font_weight])
        object_attributes += DelimiterGlyph.ATTRIBUTES_CLOSE

        content += object_attributes
        content += DelimiterGlyph.END_OBJECT

        return content
