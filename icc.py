"""super-simple inversion of control container; see pymple for something a bit more powerful."""

import typing as tg

_iccdict = dict()  # maps abstract type to implementation type


class IccKeyError(KeyError):
    pass


def register_class(abstractclass: type, implemclass: type):
    _iccdict[abstractclass] = implemclass


def get(abstractclass: type) -> type:
    _assert_exists(abstractclass)
    return _iccdict[abstractclass]


def init(abstractclass: type, *initargs, **initkwargs) -> tg.Any:
    return get(abstractclass)(*initargs, **initkwargs)  # call constructor


def _assert_exists(abstractclass):
    if abstractclass not in _iccdict:
        raise IccKeyError(f"no implementation is known for abstract class '{abstractclass}'")
