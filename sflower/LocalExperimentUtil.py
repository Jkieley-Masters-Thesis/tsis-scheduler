import ReadKubeConfigUtil
from experutil import ExperimentCreateClusterUtil, ExperimentUtil


def get():
    return None


def get_already_created_cluster_data():
    static_cluster_info = get_static_cluster_info()
    cluster_info = ReadKubeConfigUtil.get_config_data_from_file("/Users/james_kieley/.kube/config",
                                                                'myfirstcluster.k8s.local')
    cluster_info.update(static_cluster_info)
    return cluster_info


def get_minikube_config():
    static_cluster_info = get_static_cluster_info()
    cluster_info = ReadKubeConfigUtil.get_config_data_from_file("/Users/james_kieley/.kube/config", 'minikube')
    cluster_info.update(static_cluster_info)
    return cluster_info


def get_static_cluster_info():
    return {
        'zones': 'us-west-2a',
        'cluster_name': 'myfirstcluster.k8s.local',
        'cluster_s3_store': "s3://attempt1-example-com-state-store",
        'instance_type': 't2.medium'
    }


def get_kube_config_based_on_cluster(use_cluster="Amazon", create_cluster=False, **kwargs):
    if use_cluster == "minikube":
        return get_minikube_config()
    elif use_cluster == "Amazon" and create_cluster:
        cluster_info = ExperimentCreateClusterUtil.create_kops_cluster(**kwargs)
        ExperimentUtil.deploy_docker_creds()
        return cluster_info
    elif use_cluster == "Amazon" and not create_cluster:
        return get_already_created_cluster_data()
    else:
        raise ValueError("Invalid values for use_cluster, create_cluster")
