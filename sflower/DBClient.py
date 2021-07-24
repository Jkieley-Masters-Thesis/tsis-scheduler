import json
import logging
import os
from bson.json_util import dumps
from decimal import Decimal

import pymongo


def insert_many(collection_name, insert_many):
    # insert fetched data to mongodb
    client = get_mongo_client()
    insert_response = client["thesis"][collection_name].insert_many(insert_many)
    insert_many_info = json.dumps({'acknowledged': insert_response.acknowledged})
    logging.info("inserting many into: collection_name:{%s}, insert response: {%s}", collection_name, insert_many_info)


def get_mongo_client():
    connection_str = os.environ["MONGO_CONNECTION_STR"]
    client = pymongo.MongoClient(connection_str)
    return client


def insert_one(collection_name, to_insert):
    client = get_mongo_client()
    insert_response = client["thesis"][collection_name].insert_one(to_insert)
    insert_many_info = json.dumps({'acknowledged': insert_response.acknowledged})
    logging.info("inserting one into: collection_name:{%s}, insert response: {%s}", collection_name, insert_many_info)
    return insert_response

def update_one(collection_name, query, values):
    client = get_mongo_client()
    update_reponse = client["thesis"][collection_name].update_one(query, {"$set": values})
    insert_many_info = json.dumps({'acknowledged': update_reponse.acknowledged})
    logging.info("inserting one into: collection_name:{%s}, insert response: {%s}", collection_name, insert_many_info)
    return update_reponse


def query_cheapest_region_by_instance(instance):
    query = [
      {"$match":{"price_json.product.attributes.instanceType":"m3.medium"}},
      {"$addFields":{"OnDemand":{"$objectToArray":"$price_json.terms.OnDemand"}}},
      {"$addFields":{"OnDemand":{"$arrayElemAt":["$OnDemand",0]}}},
      {"$addFields":{"OnDemand.v.priceDimensions":{"$objectToArray":"$OnDemand.v.priceDimensions"}}},
      {"$addFields":{"OnDemand.v.priceDimensions":{"$arrayElemAt":["$OnDemand.v.priceDimensions",0]}}},
      {"$addFields":{"convertedPrice":{"$toDecimal":"$OnDemand.v.priceDimensions.v.pricePerUnit.USD"}}},
      {"$project":{"_id":1,"convertedPrice":1,"location":"$price_json.product.attributes.location","instanceType":"$price_json.product.attributes.instanceType","operatingSystem":"$price_json.product.attributes.operatingSystem","tenancy":"$price_json.product.attributes.tenancy","capacitystatus":"$price_json.product.attributes.capacitystatus","preInstalledSw":"$price_json.product.attributes.preInstalledSw","description":"$OnDemand.v.priceDimensions.v.description"}},
      {"$sort":{"convertedPrice":1}},{"$match":{"convertedPrice":{"$ne":0}}},
      {"$match":{"convertedPrice":{"$ne":None}}},{"$match":{"tenancy":{"$ne":"Host"}}},
      {"$match":{"tenancy":{"$ne":"Dedicated"}}},{"$match":{"operatingSystem":{"$eq":"Linux"}}},
      {"$match":{"capacitystatus":{"$eq":"Used"}}},{"$match":{"preInstalledSw":{"$eq":"NA"}}}
    ]
    client = get_mongo_client()

    # force this to return a list instead of cusor, this will make the function only capabile of handling small data sizes
    docs = []
    cursor = client["thesis"]["product_price_list"].aggregate(query)
    for doc in cursor:
        docs.append(doc)

    # first in list will be the cheapest
    cheapest = docs[0]
    max_index = len(docs) - 1
    most_expensive = docs[max_index]
    savings = most_expensive['convertedPrice'].to_decimal() - cheapest['convertedPrice'].to_decimal()
    savings_percent = savings / cheapest['convertedPrice'].to_decimal()
    savings_str = str(savings)
    savings_percent_str = str(round(savings_percent * 100, 2))

    logging.info("querying product_price_list with aggregate query to get cheapest region by instance name")
    logging.info("cheapest: " + dumps(cheapest))
    logging.info("most expensive: "+dumps(most_expensive))

    logging.info("most expensive price: "+ to_decimal_to_str(most_expensive['convertedPrice']))
    logging.info("price chosen/cheapest: $/hr: "+ to_decimal_to_str(cheapest['convertedPrice']))
    logging.info("savings of $/hr:  " + savings_str)
    logging.info("savings of %:  " + savings_percent_str)

    to_record = {
        'mostExpensiveRef':most_expensive['_id'],
        'cheapestRef':cheapest['_id'],
        'mostExpensivePrice':most_expensive['convertedPrice'],
        'cheapestPrice': cheapest['convertedPrice'],
        'savings': savings_str,
        'savingsPercent': savings_percent_str,
        'region':cheapest['location']
    }

    insert_one('cheapest_region_by_instance_decision', to_record)

    return to_record['region'], docs, to_record

def to_decimal_to_str(value):
    return str(value.to_decimal())


def insert_one_codec(collection_name, to_insert, codec_options):
    client = get_mongo_client()
    col = client["thesis"].get_collection(collection_name, codec_options=codec_options)
    insert_response = col.insert_one(to_insert)
    insert_many_info = json.dumps({'acknowledged': insert_response.acknowledged})
    logging.info("inserting one into: collection_name:{%s}, insert response: {%s}", collection_name,insert_many_info)