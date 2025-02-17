# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from packaging.version import Version

from pants.backend.plugin_development import pants_requirements
from pants.backend.plugin_development.pants_requirements import (
    PantsRequirementsTargetGenerator,
    determine_version,
)
from pants.backend.python.target_types import (
    PythonRequirementModulesField,
    PythonRequirementResolveField,
    PythonRequirementsField,
)
from pants.engine.addresses import Address
from pants.engine.internals.graph import _TargetParametrizations, _TargetParametrizationsRequest
from pants.testutil.rule_runner import QueryRule, RuleRunner
from pants.util.pip_requirement import PipRequirement


@pytest.mark.parametrize(
    "pants_version,expected",
    (
        ("2.4.0.dev1", "==2.4.0.dev1"),
        ("2.4.0rc1", ">=2.4.0a0,<2.5"),
        ("2.4.0", ">=2.4.0a0,<2.5"),
    ),
)
def test_determine_version(monkeypatch, pants_version: str, expected: str) -> None:
    monkeypatch.setattr(pants_requirements, "PANTS_SEMVER", Version(pants_version))
    assert determine_version() == expected


def test_target_generator() -> None:
    rule_runner = RuleRunner(
        rules=(
            *pants_requirements.rules(),
            QueryRule(_TargetParametrizations, [_TargetParametrizationsRequest]),
        ),
        target_types=[PantsRequirementsTargetGenerator],
    )

    rule_runner.write_files(
        {
            "BUILD": (
                "pants_requirements(name='default')\n"
                "pants_requirements(\n"
                "  name='no_testutil', testutil=False, resolve='a'\n"
                ")"
            )
        }
    )

    result = rule_runner.request(
        _TargetParametrizations,
        [
            _TargetParametrizationsRequest(
                Address("", target_name="default"), description_of_origin="tests"
            )
        ],
    ).parametrizations
    assert len(result) == 2
    pants_req = next(t for t in result.values() if t.address.generated_name == "pantsbuild.pants")
    testutil_req = next(
        t for t in result.values() if t.address.generated_name == "pantsbuild.pants.testutil"
    )
    assert pants_req[PythonRequirementModulesField].value == ("pants",)
    assert testutil_req[PythonRequirementModulesField].value == ("pants.testutil",)
    assert pants_req[PythonRequirementsField].value == (
        PipRequirement.parse(f"pantsbuild.pants{determine_version()}"),
    )
    assert testutil_req[PythonRequirementsField].value == (
        PipRequirement.parse(f"pantsbuild.pants.testutil{determine_version()}"),
    )
    for t in (pants_req, testutil_req):
        assert not t[PythonRequirementResolveField].value

    result = rule_runner.request(
        _TargetParametrizations,
        [
            _TargetParametrizationsRequest(
                Address("", target_name="no_testutil"), description_of_origin="tests"
            )
        ],
    ).parametrizations
    assert len(result) == 1
    assert next(iter(result.keys())).generated_name == "pantsbuild.pants"
    pants_req = next(iter(result.values()))
    assert pants_req[PythonRequirementResolveField].value == "a"
