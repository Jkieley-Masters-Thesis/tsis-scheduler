import http.client
import json
import logging
import os
import pathlib
import time

import boto3
import kubernetes
import yaml
from kubernetes.client.rest import ApiException

from sflower import AwsClient
from sflower import ClusterClientHelper
from sflower import DBClient
from sflower import ExecuteUtil
from sflower import GetCostService
from sflower import IOUtils
from sflower import KubeService
from sflower import ReadKubeConfigUtil
from sflower.KubeClient import KubeClient

key_path = str(pathlib.Path(__file__).parent.parent.absolute())


def get_master_cluster():
    logging.info("getting master cluster")
    return get_cluster_from_env_key("MCS_MASTER")


def get_scale_from_cluster():
    logging.info("getting scale from cluster")
    cluster_data = ReadKubeConfigUtil.get_config_data_from_file_only(os.environ["FROM_CLUSTER_KUBE_CONFIG_FILE"])
    configuration = KubeService.get_configuration_from_config(cluster_data)
    client = KubeClient(configuration)
    return client


def get_cluster_from_env_key(key):
    configuration = kubernetes.client.Configuration()

    logEnvKey(key + "_CLUSTER_SSL_CA_CERT")
    logEnvKey(key + "_CLUSTER_HOST")
    logEnvKey(key + "_CLUSTER_CERT_FILE")
    logEnvKey(key + "_CLUSTER_KEY_FILE")
    logEnvKey(key + "_CLUSTER_USE_USERNAME")

    configuration.ssl_ca_cert = os.environ[key + "_CLUSTER_SSL_CA_CERT"]
    configuration.host = os.environ[key + "_CLUSTER_HOST"]
    configuration.cert_file = os.environ[key + "_CLUSTER_CERT_FILE"]
    configuration.key_file = os.environ[key + "_CLUSTER_KEY_FILE"]

    if "true" in os.environ[key + "_CLUSTER_USE_USERNAME"]:
        logEnvKey(key + "_CLUSTER_USERNAME")
        logEnvKey(key + "_CLUSTER_PASSWORD")
        configuration.username = os.environ[key + "_CLUSTER_USERNAME"]
        configuration.password = os.environ[key + "_CLUSTER_PASSWORD"]
    configuration.debug = True
    return KubeClient(configuration)


def logEnvKey(key):
    logging.info(
        "reading environment variable: " + key + ": " + os.environ[key])


def get_cluster_client_by_key_dir(prefix, host):
    configuration = kubernetes.client.Configuration()
    configuration.ssl_ca_cert = key_path + "/keys/" + prefix + "/clustera-ca.crt"
    configuration.host = host
    configuration.cert_file = key_path + "/keys/" + prefix + "/client.crt"
    configuration.key_file = key_path + "/keys/" + prefix + "/client.key"
    configuration.debug = True
    return KubeClient(configuration)


def get_by_region(clusters, region):
    for cluster in clusters:
        if region == cluster['region']:
            return cluster
    return None


def get_scaling_policy():
    return get_master_cluster().get_mcs_policy()


def get_scale_to_clusters():
    '''
    Used to:
    1. check if the cluster to overflow to has been created
    2. Get the information for that cluster
    :return:
    '''

    response = get_master_cluster().get_mcs_clusters()
    # what happens when there are no crds here,
    # what happens when the crds definition is not there

    clusters = response['items']
    return clusters


def scale_to_cluster_exists(clusters):
    return len(clusters) > 0


def get_scale_to_cluster():
    logging.info("getting scale to cluster")
    cluster_data = ReadKubeConfigUtil.get_config_data_from_file_only(os.environ["TO_CLUSTER_KUBE_CONFIG_FILE"])
    configuration = KubeService.get_configuration_from_config(cluster_data)
    client = KubeClient(configuration)
    return client


def get_cluster_client_from_cluster_crd(cluster):
    ca_cert_data = cluster['spec']['cluster']['certificate-authority-data']
    cert_data = cluster['spec']['cluster']['user']['client-certificate-data']
    cert_key_data = cluster['spec']['cluster']['user']['client-key-data']
    host = cluster['spec']['cluster']['server']
    return ClusterClientHelper.get_cluster_client_from_data(ca_cert_data, cert_data, cert_key_data, host)


