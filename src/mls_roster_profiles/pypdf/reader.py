from __future__ import annotations

from typing import Any

from numpy import matmul
from pypdf import PageObject, PdfReader

from mls_roster_profiles.pypdf.enum import DelimiterGlyph, Operator
from mls_roster_profiles.pypdf.models import BoundingBox, Font, TextObject


class Page(PageObject):
    """
    Represents a page in a PDF document, extending the functionality of PageObject to
    refine the text extraction process.

    This refinement better acknowledges the boundaries and ordering of text objects
    as presented, changes in fonts, and relative positioning of text within each text
    object. Delimiters, position metadata, and font metadata are injected into the
    string output of `extract_text` to support the organization of structured data
    using regular expression, parsing expression grammar, or similar techniques.

    Attributes:
        text_objects (list[TextObject]): List of text objects extracted from the page.
        _text_object (TextObject): Text object that is presently being constructed by the text extraction process.
        _font (Font | None): Font family and size of the present text object.
        _font_stack (list[Font]): Stack of font states that have been pushed to by the "q" operator.
        _x_displacement (float): Tracks how much horizontal space is presently taken up by this line of text, in unscaled text units.
        _td_x_translation (float): Sum total of x translations from "Td" operations within the present text object.
        _td_y_translation (float): Sum total of y translations from "Td" operations within the present text object.

    """

    # NOTE: Goal was to also subclass BaseModel, but its metaclass conflicts with PageObject's metaclass.
    # TODO: Investigate why a column of center-aligned text objects with different widths don't all have the same x_center, as expected.

    def __init__(self, pdf: PdfReader, page: PageObject) -> None:
        """
        Initializes a Page instance.

        Args:
            pdf (PdfReader): The PDF reader instance containing the document.
            page (PageObject): The page object to be wrapped.

        """
        super().__init__(pdf=pdf, indirect_reference=page.indirect_reference)
        self.update(page)

        self.text_objects: list[TextObject] = []

        self._text_object: TextObject = TextObject()
        self._font: Font | None = None
        self._font_stack: list[Font] = []

        self._x_displacement: float = 0.0
        self._td_x_translation: float = 0.0
        self._td_y_translation: float = 0.0

    def extract_text(self) -> str:
        """
        Extracts text from the page using a visitor pattern to handle operands before
        processing.

        Returns:
            str: The extracted text from the page, formatted as a string.

        """

        def visitor_operand_before(
            operator: bytes,
            operands: list[Any],
            cm_matrix: list[float],
            tm_matrix: list[float],
        ) -> None:
            """
            Visitor function to handle operands before processing them.

            Args:
                operator (bytes): The operator being processed.
                operands (list[Any]): The operands associated with the operator.
                cm_matrix (list[float]): The current transformation matrix for the content stream.
                tm_matrix (list[float]): The text matrix for the content stream.

            """
            if operator == Operator.END_TEXT_OBJECT:
                self._end_text_object()
            elif operator == Operator.SAVE_GRAPHICS_STATE:
                self._save_graphics_state()
            elif operator == Operator.RESTORE_GRAPHICS_STATE:
                self._restore_graphics_state()
            elif operator == Operator.MOVE_TEXT_POSITION:
                self._move_text_position(operands=operands)
            elif operator == Operator.SET_FONT:
                self._set_font(operands=operands)
            elif operator == Operator.SHOW_TEXT_STRING:
                self._show_text_string(operands=operands, cm_matrix=cm_matrix, tm_matrix=tm_matrix)
            elif operator == Operator.SHOW_TEXT_STRINGS:
                self._show_text_strings(operands=operands, cm_matrix=cm_matrix, tm_matrix=tm_matrix)

        super().extract_text(visitor_operand_before=visitor_operand_before)

        text_objects = [text_object.serialize() for text_object in self.text_objects]
        return "".join(text_objects)

    def _end_text_object(self) -> None:
        """
        Ends the current text object, finalizing its content and resetting the state.

        Corresponds to the "ET" operator in PDF content streams, though not exclusively
        used for that purpose.

        """
        if self._text_object.content:
            if self._text_object.content.endswith(DelimiterGlyph.RETURN):
                self._text_object.content = self._text_object.content[:-1]

            self._text_object.content = self._text_object.content.strip()
            self._text_object.font = self._font
            self.text_objects.append(self._text_object)

        self._text_object = TextObject()
        self._x_displacement = 0.0

    def _save_graphics_state(self) -> None:
        """
        Saves the current graphics state, including the current font, to a stack.

        Corresponds to the "q" operator in PDF content streams.

        """
        self._font_stack.append(self._font)

    def _restore_graphics_state(self) -> None:
        """
        Restores the graphics state from the stack, including the font and text object.

        Corresponds to the "Q" operator in PDF content streams.

        """
        self._end_text_object()
        self._font = self._font_stack.pop()

    def _move_text_position(self, operands: list[float], x_threshold: float = 0.3, y_threshold: float = 1.0) -> None:
        """
        Moves the text position based on the provided operands, adjusting the text
        object content accordingly. Corresponds to the "Td" operator in PDF content
        streams.

        Args:
            operands (list[float]): An array of length 2, where the first element is the
                x translation (float) and the second element is the y translation (float).
            x_threshold (float): The threshold for horizontal movement to determine if a tab or precedes delimiter should be added.
            y_threshold (float): The threshold for vertical movement to determine if a return delimiter should be added.

        """
        x_translation, y_translation = operands

        if y_translation < 0 and abs(x_translation + self._td_x_translation) < x_threshold:
            self._text_object.content += DelimiterGlyph.RETURN
            self._td_x_translation = 0
            self._td_y_translation += y_translation

        elif y_translation > 0 and abs(y_translation + self._td_y_translation) < y_threshold:
            self._td_y_translation = 0
            self._td_x_translation = 0

            if x_translation < 0:
                self._text_object.content += DelimiterGlyph.PRECEDES
            else:
                self._text_object.content += DelimiterGlyph.TAB

        elif abs(y_translation) >= y_threshold:
            self._end_text_object()

        elif x_translation < 0 and self._text_object.content:
            self._text_object.content += DelimiterGlyph.PRECEDES

        elif x_translation > 0 and self._text_object.content:
            x_translation_adjusted = x_translation - self._x_displacement
            if x_translation_adjusted > x_threshold * self._font.size:
                self._text_object.content += DelimiterGlyph.TAB
            else:
                self._td_x_translation += x_translation

        self._x_displacement = 0

    def _set_font(self, operands: list[str | float]) -> None:
        """
        Sets the font for the current text object based on the provided operands.
        Corresponds to the "Tf" operator in PDF content streams.

        Args:
            operands (list[str | float]): An array of length 2, where the first element is the
                font name (string) and the second element is the font size (float).

        """
        self._end_text_object()
        self._font = Font.from_operands(operands=operands, page=self)

    def _set_origin(self, cm_matrix: list[float], tm_matrix: list[float]) -> None:
        """
        Sets the origin for the current text object based on the transformation
        matrices.

        Args:
            cm_matrix (list[float]): The current transformation matrix for the content stream.
            tm_matrix (list[float]): The text matrix for the content stream.

        """
        if self._text_object.bounding_box is None:
            tm_matrix_reshaped = [
                [tm_matrix[0], tm_matrix[1], 0],
                [tm_matrix[2], tm_matrix[3], 0],
                [tm_matrix[4], tm_matrix[5], 1],
            ]
            cm_matrix_reshaped = [
                [cm_matrix[0], cm_matrix[1], 0],
                [cm_matrix[2], cm_matrix[3], 0],
                [cm_matrix[4], cm_matrix[5], 1],
            ]

            shortened_matrix = matmul(tm_matrix_reshaped, cm_matrix_reshaped)

            self._text_object.bounding_box = BoundingBox(
                x_min=shortened_matrix[2, 0],
                y_min=shortened_matrix[2, 1],
            )

    def _handle_text_string(self, byte_string: bytes) -> None:
        """
        Handles a text string by decoding it with the current font and updating the text
        object.

        Args:
            byte_string (bytes): The byte string to decode and add to the text object.

        """
        content, width = self._font.decode(byte_string=byte_string)
        self._text_object.content += content

        displacement = width / 1000 * self._font.size
        self._x_displacement += displacement
        self._text_object.bounding_box.width = max(self._text_object.bounding_box.width, self._x_displacement)

    def _show_text_string(self, operands: list[bytes], cm_matrix: list[float], tm_matrix: list[float]) -> None:
        """
        Shows a text string by decoding it and updating the text object. Corresponds to
        the "Tj" operator in PDF content streams.

        Args:
            operands (list[bytes]): An array containing a single byte string to be shown.
            cm_matrix (list[float]): The current transformation matrix for the content stream.
            tm_matrix (list[float]): The text matrix for the content stream.

        """
        self._set_origin(cm_matrix=cm_matrix, tm_matrix=tm_matrix)
        self._handle_text_string(byte_string=operands[0])

    def _show_text_strings(self, operands: list[bytes | int], cm_matrix: list[float], tm_matrix: list[float]) -> None:
        """
        Shows multiple text strings by decoding each one and updating the text object.
        Corresponds to the "TJ" operator in PDF content streams.

        Args:
            operands (list[bytes | int]): An array containing arrays of length 2, where the first element
                is a byte string to be shown and the second element is a spacing value (int).
            cm_matrix (list[float]): The current transformation matrix for the content stream.
            tm_matrix (list[float]): The text matrix for the content stream.

        """
        self._set_origin(cm_matrix=cm_matrix, tm_matrix=tm_matrix)
        for operand in operands[0]:
            if isinstance(operand, bytes):
                self._handle_text_string(byte_string=operand)
            else:
                self._x_displacement += operand / 1000 * self._font.size
                self._text_object.bounding_box.width = max(self._text_object.bounding_box.width, self._x_displacement)
