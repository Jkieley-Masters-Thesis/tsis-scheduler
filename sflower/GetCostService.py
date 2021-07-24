from decimal import Decimal

from sflower import AwsClient
from sflower import GlobalUtil


def get_all_cost_by_instance_type(instance_type):
    regions = AwsClient.get_regions()
    costs = {}
    for region in regions:
        region_name_short = region['RegionName']
        if 'us' not in region_name_short:
            continue
        region_name_full = GlobalUtil.get_region_full_name_by_key(region_name_short)
        try:
            cost = AwsClient.get_ec2_pricing_explicit(instance_type, region_name_full)
            costs[region_name_short] = Decimal(cost['USD'])
        except AssertionError as err:
            costs[region_name_short] = 'NA'
    return costs


def get_cost_group_by_values(instance_type):
    costs = get_all_cost_by_instance_type(instance_type)
    group_by = {}
    for key in costs.keys():
        value = costs[key]
        if value in group_by:
            group_by[value].append(key)
        else:
            group_by[value] = []
            group_by[value].append(key)
    group_by_list = list(group_by.items())
    group_by_list = sorted(group_by_list, key=lambda x: x[0])
    return group_by_list
