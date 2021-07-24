import ftplib
import json
import logging
import os
import sys
import tempfile
import time
from decimal import Decimal

import boto3 as boto3
import kubernetes

from pclusterutils import ExecuteUtil
from sflower import KubeService


def get():
    return None


def get_minikube_config():
    configuration = kubernetes.client.Configuration()
    configuration.ssl_ca_cert = "/Users/james_kieley/.minikube/ca.crt"
    minikube_ip = "192.168.99.106"
    configuration.host = "https://" + minikube_ip + ":8443"
    configuration.cert_file = "/Users/james_kieley/.minikube/client.crt"
    configuration.key_file = "/Users/james_kieley/.minikube/client.key"
    configuration.debug = True
    api_client = kubernetes.client.ApiClient(configuration)
    api_instance = kubernetes.client.BatchV1Api(api_client)
    return api_instance


def log_job_status(event):
    status_dict = vars(event['object'].status)
    del status_dict['_conditions']
    json_string = json.dumps(status_dict, indent=4, sort_keys=True, default=str)
    logging.info(json_string)


def is_job_complete(event):
    status_is_not_succeeded = event['object'].status.succeeded is None
    status_is_not_failed = event['object'].status.failed is None
    if status_is_not_succeeded and status_is_not_failed:
        return False
    else:
        return True


def get_job_execution_time(event):
    start_time = event['object'].status.start_time
    finish_time = event['object'].status.completion_time
    execution_time = finish_time - start_time
    logging.info("Job Executed in: " + str(execution_time))
    return execution_time


def create_record():
    pass


def wait_until_job_is_complete(inputFileByteSize):
    '''
    Right now this function waits for 'a' job to complete does not handle multiple jobs running at once, this may be a
    future need
    :return:
    '''
    api_instance = KubeService.get_minikube_config()
    wait_until_job_is_complete_with_api_instance(api_instance, inputFileByteSize)


def is_the_job_were_looking_for(event, config):
    # get job labels
    # compare job labels against some config input
    logging.info("compare job labels against config")
    for key, value in event['object'].metadata.labels.items():
        logging.info(f'Checking key value combination: key:{key}, value:{value}, match-key:{config["job"]["job-label-match-key"]}, match-value:{config["job"]["job-label-match-value"]}')
        if key == config['job']['job-label-match-key'] and value == config['job']['job-label-match-value']:
            logging.info("keys and values match: return True")
            return True
    logging.info("No keys and values matched: return False")
    return False


def wait_until_job_is_complete_with_api_instance(api_instance, config):
    '''
    :param api_instance:
    :param inputFileByteSize:
    :return: completion_stats
    | {
    |    'executionTime': 'How long did the job execute in a readable time string ex: 0:02:05',
    |    'executionTimeSec': 'How long did the job execute number of seconds in MongoInteger NumberInt',
    |    'startTime': 'job start time from kubernetes job description in ISODate ex: ISODate("2020-08-29T03:43:50.000+0000")',
    |    'endTime': 'job finish time from kubernetes job description in ISODate ex: ISODate("2020-08-29T03:43:50.000+0000")',
    |    'inputFileByteSize': 'Number of bytes for the input file'
    | }
    '''
    w = kubernetes.watch.Watch()

    while True:
        try:
            logging.info("initiate stream watch")
            #coulddo: instead of looking at all jobs, lets look at a job based on a selector
            # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/BatchV1Api.md#list_namespaced_job
            #
            for event in w.stream(api_instance.list_job_for_all_namespaces, _request_timeout=600):
                if event['type'] == 'ADDED':
                    logging.info("Known Event: %s %s" % (event['type'], event['object'].metadata.name))
                    log_job_status(event)
                elif event['type'] == 'MODIFIED':
                    logging.info("Known Event: %s %s" % (event['type'], event['object'].metadata.name))
                    log_job_status(event)
                    if is_job_complete(event) and is_the_job_were_looking_for(event, config):
                        logging.info("job is COMPLETE")
                        execution_time = get_job_execution_time(event)
                        start_time = event['object'].status.start_time
                        finish_time = event['object'].status.completion_time
                        # other attributes to be tracked: AWSRegion, AWSAvailabilityZone, region/availabilityzone cost
                        # decision record (why was this region/az chosen?) show max/min prices
                        return {
                            'executionTime': str(execution_time),
                            'executionTimeSec': execution_time.seconds,
                            'startTime': start_time,
                            'endTime': finish_time
                        }
                    else:
                        logging.info("job is not complete")
                else:
                    logging.info("Unknown Event: %s %s" % (event['type'], event['object'].metadata.name))
                    log_job_status(event)
        except:
            logging.info("Unexpected error:", sys.exc_info())