def get_cluster_description(cluster):
    return "desc: " + yaml.dump(cluster)


def create_mcs_cluster(config):
    mcs_cluster = IOUtils.read_yaml_file(os.environ["SKELETON_MCS_CLUSTER_YAML"])
    json_obj = json.loads(config)

    mcs_cluster['spec']['cluster']['certificate-authority-data'] = json_obj['ca_cert_data']
    mcs_cluster['spec']['cluster']['server'] = json_obj['host']
    mcs_cluster['spec']['cluster']['name'] = json_obj['host']
    mcs_cluster['metadata']['name'] = "dynamically-created-cluster.k8s.local"
    mcs_cluster['spec']['cluster']['user']['client-certificate-data'] = json_obj['cert_data']
    mcs_cluster['spec']['cluster']['user']['client-key-data'] = json_obj['cert_key_data']
    mcs_cluster['spec']['cluster']['user']['password'] = json_obj['password']
    mcs_cluster['spec']['cluster']['user']['username'] = json_obj['username']

    logging.info("creating cluster: " + json_obj['host'])

    safe_create_mcs_cluster(mcs_cluster)


def safe_create_mcs_cluster(mcs_cluster):
    try:
        get_master_cluster().create_mcs_clusters(mcs_cluster)
        logging.info("MCS Cluster create with name: " + mcs_cluster['metadata']['name'])
    except ApiException as e:
        if e.status == 409 and 'Conflict' in e.reason:
            logging.info("MCS Cluster already existed by name: " + mcs_cluster['metadata']['name'])
        else:
            raise e


def get_total_cpu(pending_pods):
    sum_cpu_units = 0.0
    cpu_full_list = []
    for pod in pending_pods:
        for container in pod.spec.containers:
            value = container.resources.requests['cpu']

            if 'm' in value:
                value = value.replace('m', '')
                value = float(value)
                value = value / 1000
            else:
                value = float(value)

            sum_cpu_units = sum_cpu_units + value
            cpu_full_list.append(value)
    return sum_cpu_units, cpu_full_list


def get_total_memory(pending_pods):
    sum_mem_units = 0.0
    mem_full_list = []
    for pod in pending_pods:
        for container in pod.spec.containers:
            value = container.resources.requests['memory']
            value = value.replace('Mi', '')
            value = float(value)
            sum_mem_units = sum_mem_units + value
            mem_full_list.append(value)
    return sum_mem_units, mem_full_list


def rightsize(pending_pods, scalefactor):
    """
    # rightsize (determine the instance type by the following inputs:
    # input:
    #  - size of pending workloads (mb of RAM, and millicores or CPU needed)
    #  - scale factor (percent)
    #  - possible instance types to choose from
    # output:
    #  - AWS instance type

    """
    logging.info("Right sizing for scalefactor: " + str(scalefactor))
    total_cpu, cpu_list = get_total_cpu(pending_pods)  # in vcpus
    total_mem, mem_list = get_total_memory(pending_pods)  # in Mb
    total_mem = total_mem / 1000  # convert to gb

    total_cpu = total_cpu * scalefactor
    total_mem = total_mem * scalefactor

    logging.info("Right sizing for total cpu: " + str(total_cpu))
    logging.info("Right sizing for total mem: " + str(total_mem))

    # start with the largest possible
    # move to the lowest, that will still satisfy the req
    # it's possible first (largest one, is not large enought to satisfy, so use the largest)

    # c5 instance data

    possible_instances = [
        ['c5.xlarge', 4.0, 8.0],
        ['c5.2xlarge', 8.0, 16.0],
        ['c5.4xlarge', 16.0, 32.0],
        ['c5.9xlarge', 36.0, 72.0],
        ['c5.12xlarge', 48.0, 96.0],
        ['c5.18xlarge', 72.0, 144.0],
        ['c5.24xlarge', 96.0, 192.0]
    ]

    # begin instance selection
    possible_instances = sorted(possible_instances, key=lambda x: x[1], reverse=True)
    selected_instance = possible_instances[0][0]
    for instance in possible_instances:
        instance_name = instance[0]
        instance_vcpus = instance[1]
        instance_mem = instance[2]
        logging.info("Checking Instance: " + str(instance))
        if instance_vcpus >= total_cpu and instance_mem >= total_mem:
            selected_instance = instance_name
            logging.info("Selecting Instance: " + str(instance))
        else:
            break

    logging.info("Returning selected Instance: " + str(selected_instance))
    return selected_instance


