from pcs.common import reports

from pcs_test.tools import fixture


class CrmAttributeLoadMetadataMixin:
    def load_fake_agent_metadata(self):
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata()


class CrmAttributeMetadataErrorMixin:
    _load_cib_when_metadata_error = None

    def metadata_error_command(self):
        raise NotImplementedError

    def _metadata_error(
        self,
        agent="cluster-options",
        stdout=None,
        stderr="",
        reason=None,
        returncode=2,
        unsupported_version=False,
    ):
        if self._load_cib_when_metadata_error:
            self.config.runner.cib.load()
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name=agent,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )
        self.env_assist.assert_raise_library_error(self.metadata_error_command)
        if unsupported_version:
            report = fixture.error(
                reports.codes.AGENT_IMPLEMENTS_UNSUPPORTED_OCF_VERSION,
                agent=f"__pcmk_internal:{agent}",
                ocf_version="5.2",
                supported_versions=["1.0", "1.1"],
            )
        else:
            report = fixture.error(
                reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                agent=agent,
                reason="error" if reason is None else reason,
            )
        self.env_assist.assert_reports([report])

    def test_metadata_error_returncode(self):
        stdout = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <status code="2" message="ERROR" />
            </pacemaker-result>
        """
        self._metadata_error(stdout=stdout, reason="ERROR")

    def test_metadata_error_xml_syntax_error(self):
        stdout = "not an xml"
        stderr = "syntax error"
        self._metadata_error(
            stdout=stdout, stderr=stderr, reason=f"{stderr}\n{stdout}"
        )

    def test_metadata_error_invalid_schema(self):
        stdout = "<xml/>"
        stderr = "invalid schema"
        self._metadata_error(
            stdout=stdout, stderr=stderr, reason=f"{stderr}\n{stdout}"
        )

    def test_metadata_error_invalid_version(self):
        stdout = """
            <pacemaker-result api-version="2.38" request="crm_attribute">
                <resource-agent name="cluster-options">
                    <version>5.2</version>
                    <parameters>
                        <parameter name="parameter-name" advanced="0"
                                generated="0">
                            <longdesc lang="en">longdesc</longdesc>
                            <shortdesc lang="en">shortdesc</shortdesc>
                            <content type="string"/>
                        </parameter>
                    </parameters>
                </resource-agent>
                <status code="0" message="OK" />
            </pacemaker-result>
        """
        self._metadata_error(
            stdout=stdout, returncode=0, unsupported_version=True
        )

    def test_facade_crm_attribute_metadata_not_supported(self):
        if self._load_cib_when_metadata_error:
            self.config.runner.cib.load()
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=False
        )
        self.env_assist.assert_raise_library_error(self.metadata_error_command)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CLUSTER_OPTIONS_METADATA_NOT_SUPPORTED
                )
            ]
        )
