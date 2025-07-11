#!/usr/bin/python
# encoding: utf-8

"""
Alfred Workflow script to look up service regions and long names
"""

import sys
from typing import TYPE_CHECKING, List, Optional, Text, cast

from isengard import check_valid_mwinit, using_isengardcli
from regions import find_region, region_to_airport_code, region_to_longname
from workflow import (
    ICON_ERROR,
    MATCH_ATOM,
    MATCH_STARTSWITH,
    MATCH_SUBSTRING,
    Workflow3,
)

if TYPE_CHECKING:
    from regions import Region

ONE_DAY = 86400
ONE_MONTH = ONE_DAY * 30

SUBCOMMANDS = {
    "region": "Check regional support for %s",
    "longname": "See long name for %s",
}


def main(workflow):  # type: (Workflow3) -> None
    # imports and functions defined in here so they get wrapped and support from Workflow
    import boto3

    # region doesn't matter but this saves the user having to specify in their profile
    ssm = boto3.client("ssm", region_name="us-east-1")
    paginator = ssm.get_paginator("get_parameters_by_path")

    def get_services():  # type: () -> List[str]
        """Get a list of all service names"""
        response = paginator.paginate(
            Path="/aws/service/global-infrastructure/services"
        )
        services = []  # type: List[str]
        for page in response:
            services.extend([x["Value"] for x in page["Parameters"]])
        return services

    def get_service_regions(service):  # type: (str) -> List[str]
        """Get a list of region names for a service"""
        response = paginator.paginate(
            Path="/aws/service/global-infrastructure/services/%s/regions" % service
        )
        regions = []  # type: List[str]
        for page in response:
            regions.extend([x["Value"] for x in page["Parameters"]])
        return regions

    def get_service_longname(service):  # type: (str) -> Optional[str]
        """Get the longName for a service"""
        try:
            response = ssm.get_parameter(
                Name="/aws/service/global-infrastructure/services/%s/longName" % service
            )
            return response["Parameter"]["Value"]
        except Exception:
            return None

    def do_regions(service, check_region):  # type (str, Optional[str]) -> None
        """Populate the workflow with regions for a service"""
        if service in all_services:
            regions_for_service = workflow.cached_data(
                "regions-%s" % service, max_age=ONE_DAY
            )
            if regions_for_service is None:
                regions_for_service = get_service_regions(service)
                workflow.cache_data("regions-%s" % service, regions_for_service)
            service_name = workflow.cached_data(
                "service-name-%s" % service, max_age=ONE_MONTH
            )
            if service_name is None:
                service_name = get_service_longname(service)
                if service_name:
                    workflow.cache_data("service-name-%s" % service, service_name)
            if check_region is not None:
                matched_regions_for_service = set(
                    workflow.filter(
                        check_region,
                        regions_for_service,
                        match_on=MATCH_STARTSWITH | MATCH_SUBSTRING,
                    )
                )
                matched_regions_for_service |= set(
                    workflow.filter(
                        check_region,
                        regions_for_service,
                        key=lambda x: region_to_airport_code(x),
                        match_on=MATCH_ATOM,
                    )
                )
                matched_regions_for_service |= set(
                    workflow.filter(
                        check_region,
                        regions_for_service,
                        key=lambda x: region_to_longname(x),
                        match_on=MATCH_STARTSWITH | MATCH_ATOM | MATCH_SUBSTRING,
                    )
                )
                if len(matched_regions_for_service) == 0:
                    workflow.add_item(
                        "Not available in %s" % check_region, icon=ICON_ERROR
                    )
            else:
                matched_regions_for_service = regions_for_service
            for region in matched_regions_for_service:
                _region_info = find_region(region)  # type: List[Region]
                if len(_region_info) == 1:
                    region_info = unicode(_region_info[0])  # type: Text
                    flag = _region_info[0].flag
                    region_name = _region_info[0].long_name
                    largetext = "%s is available in %s %s" % (
                        service,
                        flag,
                        region_name,
                    )
                else:
                    region_info = u""
                    largetext = None
                workflow.add_item(region, subtitle=region_info, largetext=largetext)

    def do_subcommands(service, fragment=""):  # type: (str, str) -> None
        """Populate the workflow with available subcommands for the service"""
        commands = workflow.filter(fragment, SUBCOMMANDS.keys())
        for command in commands:
            text = SUBCOMMANDS[command]
            workflow.add_item(
                command,
                subtitle=text % service,
                autocomplete="%s %s" % (service, command),
                valid=False,
            )

    all_services = cast(
        List[str], workflow.cached_data("all_services", get_services, max_age=ONE_DAY)
    )

    args = workflow.args[0].split(" ")
    if len(args) == 1:
        # entering a service name
        items = workflow.filter(args[0], all_services)
        if not items:
            workflow.add_item("Oh no, no services match :(")
        elif len(items) == 1 and args[0] == items[0]:
            # exactly one service matches, offer subcommands for it
            do_subcommands(args[0])
        else:
            for item in items:
                workflow.add_item(item, autocomplete=item)
        workflow.send_feedback()
        return

    if len(args) >= 2:
        # entering a service name and subcommand
        service = args[0]
        command = args[1]
        if command == "region":
            if len(args) == 3:
                region = args[2]
            else:
                region = None
            do_regions(service, region)
        elif command == "longname":
            longname = get_service_longname(service)
            if longname is None:
                workflow.warn_empty(
                    "no idea sorry",
                    subtitle="probably Systems Manager %s Manager"
                    % service.capitalize(),
                    icon=ICON_ERROR,
                )
            else:
                workflow.add_item(
                    longname,
                    subtitle=u"Long service name for %s (⌘C to copy)" % service,
                    copytext=longname,
                    largetext=longname,
                )
        else:
            do_subcommands(service, command)
        workflow.send_feedback()
        return


if __name__ == "__main__":
    wf = Workflow3(libraries=["./lib"])
    if using_isengardcli():
        if not check_valid_mwinit():
            wf.warn_empty(
                "mwinit cookie expired or not present",
                subtitle="ISENGARDCLI_PATH is set but looks like you need to run mwinit in a term first",
            )
            wf.send_feedback()
            sys.exit(0)
    sys.exit(wf.run(main))
