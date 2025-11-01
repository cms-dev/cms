import dataclasses
import logging
import re
import tomllib
import sys
import types
import typing


class ConfigError(Exception):
    """Exception for critical configuration errors."""

    pass


class ConfigTypeError(ConfigError):
    def __init__(self, path: str, expected: str, got: object):
        msg = f"Expected {path} to be {expected}, got {type(got).__name__}"
        super().__init__(msg)


_T = typing.TypeVar("_T")


def parse_config(
    config_file_path: str, config_class: type[_T], enoent_help: str = ""
) -> _T:
    """
    Load a TOML config file into a config class, checking for type errors.

    config_class must be a dataclass. Each of its fields must have a type that
    is either one of the basic TOML types (str, int, float, bool), another
    dataclass satisfying the same rules, a list[T] with T satisfying these
    rules, a dict[str, T] with T satisfying these rules, a tuple whose types
    satisfy these rules, or an optional form (T | None) of any of the above.

    Dataclasses correspond to tables with specific keys in the TOML file. All
    other values correspond directly to the TOML types.

    If a dataclass field's name ends with "_", the corresponding TOML table key
    will not have the underscore. This is to allow table keys corresponding to
    python keywords.

    config_file_path: Path to the config TOML file.
    config_class: Dataclass to load the configuration into.
    enoent_help: Extra help text for "file not found" error.
    """
    try:
        data = tomllib.load(open(config_file_path, "rb"))
        return parse_config_obj(data, config_class, "")
    except FileNotFoundError:
        logging.critical(
            f"Cannot find configuration file {config_file_path}{enoent_help}"
        )
        sys.exit(1)
    except (ConfigError, tomllib.TOMLDecodeError) as e:
        # Don't show stacktrace for basic errors.
        logging.critical(f"Cannot load configuration file {config_file_path}: {e}")
        sys.exit(1)
    except Exception:
        logging.critical(
            f"Cannot load configuration file {config_file_path}", exc_info=True
        )
        sys.exit(1)


def format_key(key: str):
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    else:
        # This should be a valid TOML key, assuming python escape sequences are
        # compatible with toml ones. In any case, it's good enough for error
        # messages.
        return repr(key)

def join_path(path: str, new_part: str):
    if path != "":
        return path + "." + new_part
    else:
        return new_part

# tomllib return types: str, int, float, bool, datetime (not really relevant),
# list[X], dict[str, X]

def parse_config_obj(data: object, obj_class: type[_T], path: str) -> _T:
    if typing.get_origin(obj_class) in (typing.Union, types.UnionType):
        # The only unions we support are " | None", for optionals.
        args = typing.get_args(obj_class)
        assert len(args) == 2 and args[1] is type(None)
        # If we reached this function, then we are trying to parse `data` as a
        # value of type `obj_class`. TOML has no `null`, so this means `data`
        # must match the non-None side of the union.
        obj_class = args[0]

    if dataclasses.is_dataclass(obj_class):
        if not isinstance(data, dict):
            raise ConfigTypeError(path, "a table", data)
        kw_args = {}
        for field in dataclasses.fields(obj_class):
            if not field.init:
                continue
            # Some field names are suffixed with _ because they would otherwise
            # conflict with python keywords.
            config_name = field.name.removesuffix("_")

            is_required = (
                field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING
            )
            field_path = join_path(path, format_key(config_name))
            if is_required and config_name not in data:
                raise ConfigError(f"Key {field_path} is required")

            if config_name in data:
                kw_args[field.name] = parse_config_obj(
                    data[config_name], typing.cast(type[_T], field.type), field_path
                )
                del data[config_name]

        for k in data:
            thispath = join_path(path, format_key(k))
            logging.warning(f"Unrecognized key {thispath} in config, ignoring.")

        return obj_class(**kw_args)

    elif typing.get_origin(obj_class) is dict:
        args = typing.get_args(obj_class)
        assert args[0] is str
        value_type = args[1]

        if not isinstance(data, dict):
            raise ConfigTypeError(path, "a table", data)

        result = {}
        for k, v in data.items():
            result[k] = parse_config_obj(v, value_type, join_path(path, format_key(k)))

        # As far as I can tell, Python's type system doesn't support narrowing
        # _T based on runtime checks of obj_class, so the simplest way to get
        # this to type-check is to build result as a generic dict and tell the
        # type checker that it has the right type.
        return typing.cast(_T, result)

    elif typing.get_origin(obj_class) in (tuple, list):
        args = typing.get_args(obj_class)
        list_mode = True
        if typing.get_origin(obj_class) is tuple:
            # Tuples can be either immutable lists (tuple[T, ...]) or lists
            # having elements of different types (anything else).
            list_mode = len(args) == 2 and args[1] == Ellipsis

        if not isinstance(data, list):
            raise ConfigTypeError(path, "a list", data)

        result = []
        if list_mode:
            value_type = args[0]
            for i, x in enumerate(data):
                result.append(parse_config_obj(x, value_type, path + f"[{i}]"))
        else:
            if len(args) != len(data):
                raise ConfigError(
                    f"Expected {path} to have {len(args)} elements, got {len(data)}"
                )
            for i, (type_, val) in enumerate(zip(args, data)):
                result.append(parse_config_obj(val, type_, path + f"[{i}]"))

        # typing.cast isn't enough to make the type checker happy here.
        return obj_class(result)  # type: ignore

    elif obj_class in (str, int, bool):
        if not isinstance(data, obj_class):
            raise ConfigTypeError(path, obj_class.__name__, data)
        return data

    elif obj_class is float:
        # Allow specifying floats as ints.
        if not isinstance(data, int | float):
            raise ConfigTypeError(path, "float", data)
        return typing.cast(_T, float(data))

    else:
        raise AssertionError(f"Unsupported type found in configuration: {obj_class}")
