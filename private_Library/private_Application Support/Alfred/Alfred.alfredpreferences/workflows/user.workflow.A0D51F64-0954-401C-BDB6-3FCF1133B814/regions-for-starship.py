# -*- coding: utf-8 -*-

from __future__ import print_function

import regions

print("[aws.region_aliases]")
for region in regions.regions:
    print('%s = "%s %s"' % (
        region.short_name,
        region.flag,
        region.airport_code
    ))