def cost_optimization(instance_type):
    """
    # zone selection (cost optimization)
    # input:
    #  - instance type
    # output:
    #  - region
    #  - zone
    """
    cost_by_instance_type = GetCostService.get_cost_group_by_values(instance_type)

    # example structure of cost_by_instance_type
    # [cost, list of regions]
    # [(Decimal('0.0850000000'), ['us-east-1', 'us-east-2', 'us-west-2']), (Decimal('0.1060000000'), ['us-west-1'])]

    cheapest_region_short_name = cost_by_instance_type[0][1][0]
    zones = AwsClient.get_ec2_availability_zones(cheapest_region_short_name)
    region = cheapest_region_short_name
    zone = zones[0]

    logging.info("Region Pricing info: " + str(cost_by_instance_type))
    logging.info("Cheapest Region: " + str(region))
    logging.info("Cheapest Zone: " + str(zone))

    return region, zone


def create_scale_to_cluster(pending_pods, scalefactor):
    # all the following is optimizing for: execution time, and cost
    instance_type = rightsize(pending_pods, scalefactor)
    aws_region, aws_zone = cost_optimization(instance_type)
    cost_optimization("t2.medium")  # this is just to log the cost of master

    create_or_destory_cluster("create", aws_region, aws_zone, instance_type)


def create_or_destory_cluster(create_o_des, aws_region, aws_zone, instance_type):
    # todo: download cloud cluster keys/files through boto3
    # https://stackoverflow.com/questions/29378763/how-to-save-s3-object-to-a-file-using-boto3
    response_json = trigger_circle_ci_tsis_create_cluster(aws_region, aws_zone, create_o_des, instance_type)
    wait_for_workload_complete(response_json['id'])
    os.environ['CLUSTER_IS_CREATED'] = "1"

    # aws s3 cp s3://thesis-cluster-creation/id_rsa ./cluster-keys/id_rsa
    # aws s3 cp s3://thesis-cluster-creation/id_rsa.pub ./cluster-keys/id_rsa.pub
    # aws s3 cp s3://thesis-cluster-creation/kube_config ./cluster-keys/kube_config
    # aws s3 cp s3://thesis-cluster-creation/ip-address.txt ./cluster-keys/ip-address.txt

    get_cluster_files_and_set_vars()

    # 4. Continue and download keys/files
    # 5. set TO_CLUSTER_KUBE_CONFIG_FILE, ASU_WORKER_NODE_IP


def get_cluster_files_and_set_vars():
    s3_client = boto3.client('s3')
    s3_client.download_file('thesis-cluster-creation', 'id_rsa', './cluster-keys/id_rsa')
    s3_client.download_file('thesis-cluster-creation', 'id_rsa.pub', './cluster-keys/id_rsa.pub')
    s3_client.download_file('thesis-cluster-creation', 'kube_config', './cluster-keys/kube_config')
    s3_client.download_file('thesis-cluster-creation', 'ip-address.txt', './cluster-keys/ip-address.txt')
    ssh_key_full_path = os.path.abspath('./cluster-keys/id_rsa')

    ExecuteUtil.execute("chmod 400 " + ssh_key_full_path)

    ExecuteUtil.execute("scp " + ssh_key_full_path + " asu-worker:/root/id_rsa")

    os.environ['TO_CLUSTER_KUBE_CONFIG_FILE'] = os.path.abspath('./cluster-keys/kube_config')
    os.environ['ASU_WORKER_SSH_KEY'] = ssh_key_full_path
    os.environ['ASU_WORKER_NODE_IP'] = IOUtils.read_text_file('./cluster-keys/ip-address.txt').replace("\n", "")
    os.environ['CLUSTER_FILES_ARE_DOWNLOADED'] = "1"

    logging.info("done")


def wait_for_workload_complete(pipeline_id):
    max_count = 900
    count = 0
    creation_was_successful = False
    response_json = ''
    while count < max_count:
        response_json = trigger_circle_ci_get_workflow(pipeline_id)
        logging.info("Checking workflow status, " + str(count))
        if len(response_json['items']) > 0:
            if response_json['items'][0]['status'] == 'success':
                logging.info("Workflow Status was successful!")
                creation_was_successful = True
                break
        count += 1
        time.sleep(5)

    if not creation_was_successful:
        raise Exception("Failure to create cluster")
    return response_json


