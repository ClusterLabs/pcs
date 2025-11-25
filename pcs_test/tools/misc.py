import logging
import os
import re
import tempfile
from functools import lru_cache
from unittest import (
    mock,
    skipUnless,
)

from lxml import etree

from pcs import settings
from pcs.cli.common.parse_args import InputModifiers
from pcs.common import str_tools
from pcs.lib.external import CommandRunner

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None  # type: ignore

from pcs_test import TEST_ROOT
from pcs_test import settings as tests_settings
from pcs_test.tools.custom_mock import MockLibraryReportProcessor

runner = CommandRunner(
    mock.MagicMock(logging.Logger), MockLibraryReportProcessor(), os.environ
)


class ParametrizedTestMetaClass(type):
    """
    Example:
        class GeneralTest(TestCase):
            attr = None
            def _test_1(self):
                self.assertIn(self.attr, [1, 2])

            def _test_2(self):
                self.assertNotIn(self.attr, [0, 3, 4, 5])

        class Test1(GeneralTest, metaclass=ParametrizedTestMetaClass):
            attr = 1

        class Test2(GeneralTest, metaclass=ParametrizedTestMetaClass):
            attr = 2

        class Test3(GeneralTest, metaclass=ParametrizedTestMetaClass):
            # This should fail
            attr = 3
    """

    def __init__(cls, classname, bases, class_dict):
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if attr_name.startswith("_test") and callable(attr):
                setattr(cls, attr_name[1:], attr)

        super().__init__(classname, bases, class_dict)


def dict_to_modifiers(options):
    def _convert_val(val):
        if val is True:
            return ""
        return val

    return InputModifiers(
        {
            f"--{opt}": _convert_val(val)
            for opt, val in options.items()
            if val is not False
        }
    )


def get_test_resource(name):
    """Return full path to a test resource file specified by name"""
    return os.path.join(TEST_ROOT, "resources", name)


def get_tmp_dir(name=None):
    """Create a temp directory with a unique name in our test dir"""
    tmp_dir = get_test_resource("temp")
    os.makedirs(tmp_dir, exist_ok=True)
    return tempfile.TemporaryDirectory(
        suffix=".tmp",  # for .gitignore
        prefix=(f"{name}." if name else None),
        dir=tmp_dir,
    )


def get_tmp_file(name=None, mode="w+"):
    """Create a temp file with a unique name in our test dir"""
    tmp_dir = get_test_resource("temp")
    os.makedirs(tmp_dir, exist_ok=True)
    return tempfile.NamedTemporaryFile(
        mode=mode,
        suffix=".tmp",  # for .gitignore
        prefix=(f"{name}." if name else None),
        dir=tmp_dir,
    )


def write_data_to_tmpfile(data, tmp_file):
    tmp_file.seek(0)
    tmp_file.truncate()
    tmp_file.write(data)
    tmp_file.flush()
    tmp_file.seek(0)


def write_file_to_tmpfile(source_file_path, tmp_file):
    with open(source_file_path) as source:
        write_data_to_tmpfile(source.read(), tmp_file)


def read_test_resource(name):
    with open(get_test_resource(name)) as a_file:
        return a_file.read()


def cmp3(a, b):
    # pylint: disable=invalid-name

    # python3 doesn't have the cmp function, this is an official workaround
    # https://docs.python.org/3.0/whatsnew/3.0.html#ordering-comparisons
    return (a > b) - (a < b)


def compare_version(a, b):
    # pylint: disable=invalid-name
    if a[0] == b[0]:
        if a[1] == b[1]:
            return cmp3(a[2], b[2])
        return cmp3(a[1], b[1])
    return cmp3(a[0], b[0])


def is_minimum_pacemaker_version(major, minor, rev):
    return _is_version_sufficient(
        _get_current_pacemaker_version(), (major, minor, rev)
    )


@lru_cache()
def _get_current_pacemaker_version():
    output, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_mon_exec, "--version"]
    )
    pacemaker_version = output.split("\n", maxsplit=1)[0]
    regexp = re.compile(r"Pacemaker (\d+)\.(\d+)\.(\d+)")
    match = regexp.match(pacemaker_version)
    major = int(match.group(1))
    minor = int(match.group(2))
    rev = int(match.group(3))
    return major, minor, rev


@lru_cache()
def _get_current_cib_schema_version():
    regexp = re.compile(r"pacemaker-((\d+)\.(\d+))")
    all_versions = set()
    xml = etree.parse(tests_settings.pacemaker_version_rng).getroot()
    for value_el in xml.xpath(
        ".//x:attribute[@name='validate-with']//x:value",
        namespaces={"x": "http://relaxng.org/ns/structure/1.0"},
    ):
        match = re.match(regexp, value_el.text)
        if match:
            all_versions.add((int(match.group(2)), int(match.group(3))))
    return sorted(all_versions)[-1]


def is_minimum_cib_schema_version(cmajor, cminor, crev):
    major, minor = _get_current_cib_schema_version()
    return compare_version((major, minor, 0), (cmajor, cminor, crev)) > -1


def _is_version_sufficient(current_version, minimal_version):
    return compare_version(current_version, minimal_version) > -1


def _format_version(version_tuple):
    return ".".join([str(x) for x in version_tuple])


def is_minimum_pacemaker_features(cmajor, cminor, crev):
    major, minor, rev = _get_current_pacemaker_features()[0]
    return compare_version((major, minor, rev), (cmajor, cminor, crev)) > -1


