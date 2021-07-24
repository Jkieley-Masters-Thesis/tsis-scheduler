import concurrent
import concurrent.futures
import json
import logging

import boto3

from sflower import DBClient


def flatten_list(spot_prices):
    final_list = []
    for spot_price in spot_prices:
        if type(spot_price) is list:
            final_list.extend(spot_price)
        elif type(spot_price) is dict:
            final_list.append(spot_price)
        else:
          logging.error("unknown type")
    return final_list


def get_cheapest_region_for_spot_instance(instance_types, product_description, run_id):
    '''
    Spawns a thread for each region. regions are dynamically populated from available regions
    :param instance_types: expects a single string ex: 't2.medium'
    :param product_description: expects a single string ex: 'Linux/UNIX (Amazon VPC)'
    :param run_id: to track the different runs (or times the process has been run to populate data in mongodb for analysis)
    :return:
    '''

    regions = get_regions() # regions are dynamically populated from available regions
    spot_prices = get_spot_instance_pricing(regions, instance_types, product_description, run_id)
    spot_prices = flatten_list(spot_prices)
    return spot_prices


def get_regions():
    '''
    regions are dynamically populated from available regions
    "Describes the Regions that are enabled for your account, or all Regions."
    https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeRegions.html
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_regions
    :return:
    '''
    ec2 = boto3.client('ec2')
    response = ec2.describe_regions()
    regions = response['Regions']
    logging.info('Regions:'+ json.dumps(regions))
    return regions

def get_spot_instance_pricing(regions, instance_types, product_description, run_id):
    '''
    Spawns a thread for each region
    :param regions: list of regions to pull pricing from
    :param instance_types: expects a single string ex: 't2.medium'
    :param product_description: expects a single string ex: 'Linux/UNIX (Amazon VPC)'
    :param run_id: to track the different runs (or times the process has been run to populate data in mongodb for analysis)
    :return:
    '''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_spot_instance_cheapest_by_region, region, instance_types, product_description, run_id)
                   for region in regions]
        results = [f.result() for f in futures]
        return results


def get_spot_instance_cheapest_by_region(region, instance_types, product_description, run_id):
    '''
    This will ping a specific region of spot instance pricing.

    Istance type is hardcoded to: 't2.medium',
    Product description is hardcoded to: 'Linux/UNIX (Amazon VPC)', # ex windows can come with additional license pricing

    :param client: the aws communiciation client
    :param region: the region to check pricing for
    :return:

    Array of availability zones with pricing, there can be many availalbility zones in a region.
    '''
    client = boto3.client(service_name='ec2', region_name=region['RegionName'])
    logging.info("fetching prices for region: " + region['RegionName'])
    response_list = []
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.describe_spot_price_history
    response = client.describe_spot_price_history(
        DryRun=False,
        InstanceTypes=[
            instance_types,
        ],
        ProductDescriptions=[
            'Linux/UNIX (Amazon VPC)',
        ],
    )

    # add addtionial meta data to make data analysis easier
    response['RegionName'] = region['RegionName']
    response['RunId'] = run_id

    logging.info(
        "len(response['SpotPriceHistory']): " + str(len(response['SpotPriceHistory'])) + " : region: " + region[
            'RegionName'])
    # logging.info("json: "+json.dumps(response, indent=4, sort_keys=True, default=str))

    if len(response['SpotPriceHistory']) == 0:
        # return response_list  # return an empty list
        return response  # return an empty list

    response_list.append(response)
    if response['NextToken']:
        # if there are more fetch those and add to the list res
        return get_spot_instance_next(response_list, response['NextToken'], client, instance_types, product_description)
    else:
        # otherwise return the current list
        # return response_list  # return an empty list
        return response_list  # return an empty list


def get_spot_instance_next(response_list, next_token, client, instance_types, product_description):
    response = client.describe_spot_price_history(
        DryRun=False,
        NextToken=next_token,
        InstanceTypes=[
            instance_types,
        ],
        ProductDescriptions=[
            product_description,
        ],
    )
    response_list.append(response)
    if response['NextToken']:
        return get_spot_instance_next(response_list, response['NextToken'], client)
    else:
        return response_list


def remove_keys_with_dots(price_json):
    new_json = {}
    for key in price_json.keys():
        new_key = key
        if "." in key:
            new_key = key.replace('.', '--')
        if type(price_json[key]) is dict:
            new_json[new_key] = remove_keys_with_dots(price_json[key])
        else:
            new_json[new_key] = price_json[key]
    return new_json