def trigger_circle_ci_get_workflow(pipeline_id):
    '''
    API Documentation: https://circleci.com/docs/api/v2/?utm_medium=SEM&utm_source=gnb&utm_campaign=SEM-gb-DSA-Eng-uscan&utm_content=&utm_term=dynamicSearch-&gclid=CjwKCAjwn6GGBhADEiwAruUcKl34epNZ0br2O0xL2Ory8BuTs05x085-eWacBr_1NHneRg_Vf9fNKhoCd0cQAvD_BwE#operation/listWorkflowsByPipelineId

    example response:
    {
    "next_page_token": null,
    "items": [
        {
            "pipeline_id": "e19c1eac-dc68-4b27-a568-33d37ea4814b",
            "id": "c4c4a0c9-ab87-4393-bd24-59491c5c0559",
            "name": "deployer",
            "project_slug": "bb/jkieley1/tsis-create-cluster",
            "status": "success", // "running",
            "started_by": "9a2faf93-4942-4d6f-9cf8-1f55297db381",
            "pipeline_number": 30,
            "created_at": "2021-06-15T15:25:50Z",
            "stopped_at": "2021-06-15T15:38:06Z"
        }
    ]
}
    '''
    conn = http.client.HTTPSConnection("circleci.com")
    payload = ''
    headers = {
        'Authorization': 'Basic OTk5ZmMyYjY1MTYzOGU2NWNkNWUwNTBlN2QwMGQ3NjViNGVkMjQyYTo=',
        'Cookie': 'ring-session=TGhc%2FK75OBDxT4e%2FgGQ6%2BJns1NdGPeKpgmbX3TIb03LCj%2FI89eSEAcKHhXkbBzOtWBskdjr14mv0QSBuX81AAevoIxJz7g761qj8PTpZfr70WfQn1nWArXbYW5cpFvitks34Cl785SR2WFbKuhOM77N30NXURvxmbG80Cm17NraelUdSsbo7QYYma0%2BQKomLlXDgAnNGrxq2xdlPV255fvwbE8ZrvWfP9JphYMgmnh8%3D--tmzqLE3Ab1UdVqkvnNxZTtn3g6H5DbjgwpSQztSGoIk%3D'
    }
    conn.request("GET", "/api/v2/pipeline/" + pipeline_id + "/workflow", payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_str = data.decode("utf-8")
    response_json = json.loads(response_str)
    logging.info("trigger_circle_ci_get_workflow response: " + json.dumps(response_json, indent=4, sort_keys=True))
    return response_json


def trigger_circle_ci_tsis_create_cluster(aws_region, aws_zone, create_o_des, instance_type):
    '''
    Api Documentation: https://circleci.com/docs/api/v2/?utm_medium=SEM&utm_source=gnb&utm_campaign=SEM-gb-DSA-Eng-uscan&utm_content=&utm_term=dynamicSearch-&gclid=CjwKCAjwn6GGBhADEiwAruUcKl34epNZ0br2O0xL2Ory8BuTs05x085-eWacBr_1NHneRg_Vf9fNKhoCd0cQAvD_BwE#operation/triggerPipeline

    Examples response:
    {
      "number" : 30,
      "state" : "pending",
      "id" : "e19c1eac-dc68-4b27-a568-33d37ea4814b",
      "created_at" : "2021-06-15T15:25:50.034Z"
    }
    '''
    conn = http.client.HTTPSConnection("circleci.com")
    payload = json.dumps({
        "branch": "with-parameters",
        "parameters": {
            "operation": create_o_des,
            "awsRegion": aws_region,
            "awsZone": aws_zone,
            "clusterNodeInstanceType": instance_type
        }
    })
    headers = {
        'authorization': 'Basic OTk5ZmMyYjY1MTYzOGU2NWNkNWUwNTBlN2QwMGQ3NjViNGVkMjQyYTo=',
        'content-type': 'application/json',
        'x-attribution-actor-id': 'jamesk_remote_api',
        'x-attribution-login': 'jamesk_remote_api'
    }
    conn.request("POST", "/api/v2/project/bitbucket/jkieley1/tsis-create-cluster/pipeline", payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_str = data.decode("utf-8")
    response_json = json.loads(response_str)
    logging.info(
        "trigger_circle_ci_tsis_create_cluster response: " + json.dumps(response_json, indent=4, sort_keys=True))
    return response_json


def trigger_circle_ci_tsis_scale_cluster():
    '''
    Api Documentation: https://circleci.com/docs/api/v2/?utm_medium=SEM&utm_source=gnb&utm_campaign=SEM-gb-DSA-Eng-uscan&utm_content=&utm_term=dynamicSearch-&gclid=CjwKCAjwn6GGBhADEiwAruUcKl34epNZ0br2O0xL2Ory8BuTs05x085-eWacBr_1NHneRg_Vf9fNKhoCd0cQAvD_BwE#operation/triggerPipeline

    Examples response:
    {
      "number" : 30,
      "state" : "pending",
      "id" : "e19c1eac-dc68-4b27-a568-33d37ea4814b",
      "created_at" : "2021-06-15T15:25:50.034Z"
    }
    '''
    conn = http.client.HTTPSConnection("circleci.com")
    payload = json.dumps({
        "branch": "execute",
    })
    headers = {
        'authorization': 'Basic OTk5ZmMyYjY1MTYzOGU2NWNkNWUwNTBlN2QwMGQ3NjViNGVkMjQyYTo=',
        'content-type': 'application/json',
        'x-attribution-actor-id': 'jamesk_remote_api',
        'x-attribution-login': 'jamesk_remote_api'
    }
    conn.request("POST", "/api/v2/project/bitbucket/jkieley1/tsis-cluster-scaler/pipeline", payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_str = data.decode("utf-8")
    response_json = json.loads(response_str)
    logging.info(
        "trigger_circle_ci_tsis_scale_cluster response: " + json.dumps(response_json, indent=4, sort_keys=True))
    return response_json


def copy_aws_to_cluster_data():
    exe_response = ExecuteUtil.execute_env(
        "bash /Users/james_kieley/git/thesis-kube-nfs/kubernetes/scaling-overflower/experiment-scheduling-ml-workload/3-model-workload/run-scripts/copy-cluster-files-locally.sh",
        {"PATH": "/Users/james_kieley/.bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/X11/bin"})

    # os.environ["TO_CLUSTER_KUBE_CONFIG_FILE"] = "/Users/james_kieley/git/thesis-kube-keys/kube_config"
    logging.info("Local Cluster files have been copied")
    return exe_response


def create_cluster():
    logging.info("calling scaling-overflower-create-cluster/spawn")
    conn = http.client.HTTPSConnection("scaling-overflower-create-cluster", 8080, timeout=800)
    payload = ''
    headers = {}
    conn.request("GET", "/spawn", payload, headers)
    res = conn.getresponse()
    data = res.read()
    logging.info("response from /spawn: " + data.decode("utf-8"))


def get_created_cluster_config():
    logging.info("calling scaling-overflower-create-cluster/config")

    conn = http.client.HTTPSConnection("scaling-overflower-create-cluster", 8080)
    payload = ''
    headers = {}
    conn.request("GET", "/config", payload, headers)
    res = conn.getresponse()
    data = res.read()
    response_text = data.decode("utf-8")
    logging.info("response from /config: " + response_text)
    return response_text


def get_cheapest_region_by_instance(instance):
    # couldtodo: query mongodb data
    DBClient.query_cheapest_region_by_instance(instance)
    pass


def get_cheapest_region_by_instance_spot_instance():
    # couldtodo: query data from AWS live, persist: max, min and final decision
    # more analysis can be done by quering the entire 90day history and looking for the largest variences
    pass


def create_scale_to_cluster_cheapest_by_instance_region():
    instance = "t2.medium"
    region = get_cheapest_region_by_instance()  # instances will come from cluster definition, no need to make it dynamic now
    spot_instance_region = get_cheapest_region_by_instance_spot_instance()
    # /Users/james_kieley/git/thesis-kube-nfs/kubernetes/scaling-overflower/spawn-pcluster/kubernetes/config/myfirstcluster.k8s.local_all.yaml
    return None
