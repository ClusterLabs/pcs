from collections import defaultdict
from dataclasses import replace
from hashlib import sha1
from typing import Iterable, Optional, cast

from pcs.common.file_type_codes import FileTypeCode
from pcs.common.node_communicator import Communicator, RequestTarget
from pcs.common.reports import ReportItemContext
from pcs.common.reports.processor import ReportProcessor
from pcs.common.str_tools import format_list
from pcs.lib.communication.pcs_cfgsync import ConfigInfo, GetConfigs
from pcs.lib.communication.tools import run
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.interface.config import (
    FacadeInterface,
    ParserErrorException,
    SyncVersionFacadeInterface,
)

from .const import SYNCED_CONFIGS


class ConfigFetcher:
    def __init__(
        self, node_communicator: Communicator, report_processor: ReportProcessor
    ):
        self._node_communicator = node_communicator
        self._report_processor = report_processor

    def fetch(
        self,
        cluster_name: str,
        target_list: Iterable[RequestTarget],
        file_type_codes_to_fetch: Iterable[FileTypeCode] = SYNCED_CONFIGS,
    ) -> tuple[dict[FileTypeCode, SyncVersionFacadeInterface], bool]:
        """
        Downloads configs from all nodes in the cluster, and find the newest
        among them. Returns a dict containing facade with the newest config for
        each received config type, and a bool indicating whether we were able to
        download configs from the cluster.

        cluster_name -- name of the cluster
        target_list -- list of request targets
        file_type_codes_to_fetch -- list of wanted file type codes
        """
        if not set(file_type_codes_to_fetch) <= set(SYNCED_CONFIGS):
            raise AssertionError(
                f"This method only supports {format_list(list(SYNCED_CONFIGS))}"
            )

        cmd = GetConfigs(self._report_processor, cluster_name, False)
        cmd.set_targets(target_list)  # type: ignore
        received_configs = run(self._node_communicator, cmd)  # type: ignore

        configs_to_update = {}

        for file_type in file_type_codes_to_fetch:
            if file_type not in received_configs.config_files:
                continue

            instance = FileInstance.for_common(file_type)
            configs = self._parse_received_configs(
                instance, received_configs.config_files[file_type]
            )
            newest_config = _find_newest_config(instance, configs)
            if newest_config is None:
                continue

            if not instance.raw_file.exists():
                # if the file does not exist locally, but we received it from
                # other nodes, then we want to save the file locally as well
                configs_to_update[file_type] = newest_config
                continue

            local_config = self._parse_local_config(instance)
            if local_config is None:
                # We were unable to parse the local config for this file_type
                # and we can't compare the received configs with it. But we
                # might still be able to properly work with the remaining
                # config types
                continue

            if local_config.data_version < newest_config.data_version:
                configs_to_update[file_type] = newest_config
            elif local_config.data_version > newest_config.data_version:
                pass
            elif _file_hash(instance, local_config) != _file_hash(
                instance, newest_config
            ):
                configs_to_update[file_type] = newest_config

        return configs_to_update, received_configs.was_successful

    def _parse_local_config(
        self, file_instance: FileInstance
    ) -> Optional[SyncVersionFacadeInterface]:
        try:
            return cast(
                SyncVersionFacadeInterface, file_instance.read_to_facade()
            )
        except RawFileError as e:
            self._report_processor.report(raw_file_error_report(e))
        except ParserErrorException as e:
            self._report_processor.report_list(
                file_instance.parser_exception_to_report_list(e)
            )
        return None

    def _parse_received_configs(
        self, file_instance: FileInstance, raw_files: Iterable[ConfigInfo]
    ) -> list[SyncVersionFacadeInterface]:
        result = []
        for file in raw_files:
            try:
                facade = cast(
                    SyncVersionFacadeInterface,
                    file_instance.raw_to_facade(
                        file.cfg_content.encode("utf-8")
                    ),
                )
                result.append(facade)
            except ParserErrorException as e:
                # Add context, so we know from which node we received invalid
                # config
                context = ReportItemContext(node=file.cfg_origin)
                report_list = [
                    replace(report, context=context)
                    for report in file_instance.parser_exception_to_report_list(
                        e, is_forced_or_warning=True
                    )
                ]
                self._report_processor.report_list(report_list)
        return result


def _file_hash(file_instance: FileInstance, facade: FacadeInterface) -> str:
    # sha1 is used to be compatible with the old ruby implementation.
    # The hash is only used to compare and sort the files, not for security
    # reasons
    return sha1(
        file_instance.facade_to_raw(facade), usedforsecurity=False
    ).hexdigest()


def _find_newest_config(
    file_instance: FileInstance, configs: Iterable[SyncVersionFacadeInterface]
) -> Optional[SyncVersionFacadeInterface]:
    if not configs:
        return None

    max_version = max(cfg.data_version for cfg in configs)
    cfg_hash = {}
    hash_count: dict[str, int] = defaultdict(int)

    for cfg in configs:
        if cfg.data_version == max_version:
            file_hash = _file_hash(file_instance, cfg)
            cfg_hash[file_hash] = cfg
            hash_count[file_hash] += 1

    # find the biggest hash among hashes with the most frequent count, so that
    # this function always returns config with the same content when receiving
    # the same amount of different configs with the same version
    most_frequent_hash_count = max(hash_count.values())
    most_frequent_hash = max(
        h for h in hash_count if hash_count[h] == most_frequent_hash_count
    )

    return cfg_hash[most_frequent_hash]
