from unittest import mock, TestCase

from pcs_test.tools.misc import dict_to_modifiers

from pcs import status
from pcs.cli.common.errors import CmdLineInputError


@mock.patch("pcs.status.print")
class XmlStatus(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["status"])
        self.lib.status = mock.Mock(spec_set=["pacemaker_status_xml"])

    def _call_cmd(self, argv=None):
        status.xml_status(self.lib, argv or [], dict_to_modifiers({}))

    def test_success(self, mock_print):
        xml_status = """
            <xml>
                <pcmk status data />
            </xml>
        """
        self.lib.status.pacemaker_status_xml.return_value = xml_status
        self._call_cmd([])
        self.lib.status.pacemaker_status_xml.assert_called_once_with()
        mock_print.assert_called_once_with(xml_status.strip())

    def test_argv(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["x"])
        self.assertIsNone(cm.exception.message)
        mock_print.assert_not_called()