def get_byte_size(input_csv_file):
    file_stats = os.stat(input_csv_file)
    num_of_bytes = file_stats.st_size
    return num_of_bytes


def increase_csv_file_size(input_csv_file, multiple_factor):
    with open(input_csv_file, "r") as input_file:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as output_file:
            for i, line in enumerate(input_file.readlines()):
                if i == 0:
                    output_file.write(line)  # we only want to output the header line once
                else:
                    for j in range(multiple_factor):
                        output_file.write(line)
            logging.info("output file complete path: {" + output_file.name + "}")
            return output_file.name


def upload_file_to_ftp(file_path, file_name):
    session = get_ftp_session()
    file = open(file_path, 'rb')  # file to send
    session.storbinary('STOR ' + file_name, file)  # send the file
    file.close()  # close file and FTP
    session.quit()


def get_ftp_session():
    ftp = ftplib.FTP()
    ftp.connect('127.0.0.1', 2121)
    ftp.login('admin', 'admin')
    session = ftp
    return session


def download_from_ftp(ftp_file_name, download_dir):
    ftp = get_ftp_session()
    ftp.retrbinary("RETR " + ftp_file_name, open(download_dir + '/' + ftp_file_name, 'wb').write)
    ftp.quit()


def setEnv(param, value):
    os.environ[param] = value
    logging.info("Setting Environment Variable: %s to value: %s", param, value)


def logEnv(param):
    logging.info("Environment Variable: %s has value: %s", param, os.environ[param])


def check_set_env(param, reason):
    if param in os.environ:
        logging.info("Environment Variable has been checked and set: %s", param)
        logEnv(param)
    else:
        raise ValueError("Expected the following Environment variable to be set, but it is not: %s, it is used for: %s",
                         param, reason)


def wait_until_cluster_ready(start, sleep_interval, check_count):
    is_ready_phase = "Your cluster " + os.environ["NAME"] + " is ready"

    for x in range(check_count):
        time.sleep(sleep_interval)
        logging.info('checking for the nth time: ' + str(x))
        output = ExecuteUtil.execute("kops validate cluster")
        term_is_present = is_ready_phase in output
        logging.info('term_is_present: ' + str(term_is_present))
        if term_is_present:
            logging.info('triggered')
            break
    end = time.time()
    logging.info('Total Execution time: ' + str(end - start))


def get_public_ip_of_single_node(region_name):
    client = boto3.client(service_name='ec2', region_name=region_name)
    response = client.describe_instances()
    instances = map(lambda x: x['Instances'], response['Reservations'], )
    flat_instances = [item for sublist in instances for item in sublist]
    node = next(obj for obj in flat_instances if 'nodes' in obj['SecurityGroups'][0]['GroupName'])
    return node['PublicIpAddress']


def get_region_full_name_by_key(region_lookup_key):
    # todo: set REGIONS_FILE in circleci build
    region_file = os.environ['REGIONS_FILE']
    region_map = {}
    with open(region_file, 'r') as file:
        for line in file:
            pieces = line.split('\t')
            region_full_name = pieces[0]
            region_key = pieces[1].replace('\n', '')
            region_map[region_key] = region_full_name
    region_full_name = region_map[region_lookup_key]
    return region_full_name


def covert_dec_to_dec128(final_insert):
    return None


