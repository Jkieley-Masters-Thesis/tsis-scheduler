import logging
import os
import time

import GlobalUtil
from pclusterutils import ExecuteUtil


def create_kops_cluster(*, zones='us-west-2a',
                        cluster_name='myfirstcluster.k8s.local',
                        cluster_s3_store="s3://attempt1-example-com-state-store",
                        instance_type="t2.medium",
                        node_count=1):
    start = time.time()
    logging.info('Begin creating On-Prem Cluster')

    logging.info("zones: %s", zones)
    logging.info("cluster_name: %s", cluster_name)
    logging.info("cluster_s3_store: %s", cluster_s3_store)

    GlobalUtil.setEnv("NAME", cluster_name)
    GlobalUtil.setEnv("KOPS_STATE_STORE", cluster_s3_store)
    GlobalUtil.logEnv("KOPS_CLUSTER_CREATE_SSH_PUB_FILE")
    ExecuteUtil.execute(
        ("kops create cluster"
         " --node-count {}"
         " --node-size {}"
         " --master-size {}"
         " --zones={}"
         " {}").format(str(node_count),instance_type, instance_type, zones, cluster_name)
    )
    ssh_file = os.environ["KOPS_CLUSTER_CREATE_SSH_PUB_FILE"]
    ExecuteUtil.execute("kops create secret --name $NAME sshpublickey admin -i " + ssh_file)
    ExecuteUtil.execute("kops update cluster $NAME --yes")
    ExecuteUtil.execute("kops rolling-update cluster $NAME --yes")
    GlobalUtil.wait_until_cluster_ready(start, 10, 80)
    return {
        'zones': zones,
        'cluster_name': cluster_name,
        'cluster_s3_store': cluster_s3_store,
        'instance_type': instance_type
    }


def destroy_kops_cluster(cluster_name='myfirstcluster.k8s.local',
                        cluster_s3_store="s3://attempt1-example-com-state-store"):
    start = time.time()

    logging.info('Begin decomming On-Prem Cluster')

    GlobalUtil.setEnv("NAME", cluster_name)
    GlobalUtil.setEnv("KOPS_STATE_STORE", cluster_s3_store)

    ExecuteUtil.execute("kops delete cluster --name ${NAME} --yes")
    end = time.time()
    logging.info('Total Execution time: ' + str(end - start))
