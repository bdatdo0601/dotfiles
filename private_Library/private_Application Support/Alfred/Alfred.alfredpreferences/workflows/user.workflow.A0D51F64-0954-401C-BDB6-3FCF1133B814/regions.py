# -*- coding: utf-8 -*-
"""
Region lookup utilities
"""

from typing import List, Text


class Region:
    """Represent an AWS Region"""

    def __init__(
        self, airport_code, short_name, long_name, flag
    ):  # type: (str, str, str, Text) -> None
        self.airport_code = airport_code
        self.short_name = short_name
        self.long_name = long_name
        self.flag = flag

        # calculate these in advance
        self._airport_code_lower = airport_code.lower()
        self._short_name_lower = short_name.lower()
        self._long_name_lower = long_name.lower()

    def __unicode__(self):  # type: () -> Text
        result = []  # type: List[Text]
        result.append(self.long_name)
        result.append(self.flag)
        if self.airport_code:
            result.append("(%s)" % self.airport_code)
        return " ".join(result)


# although this information is available via
# ssm:/aws/service/global-infrastructure/regions/$region, that doesn't include the
# airport code or (obviously) the emoji
regions = []  # type: List[Region]
regions.append(Region("LHR", "eu-west-2", "Europe (London)", u"🇬🇧"))
regions.append(Region("DUB", "eu-west-1", "Europe (Dublin)", u"🇮🇪"))
regions.append(Region("CPT", "af-south-1", "Africa (Cape Town)", u"🇿🇦"))
regions.append(Region("KIX", "ap-northeast-3", "Asia Pacific (Osaka-Local)", u"🇯🇵"))
regions.append(Region("YUL", "ca-central-1", "Canada (Central)", u"🇨🇦"))
regions.append(Region("BJS", "cn-north-1", "China (Beijing)", u"🇨🇳"))
regions.append(Region("ZHY", "cn-northwest-1", "China (Ningxia)", u"🇨🇳"))
regions.append(Region("FHR", "eu-central-1", "Europe (Frankfurt)", u"🇩🇪"))
regions.append(Region("MXP", "eu-south-1", "Europe (Milan)", u"🇮🇹"))
regions.append(Region("GRU", "sa-east-1", "South America (Sao Paulo)", u"🇧🇷"))
regions.append(Region("HKG", "ap-east-1", "Asia Pacific (Hong Kong)", u"🇭🇰"))
regions.append(Region("NRT", "ap-northeast-1", "Asia Pacific (Tokyo)", u"🇯🇵"))
regions.append(Region("BOM", "ap-south-1", "Asia Pacific (Mumbai)", u"🇮🇳"))
regions.append(Region("ARN", "eu-north-1", "Europe (Stockholm)", u"🇸🇪"))
regions.append(Region("BAH", "me-south-1", "Middle East (Bahrain)", u"🇧🇭"))
regions.append(Region("IAD", "us-east-1", "US East (N. Virginia)", u"🇺🇸"))
regions.append(Region("CMH", "us-east-2", "US East (Ohio)", u"🇺🇸"))
regions.append(Region("PDT", "us-gov-west-1", "AWS GovCloud (US-West)", u"🕵️‍♀️"))
regions.append(Region("PDX", "us-west-1", "US West (Oregon)", u"🇺🇸"))
regions.append(Region("SFO", "us-west-2", "US West (N. California)", u"🇺🇸"))
regions.append(Region("ICN", "ap-northeast-2", "Asia Pacific (Seoul)", u"🇰🇷"))
regions.append(Region("SIN", "ap-southeast-1", "Asia Pacifia (Singapore)", u"🇸🇬"))
regions.append(Region("CDG", "eu-west-3", "Europe (Paris)", u"🇫🇷"))
regions.append(Region("OSU", "us-gov-east-1", "AWS GovCloud (US-East)", u"🕵️‍♀️"))
regions.append(Region("SYD", "ap-southeast-2", "Asia Pacific (Sydney)", u"🇦🇺"))

_region_short_name_to_airport_code = {x.short_name: x.airport_code for x in regions}
_region_short_name_to_long_name = {x.short_name: x.long_name for x in regions}


def region_match(search_text):  # type: (str) -> bool
    """Convenience method to check if there's a match against the search text"""
    return len(find_region(search_text)) > 0


def find_region(search_text):  # type: (str) -> List[Region]
    """Return a list of Regions where any field substring-matches the search text"""
    results = []  # type: List[Region]
    search_text = search_text.lower()
    for region in regions:
        if (
            search_text in region._airport_code_lower
            or search_text in region._short_name_lower
            or search_text in region._long_name_lower
        ):
            results.append(region)
    return results


def region_to_airport_code(region):  # type: (str) -> str
    """Convert a short region name into an airport code"""
    return _region_short_name_to_airport_code[region]


def region_to_longname(region):  # type: (str) -> str
    """Convert a short region name into a long region name"""
    return _region_short_name_to_long_name[region]