def get_decimal_codec_options():
    # customized bson encoding to deal with custom types, I knew this was here!
    # https://api.mongodb.com/python/current/examples/custom_type.html#custom-type-type-registry
    from bson.decimal128 import Decimal128
    from bson.codec_options import TypeCodec
    class DecimalCodec(TypeCodec):
        python_type = Decimal  # the Python type acted upon by this type codec
        bson_type = Decimal128  # the BSON type acted upon by this type codec

        def transform_python(self, value):
            """Function that transforms a custom type value into a type
            that BSON can encode."""
            return Decimal128(value)

        def transform_bson(self, value):
            """Function that transforms a vanilla BSON type value into our
            custom type."""
            return value.to_decimal()

    decimal_codec = DecimalCodec()
    from bson.codec_options import TypeRegistry
    type_registry = TypeRegistry([decimal_codec])
    from bson.codec_options import CodecOptions
    codec_options = CodecOptions(type_registry=type_registry)
    return codec_options


def generate_new_input_file_by_multiple(input_csv_file, multiple_factor):
    input_file_byte_size = get_byte_size(input_csv_file)
    logging.info("file size before: %s", input_file_byte_size)
    generated_input_file = increase_csv_file_size(input_csv_file, multiple_factor)
    input_file_byte_size = get_byte_size(generated_input_file)
    logging.info("file size after: %s", input_file_byte_size)
    return generated_input_file, input_file_byte_size


def upload_file_via_scp(config,input_file, local_file, ftp_file_name,run_id):
    '''
    What does this function do?
    1. uploads the given file to the given server via the scp protocal
    '''
    remote_path = input_file['remote-file-path'].replace('{run_id}', str(run_id)) + ftp_file_name
    input_file['remote-file-path-full'] = config['remote-mount-dir'] + ftp_file_name
    execution_string = 'scp -i "%s" "%s" "%s@%s:%s"' % (
        config['remote-host-key'], local_file, config['ssh-user'],
        config['remote-host'], remote_path)
    ExecuteUtil.execute(execution_string)
    return None

def get_folder_size(config, run_id):
    '''

    '''
    remove_folder_loc = config['output-file']['folder-path'].replace('{run_id}', str(run_id))
    execution_string = "ssh -i '%s' %s@%s 'du -shb %s'" % (
        config['remote-host-key'],
        config['ssh-user'],
        config['remote-host'],
        remove_folder_loc)
    response = ExecuteUtil.execute(execution_string)
    return int(response.split('\t')[0])

def create_run_dir(config, run_id):
    execution_string = "ssh -i '%s' %s@%s 'mkdir %s'" % (
        config['remote-host-key'],
        config['ssh-user'],
        config['remote-host'],
        config['job']['host-path-mount-dir'].replace('{run_id}', str(run_id))
    )
    return ExecuteUtil.execute(execution_string)

def take_screenshot(config,run_id, pod_name, from_time, to_time):
    '''
    from_time in unix timestamp format
    to_time
    '''
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import os

    options = Options()
    options.add_argument("--headless")
    options.add_argument("window-size=1920,2080")
    driver = webdriver.Chrome(chrome_options=options, executable_path="/Users/james_kieley/Downloads/chromedriver")
    driver.implicitly_wait(10)  # seconds

    driver.get('http://localhost:3000/login')
    driver.find_element_by_css_selector('[name="user"]').send_keys("admin")
    driver.find_element_by_css_selector('[name="password"]').send_keys(os.environ['GRAFANA_PASS'])
    driver.find_element_by_css_selector('button').click()

    driver.find_element_by_css_selector(
        '[href="https://grafana.com/docs/grafana/latest?utm_source=grafana_gettingstarted"]')  # wait for this element to be present (due to implicit wait)
    driver.get(f'http://localhost:3000/d/GlXkUBGiz/kubernetes-pod-overview?orgId=1&var-namespace=default&var-pod={pod_name}&var-container=All&from={from_time}&to={to_time}')
    driver.find_element_by_css_selector(
        '[aria-label="TimePicker Open Button"]')  # wait for this element to be present (due to implicit wait)
    driver.find_element_by_css_selector(
        '#panel-3 > div > div:nth-child(1) > div > div.panel-content > div > plugin-component > panel-plugin-graph > grafana-panel > ng-transclude > div > div.graph-panel__chart > canvas.flot-overlay')  # wait for this element to be present (due to implicit wait)

    driver.get_screenshot_as_file(config['screenshot-folder'] + str(run_id) + ".png")