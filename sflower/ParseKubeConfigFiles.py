import yaml

from ClusterClientHelper import get_cluster_client_from_data


def get():
    return None


def get_cluster_from_kube_config_file(file, clusterIndex, userIndex):
    with open(file, 'r') as file:
        yaml_config = yaml.load(file, Loader=yaml.FullLoader)
        ca_cert_data = yaml_config['clusters'][clusterIndex]['cluster']['certificate-authority-data']
        host = yaml_config['clusters'][clusterIndex]['cluster']['server']
        cert_data = yaml_config['users'][userIndex]['user']['client-certificate-data']
        cert_key_data = yaml_config['users'][userIndex]['user']['client-key-data']
        return ca_cert_data, host, cert_data, cert_key_data


def get_cluster_from_kube_config_file_with_username(file, clusterIndex, userIndex):
    with open(file, 'r') as file:
        yaml_config = yaml.load(file, Loader=yaml.FullLoader)

        ca_cert_data = yaml_config['clusters'][clusterIndex]['cluster']['certificate-authority-data']
        host = yaml_config['clusters'][clusterIndex]['cluster']['server']
        cert_data = yaml_config['users'][userIndex]['user']['client-certificate-data']
        cert_key_data = yaml_config['users'][userIndex]['user']['client-key-data']
        username = yaml_config['users'][userIndex]['user']['username']
        password = yaml_config['users'][userIndex]['user']['password']

        return {
            'ca_cert_data': ca_cert_data,
            'host': host,
            'cert_data': cert_data,
            'cert_key_data': cert_key_data,
            'username': username,
            'password': password
        }


def get_cluster_from_config_file(clusterIndex, stage_config, userIndex):
    ca_cert_data, host, cert_data, cert_key_data = get_cluster_from_kube_config_file(stage_config, clusterIndex,
                                                                                     userIndex)
    return get_cluster_client_from_data(ca_cert_data, cert_data, cert_key_data, host)