def _has_pacemaker_features(requested_features):
    requested = frozenset(requested_features)
    actual = _get_current_pacemaker_features()[1]
    return actual >= requested


@lru_cache()
def _get_current_pacemaker_features():
    output, dummy_stderr, dummy_retval = runner.run(
        [settings.pacemakerd_exec, "--features"]
    )
    features_string = output.split("\n")[1]
    regexp = re.compile(r"Supporting v(\d+)\.(\d+)\.(\d+):\s*(.*)")
    match = regexp.search(features_string)
    major = int(match.group(1))
    minor = int(match.group(2))
    rev = int(match.group(3))
    features_list = frozenset(match.group(4).split())
    return (major, minor, rev), features_list


@lru_cache()
def is_pacemaker_21_without_20_compatibility():
    return is_minimum_pacemaker_version(
        2, 1, 0
    ) and not _has_pacemaker_features(["compat-2.0"])


def skip_unless_pacemaker_version(version_tuple, feature):
    current_version = _get_current_pacemaker_version()
    return skipUnless(
        _is_version_sufficient(current_version, version_tuple),
        (
            "Pacemaker version is too old (current: {current_version},"
            " must be >= {minimal_version}) to test {feature}"
        ).format(
            current_version=_format_version(current_version),
            minimal_version=_format_version(version_tuple),
            feature=feature,
        ),
    )


def skip_unless_pacemaker_features(version_tuple, feature):
    return skipUnless(
        is_minimum_pacemaker_features(*version_tuple),
        (
            "Pacemaker must support feature set version {version} to test "
            "{feature}"
        ).format(version=_format_version(version_tuple), feature=feature),
    )


def skip_unless_cib_schema_version(version_tuple, feature):
    current_version = _get_current_cib_schema_version()
    return skipUnless(
        is_minimum_cib_schema_version(*version_tuple),
        (
            "Pacemaker supported CIB schema version is too low (current: "
            "{current_version}, must be >= {minimal_version}) to test {feature}"
        ).format(
            current_version=_format_version(current_version),
            minimal_version=_format_version(version_tuple),
            feature=feature,
        ),
    )


def skip_unless_crm_rule():
    return skip_unless_pacemaker_version(
        (2, 0, 2), "listing of constraints that might be expired"
    )


def skip_unless_pacemaker_supports_rsc_and_op_rules():
    return skip_unless_cib_schema_version(
        (3, 4, 0), "rsc_expression and op_expression elements in rule elements"
    )


def skip_unless_pacemaker_supports_op_onfail_demote():
    return skip_unless_cib_schema_version(
        (3, 4, 0), "resource operations with 'on-fail' option set to 'demote'"
    )


def skip_unless_root():
    return skipUnless(os.getuid() == 0, "Root user required")


@lru_cache()
def _is_booth_resource_agent_installed():
    output, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_resource_exec, "--list-agents", "ocf:pacemaker"]
    )
    return "booth-site" in output


def skip_unless_booth_resource_agent_installed():
    return skipUnless(
        _is_booth_resource_agent_installed(),
        "test requires resource agent ocf:pacemaker:booth-site"
        " which is not installed",
    )


def skip_unless_webui_installed():
    return skipUnless(webui, "test requires webui which is not installed")


def create_patcher(target_prefix_or_module):
    """
    Return function for patching tests with preconfigured target prefix
    string|module target_prefix_or_module could be:
        * a prefix for patched names. Typically tested module:
            "pcs.lib.commands.booth"
        * a (imported) module: pcs.lib.cib
        Between prefix and target is "." (dot)
    """
    prefix = target_prefix_or_module
    if not isinstance(target_prefix_or_module, str):
        prefix = target_prefix_or_module.__name__

    def patch(target, *args, **kwargs):
        return mock.patch("{0}.{1}".format(prefix, target), *args, **kwargs)

    return patch


def outdent(text):
    return "\n".join(str_tools.outdent(text.splitlines()))


def create_setup_patch_mixin(module_specification_or_patcher):
    """
    Configure and return SetupPatchMixin

    SetupPatchMixin add method 'setup_patch' to a test case.

    Method setup_patch takes name that should be patched in destination module
    (see module_specification_or_patcher). Method provide cleanup after test.
    It is expected to be used in 'setUp' method but should work inside test as
    well.

    string|callable module_specification_or_patcher can be
       * callable patcher created via create_patcher:
         create_patcher("pcs.lib.cib")
       * name of module: "pcs.lib.cib"
       * (imported) module: pcs.lib.cib
         Note that this must be not a callable (can be done via
         sys.modules[__name__] = something_callable. If is a callable use name
         of the module instead.
    """
    if callable(module_specification_or_patcher):
        patch_module = module_specification_or_patcher
    else:
        patch_module = create_patcher(module_specification_or_patcher)

    class SetupPatchMixin:
        def setup_patch(self, target_suffix, *args, **kwargs):
            patcher = patch_module(target_suffix, *args, **kwargs)
            self.addCleanup(patcher.stop)
            return patcher.start()

    return SetupPatchMixin


class PacemakerFeatures:
    @staticmethod
    def stonith_renamed_to_fencing():
        return is_minimum_pacemaker_features(3, 20, 5)

    @staticmethod
    def skip_unless_stonith_renamed_to_fencing():
        return skip_unless_pacemaker_features(
            (3, 20, 5),
            "cluster properties 'stonith-*' renamed to 'fencing-*'",
        )
