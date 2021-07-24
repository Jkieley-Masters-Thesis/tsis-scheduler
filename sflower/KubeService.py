import kubernetes


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


def get_batch_v1_api_from_config(config):
    configuration = kubernetes.client.Configuration()
    configuration.ssl_ca_cert = config['client_authority_file']
    configuration.host = config['host']
    configuration.cert_file = config['client_certificate_file']
    configuration.key_file = config['client_key_file']
    configuration.debug = True
    api_client = kubernetes.client.ApiClient(configuration)
    api_instance = kubernetes.client.BatchV1Api(api_client)
    return api_instance


def get_configuration_from_config(config):
    configuration = kubernetes.client.Configuration()
    configuration.ssl_ca_cert = config['client_authority_file']
    configuration.host = config['host']
    configuration.cert_file = config['client_certificate_file']
    configuration.key_file = config['client_key_file']
    configuration.debug = True
    return configuration
