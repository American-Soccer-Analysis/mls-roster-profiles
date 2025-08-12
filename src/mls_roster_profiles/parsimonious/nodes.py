import datetime
from collections.abc import Iterable
from enum import StrEnum
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from dateutil import parser as date_parser
from loguru import logger
from parsimonious.nodes import Node
from parsimonious.nodes import NodeVisitor as ParsimoniousNodeVisitor
from pydantic import BaseModel


class BaseModelNotFoundError(Exception):
    """Exception raised when a `BaseModel` class is not found or is invalid, in the
    context of the custom `NodeVisitor` class which dynamically creates visitor methods
    based on the provided model."""

    def __init__(self, message: str = "BaseModel class not found or invalid."):
        super().__init__(message)


class NodeVisitor(ParsimoniousNodeVisitor):
    """
    Extended `NodeVisitor` that dynamically creates visit methods based on the
    annotations of a provided Pydantic `BaseModel` class.

    For terminal nodes (e.g., strings, enum values, integers, dates, etc.), the visitor method
    simply returns a dictionary with a single key-value pair, representing the attribute name
    and its extracted value, respectively.

    For nested structures, or lists of nested structures, this method traverses these until
    reaching all terminal nodes and then continues onto the next attribute. These structures are
    accordingly represented as dictionaries reflecting all nested attributes.

    Support for simple lists is not yet implemented.

    It is expected that all the field names in the Pydantic model are unique and exactly
    match the respective named variables in the grammar. Where applicable, the field's
    `validation_alias` or `alias` is used in this regard. In this same context, any nested
    Pydantic models will have their names converted from camel case to snake case
    (e.g., `MyModel` becomes `my_model`, and the method is called `visit_my_model`).

    Attributes:
        model_class (BaseModel): The Pydantic model class to use for creating visitor methods.

    """

    model_class: BaseModel | None = None

    def __init__(self) -> None:
        super().__init__()
        self._create_visitors(self.model_class)
        self._add_model_visitor("root", self.model_class, include_key=False)

    @staticmethod
    def _get_fields(model_class: BaseModel) -> Iterable[tuple[str, type]]:
        """
        Get the fields of a Pydantic model class, including their names and types. This
        method handles both the `alias` and `validation_alias` attributes of the model
        fields, ensuring that the correct field names are used in the visitor methods.

        Args:
            model_class (BaseModel): The Pydantic model class to inspect.

        Yields:
            tuple[str, type]: A tuple containing the field name and its type annotation.

        """
        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation
            if field_info.validation_alias:
                field_name = field_info.validation_alias
            elif field_info.alias:
                field_name = field_info.alias
            yield field_name, field_type

    def _create_visitors(self, model_class: BaseModel) -> None:
        """
        Recursively create visitor methods for each field in the provided Pydantic model
        class.

        For terminal nodes (e.g., strings, enum values, integers, dates, etc.), the visitor method
        simply returns a dictionary with a single key-value pair, representing the attribute name
        and its extracted value, respectively.

        For nested structures, or lists of nested structures, this method traverses these until
        reaching all terminal nodes and then continues onto the next attribute. These structures are
        accordingly represented as dictionaries reflecting all nested attributes.

        Support for simple lists is not yet implemented.

        Args:
            model_class (BaseModel): The Pydantic model class to use for creating visitor methods.

        Raises:
            BaseModelNotFoundError: If the provided model class is not a valid `BaseModel` or is `None`.

        """
        if model_class is None or not issubclass(model_class, BaseModel):
            raise BaseModelNotFoundError

        for field_name, field_type in self._get_fields(model_class):
            if self._is_str(field_type):
                self._add_str_visitor(field_name)

            elif self._is_date(field_type):
                self._add_date_visitor(field_name)

            elif self._is_int(field_type):
                self._add_int_visitor(field_name)

            elif self._is_list_of_model(field_type):
                child_type = get_args(field_type)[0]
                self._create_visitors(child_type)
                self._add_model_visitor(field_name, child_type)

            elif self._is_model(field_type):
                self._add_model_visitor(field_name, field_type)
                self._create_visitors(field_type)

            elif self._is_list(field_type):
                # TODO: Check that there's a user-defined visitor; if not, raise error
                pass

            else:
                logger.warning(f"Unsupported type for field `{field_name}`: {field_type}")

    @staticmethod
    def _is_str(annotation: type) -> bool:
        """
        Check if the provided field annotation is a string type or a union of only
        string-like (i.e., strings, literals, or enum values) and/or `None` types.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is a string type or a union of string-like types, False otherwise.

        """
        if annotation is str:
            return True
        if isinstance(annotation, UnionType) or get_origin(annotation) is Union:
            args = get_args(annotation)
            if all(
                arg is str
                or arg is NoneType
                or (get_origin(arg) is Literal and all(isinstance(val, str) for val in get_args(arg)))
                or issubclass(arg, StrEnum)
                for arg in args
            ):
                return True
        return False

    @staticmethod
    def _is_date(annotation: type) -> bool:
        """
        Check if the provided field annotation is a date type or a union of only date-
        like and/or `None` types.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is a date type or a union of date-like types, False otherwise.

        """
        if annotation is datetime.date:
            return True
        if isinstance(annotation, UnionType) or get_origin(annotation) is Union:
            args = get_args(annotation)
            if all(arg is datetime.date or arg is NoneType for arg in args):
                return True
        return False

    @staticmethod
    def _is_int(annotation: type) -> bool:
        """
        Check if the provided field annotation is an integer type or a union of only
        integer-like and/or `None` types.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is an integer type or a union of integer-like types, False otherwise.

        """
        if annotation is int:
            return True
        if isinstance(annotation, UnionType) or get_origin(annotation) is Union:
            args = get_args(annotation)
            if all(arg is int or arg is NoneType for arg in args):
                return True
        return False

    @staticmethod
    def _is_list(annotation: type) -> bool:
        """
        Check if the origin of the provided field annotation is a list type.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is a list type, False otherwise.

        """
        return get_origin(annotation) is list

    @staticmethod
    def _is_model(annotation: type) -> bool:
        """
        Check if the provided field annotation is a Pydantic model.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is a subclass of `BaseModel`, False otherwise.

        """
        # NOTE: Only acknowledges `attr: BaseModel`
        #       Can be extended if `attr: BaseModel | None` is ever considered valid
        return issubclass(annotation, BaseModel)

    @staticmethod
    def _is_list_of_model(annotation: type) -> bool:
        """
        Check if the provided field annotation is a list of Pydantic models.

        Args:
            annotation (type): The type annotation to check.

        Returns:
            bool: True if the annotation is a list of models, False otherwise.

        """
        if NodeVisitor._is_list(annotation):
            args = get_args(annotation)
            return len(args) == 1 and NodeVisitor._is_model(args[0])
        return False

    @staticmethod
    def flatten(visited_children: list[Any]) -> Iterable[Any]:
        """
        Recursively flatten a list of iterables, removing all non-visited nodes.

        Args:
            visited_children (list[Any]): A list of visited children nodes, which may include nested structures
                such as lists, dictionaries, or other iterables.

        Yields:
            Any: Flattened items from the visited children, yielding only terminal nodes or non-iterable items.

        """

        def can_flatten(thing):
            if isinstance(thing, str | dict | bytes):
                return False
            return isinstance(thing, Iterable)

        for item in visited_children:
            if isinstance(item, Node):
                continue

            if not can_flatten(item):
                yield item
            else:
                yield from NodeVisitor.flatten(item)

    @classmethod
    def _add_str_visitor(cls, field_name: str) -> None:
        """
        Add a visitor method for string fields in the Pydantic model.

        This method creates a visitor that extracts the text from the node,
        strips any leading or trailing whitespace, and returns it as a dictionary
        with the field name as the key.

        Args:
            field_name (str): The name of the field in the Pydantic model.

        """

        def _visitor(self, node: Node, visited_children: list[Any]) -> dict[str, str]:
            return {field_name: node.text.strip()}

        setattr(cls, f"visit_{field_name}", _visitor)

    @classmethod
    def _add_date_visitor(cls, field_name: str) -> None:
        """
        Add a visitor method for date fields in the Pydantic model.

        This method creates a visitor that parses the date from the node's text
        and returns it as a dictionary with the field name as the key.

        Args:
            field_name (str): The name of the field in the Pydantic model.

        """

        def _visitor(self, node: Node, visited_children: list[Any]) -> dict[str, datetime.date]:
            return {field_name: date_parser.parse(node.text.strip()).date()}

        setattr(cls, f"visit_{field_name}", _visitor)

    @classmethod
    def _add_int_visitor(cls, field_name: str) -> None:
        """
        Add a visitor method for integer fields in the Pydantic model.

        This method creates a visitor that extracts the text from the node,
        removes any commas, converts it to an integer, and returns it as a
        dictionary with the field name as the key.

        Args:
            field_name (str): The name of the field in the Pydantic model.

        """

        def _visitor(self, node: Node, visited_children: list[Any]) -> dict[str, int]:
            text = node.text.strip()
            return {field_name: int(text.replace(",", ""))}

        setattr(cls, f"visit_{field_name}", _visitor)

    @staticmethod
    def _get_list_fields(model_class: BaseModel) -> list[str]:
        """
        Get the list fields from a Pydantic model class.

        Args:
            model_class (BaseModel): The Pydantic model class to inspect.

        Returns:
            list[str]: A list of field names that are lists in the model.

        """
        list_fields = []
        for _field_name, _field_type in NodeVisitor._get_fields(model_class):
            if get_origin(_field_type) is list:
                list_fields.append(_field_name)

        return list_fields

    @classmethod
    def _add_model_visitor(cls, field_name: str, model_class: BaseModel, include_key: bool = True) -> None:
        """
        Add a visitor method for fields that are Pydantic models.

        This method creates a visitor that collects child nodes into a dictionary,
        where each key corresponds to a field in the model.

        If there are multiple children with the same key, and their respective values are strings,
        they are concatenated with a space in between. If the values are lists, they are
        aggregated into a single list.

        If `include_key` is True, the field name is included as a key in the returned dictionary.
        This is typically the difference between `attr: list[BaseModel]` and `attr: BaseModel`.

        Args:
            field_name (str): The name of the field in the Pydantic model.
            model_class (BaseModel): The Pydantic model class to use for creating the visitor.
            include_key (bool): Whether to include the field name as a key in the returned dictionary.

        """
        list_fields = cls._get_list_fields(model_class)

        def _visitor(self, node: Node, visited_children: list[Any]) -> dict[str, Any]:
            model = {field: [] for field in list_fields}
            for child in NodeVisitor.flatten(visited_children):
                if isinstance(child, dict):
                    if len(child) != 1:
                        logger.warning(f"Unexpected child dictionary length ({len(child)}) in `{field_name}` visitor.")
                        continue
                    key, value = next(iter(child.items()))
                    if key in list_fields:
                        if isinstance(value, list):
                            model[key].extend(value)
                        else:
                            model[key].append(value)
                    elif key in model:
                        if isinstance(model[key], str):
                            model[key] += " " + value
                        else:
                            logger.warning(f"Unexpected duplicate key (`{key}`) in `{field_name}` visitor.")
                    else:
                        model.update(child)
                else:
                    logger.warning(f"Unexpected child type ({type(child)}) in `{field_name}` visitor.")

            if include_key:
                return {field_name: model}

            return model

        setattr(cls, f"visit_{field_name}", _visitor)

    def generic_visit(self, node: Node, visited_children: list[Any]) -> list[Any] | Node:
        """
        Override the generic visit method to handle cases where no specific visitor
        method is defined.

        Args:
            node (Node): The current node being visited.
            visited_children (list[Any]): A list of children nodes that were visited.

        Returns:
            list[Any] | Node: The visited children if any, or the node itself if no children were visited.

        """
        return visited_children or node

    def serialize(self, tree: Node) -> BaseModel:
        """
        Serialize the parsed tree into a Pydantic model instance.

        Args:
            tree (Node): The root node of the parsed tree.

        Returns:
            BaseModel: An instance of the Pydantic model class, validated and populated with the parsed data.

        """
        result = self.visit(tree)
        return self.model_class.model_validate(result)
