import json
from urllib.parse import unquote
from urllib.parse import quote
import http.client
import mimetypes


def get_cpu_usage(pod_name, start_time, end_time):
    conn = http.client.HTTPConnection("localhost", 9090)
    payload = ''
    headers = {}

    prometheus_query = 'sum by (container_name)(rate(container_cpu_usage_seconds_total{pod=~"%s", container_name=~".*", image!="", container_name!="POD", image!=""}[2m]))' % pod_name
    query = quote(prometheus_query) + '&start=' + str(start_time) + '&end=' + str(end_time) + '&step=4'

    conn.request("GET", "/api/v1/query_range?query=" + query, payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_string = data.decode("utf-8")
    json_parsed = json.loads(response_string)
    return json_parsed['data']['result'][0]['values']


def get_mem_usage(pod_name, start_time, end_time):
    conn = http.client.HTTPConnection("localhost", 9090)
    payload = ''
    headers = {}

    prometheus_query = 'avg by(container_name) (container_memory_working_set_bytes{pod=~"%s", container=~".*", container!="POD",container!="",image!=""})' % pod_name
    query = quote(prometheus_query) + '&start=' + str(start_time) + '&end=' + str(end_time) + '&step=4'

    conn.request("GET", "/api/v1/query_range?query=" + query, payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_string = data.decode("utf-8")
    json_parsed = json.loads(response_string)
    return json_parsed['data']['result'][0]['values']