def get_ec2_availability_zones(region_name_short):
    ec2 = boto3.client('ec2', region_name=region_name_short)
    response = ec2.describe_availability_zones()
    zones_array = response['AvailabilityZones']
    zones_array = list(map(lambda x: x['ZoneName'], zones_array))
    return zones_array


def get_ec2_pricing_explicit(instance_type, region_name):
    client = boto3.client('pricing', region_name='us-east-1')
    filters = [
        {
            'Type': 'TERM_MATCH',
            'Field': 'productFamily',
            'Value': 'Compute Instance'
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'instanceType',
            'Value': instance_type
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'operatingSystem',
            'Value': 'Linux'
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'tenancy',
            'Value': 'Shared'
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'preInstalledSw',
            'Value': 'NA'
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'capacitystatus',
            'Value': 'Used'
        },
    ]
    response = client.get_products(ServiceCode='AmazonEC2', Filters=filters)
    prices = []
    for price in response['PriceList']:
        prices.append(json.loads(price))

    logging.info("fetched price list for: %s %s %s", instance_type, region_name, str(len(prices)))
    assert len(prices) == 1
    price = prices[0]

    price_per_unit = get_price_per_unit_from_product(price)

    return price_per_unit


def get_price_per_unit_from_product(price):
    on_demand = price['terms']['OnDemand']
    dyn_key1 = decend_one_key(on_demand)
    price_dimensions = dyn_key1['priceDimensions']
    price_data = decend_one_key(price_dimensions)
    price_per_unit = price_data['pricePerUnit']
    return price_per_unit


def decend_one_key(dict):
    keys = dict.keys()
    assert len(keys) == 1
    return dict[list(dict.keys())[0]]

def get_ec2_pricing(instance_type):
    client = boto3.client('pricing', region_name='us-east-1')
    filters = [
        {
            'Type': 'TERM_MATCH',
            'Field': 'productFamily',
            'Value': 'Compute Instance'
        },
        {
            'Type': 'TERM_MATCH',
            'Field': 'instanceType',
            'Value': instance_type
        },
    ]
    count = 0
    continueOn = True
    nextToken = None
    while continueOn:
        logging.info("looping through: instance_type: {%s}, count: {%s}", instance_type, count)
        count+=1
        if nextToken is None:
            response = get_products(client, filters)
        else:
            response = get_products(client, filters, response['NextToken'])
        # insert into db

        to_be_inserted = []
        for price in response['PriceList']:
            price_json = json.loads(price)
            mod_price_json = remove_keys_with_dots(price_json) # mongodb can't handle json keys with dots
            to_be_inserted.append({'price_json': mod_price_json})

        if len(response['PriceList']) > 0:
            insert_many_result = DBClient.insert_many("product_price_list", to_be_inserted)
            logging.info("insert_many_result: instance_type: {%s}, count: {%s}, result: {%s}",instance_type, count, insert_many_result)
        else:
            logging.info("given an empty price list: instance_type: {%s}, count: {%s}", instance_type, count)

        if 'NextToken' in response:
            logging.info("next token was found: " + str(len(response['NextToken'])))
            nextToken = response['NextToken']
        else:
            logging.info("next token was not found")
            continueOn = False

    return instance_type


def get_products(client, filters, nextToken=None):
    if nextToken is None:
        return client.get_products(ServiceCode='AmazonEC2', Filters=filters)
    else:
        return client.get_products(ServiceCode='AmazonEC2', Filters=filters, NextToken=nextToken)



def parsePricing(response):
    priceList = []
    if len(response['PriceList']) > 0:
        for i in response['PriceList']:
            priceItem = json.loads(i)
            priceList.append(priceItem)
    else:
        logging.info("PriceList was had no values to parse")
    return priceList


def get_all_instance_types():
    responses = get_attribute_values('instanceType')
    instanceTypes = []
    for response in responses:
        for value in response['AttributeValues']:
            instanceTypes.append(value['Value'])
    return instanceTypes

def get_attribute_values(attr_name, nextToken=None):
    responses = []
    client = boto3.client('pricing', region_name='us-east-1')

    get_attribute_values_(client, attr_name, responses)
    return responses


def get_attribute_values_(client, attr_name, responses, nextToken=None):
    response = None
    if nextToken is None:
        response = client.get_attribute_values(ServiceCode='AmazonEC2', AttributeName=attr_name)
    else:
        response = client.get_attribute_values(ServiceCode='AmazonEC2', AttributeName=attr_name, NextToken=nextToken)
    responses.append(response)

    if 'NextToken' in response:
        get_attribute_values_(client,attr_name, responses, response['NextToken'])
    else:
        return responses