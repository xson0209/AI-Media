from __future__ import annotations

import asyncio
import inspect

import pytest


def pytest_addoption(parser):
    parser.addini("asyncio_mode", "Compatibility placeholder for async test mode", default="auto")


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: run coroutine test functions with asyncio.run")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if pyfuncitem.config.pluginmanager.hasplugin("asyncio"):
        return None

    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None

    test_args = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_function(**test_args))
    return True
