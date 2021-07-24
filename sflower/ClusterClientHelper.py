import kubernetes

from sflower import TempFileHelper
from sflower.KubeClient import KubeClient


def get_cluster_client_from_data(ca_cert_data, cert_data, cert_key_data, host):
    ca_cert_file = TempFileHelper.createTempFileFromData(ca_cert_data, "ca_cert_file")
    cert_file = TempFileHelper.createTempFileFromData(cert_data, "cert_file")
    key_file = TempFileHelper.createTempFileFromData(cert_key_data, "key_file")
    configuration = kubernetes.client.Configuration()
    configuration.ssl_ca_cert = ca_cert_file
    configuration.host = host
    configuration.cert_file = cert_file
    configuration.key_file = key_file
    configuration.debug = True
    return KubeClient(configuration)
