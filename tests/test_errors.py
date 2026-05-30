"""Tests for primer/errors.py — all eight exceptions exist and are well-formed."""
from __future__ import annotations

import pytest

import primer.errors as err
from primer.errors import PrimerError


ALL_EXCEPTIONS = [
    err.ConfigError,
    err.OllamaOutputError,
    err.GenerationError,
    err.AgentNotFoundError,
    err.InsufficientTasksError,
    err.TaskValidationError,
    err.IsolationError,
]


@pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS)
def test_subclasses_primer_error(exc_class):
    assert issubclass(exc_class, PrimerError)


@pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS)
def test_subclasses_exception(exc_class):
    assert issubclass(exc_class, Exception)


@pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS)
def test_instantiable_with_message(exc_class):
    msg = f"test message for {exc_class.__name__}"
    instance = exc_class(msg)
    assert str(instance) == msg


@pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS)
def test_raiseable(exc_class):
    with pytest.raises(exc_class):
        raise exc_class("test")


@pytest.mark.parametrize("exc_class", ALL_EXCEPTIONS)
def test_catchable_as_primer_error(exc_class):
    with pytest.raises(PrimerError):
        raise exc_class("test")


def test_primer_error_is_exception():
    assert issubclass(PrimerError, Exception)
