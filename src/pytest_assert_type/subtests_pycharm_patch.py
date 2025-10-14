# SPDX-FileCopyrightText: 2023-present Arseny Boykov (Bobronium) <mail@bobronium.me>
#
# SPDX-License-Identifier: MIT

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

if TYPE_CHECKING:
    import pluggy


try:  # pragma: no cover
    import pytest_subtests.plugin
    from pytest_subtests.plugin import SubTestReport
    from pytest_subtests.plugin import _SubTestContextManager
except ImportError:  # pragma: no cover

    def enable() -> None:
        pass
else:
    logger = logging.getLogger(__name__)

    class HookRelayProxy:
        """
        Used to modify SubTestReport to get proper subtests recognition in PyCharm.
        """

        def __init__(self, hook: Any) -> None:
            self.hook = hook

        def __getattr__(self, item: str) -> Any:
            return getattr(self.hook, item)

        def pytest_runtest_logreport(self, report: SubTestReport, *args: Any, **kwargs: Any) -> Any:
            try:
                report.nodeid += f"{report.sub_test_description()}"
                report.context.msg = "subtest"
                report.context.kwargs = {}
            except Exception:  # pragma: no cover
                logger.exception(
                    "Something went wrong while patching subtests to support pycharm test runner"
                )
            return self.hook.pytest_runtest_logreport(*args, report=report, **kwargs)

    class PyCharmCompatibleSubTestContextManager(_SubTestContextManager):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.ihook: pluggy.HookRelay = cast("pluggy.HookRelay", HookRelayProxy(self.ihook))

    def enable() -> None:
        pytest_subtests.plugin._SubTestContextManager = PyCharmCompatibleSubTestContextManager  # type: ignore[misc]  # noqa: SLF001
