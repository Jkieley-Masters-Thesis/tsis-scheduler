import base64
import logging
from sflower import TempFileHelper
import yaml


def write_text_to_file(text, filename):
    with open(filename, 'w+') as text_file:
        text_file.write(text)


def get_config_data_from_file(config_file, cluster_and_user_name):
    cluster_config_data = {}

    local_config = get_obj_from_yaml(config_file)
    cluster = get_by_key_value('clusters', 'name', cluster_and_user_name, local_config)
    user = get_by_key_value('users', 'name', cluster_and_user_name, local_config)

    check_then_create_data_file('client-certificate','client-certificate-data','client_certificate_file',"client_certificate.crt",user['user'],cluster_config_data)
    check_then_create_data_file('client-key','client-key-data','client_key_file',"client.key",user['user'],cluster_config_data)
    check_then_create_data_file('certificate-authority','certificate-authority-data','client_authority_file',"ca.crt",cluster['cluster'],cluster_config_data)

    if_key_then_copy('username', user['user'], cluster_config_data)
    if_key_then_copy('password', user['user'], cluster_config_data)

    cluster_config_data['host'] = cluster['cluster']['server']
    return cluster_config_data


def get_config_data_from_file_only(config_file):
    cluster_config_data = {}

    local_config = get_obj_from_yaml(config_file)
    cluster = local_config['clusters'][0]
    user = local_config['users'][0]

    check_then_create_data_file('client-certificate','client-certificate-data','client_certificate_file',"client_certificate.crt",user['user'],cluster_config_data)
    check_then_create_data_file('client-key','client-key-data','client_key_file',"client.key",user['user'],cluster_config_data)
    check_then_create_data_file('certificate-authority','certificate-authority-data','client_authority_file',"ca.crt",cluster['cluster'],cluster_config_data)

    if_key_then_copy('username', user['user'], cluster_config_data)
    if_key_then_copy('password', user['user'], cluster_config_data)

    cluster_config_data['host'] = cluster['cluster']['server']
    return cluster_config_data


def temp_file_from_data(data, filename):
    # when called more than once will override the previous one :O
    output_dir = "/Users/james_kieley/git/thesis-kube-nfs/kubernetes/scaling-overflower/test/integration/"
    final_filename = output_dir + filename
    write_text_to_file(get_real_str_from_base64_str(data), final_filename)
    return final_filename

def if_key_then_copy(key, from_dict, to_dict):
    if key in from_dict:
        to_dict[key] = from_dict[key]

def check_then_create_data_file(key, data_key, file_key, file_name, from_dict, to_dict):
    if data_key in from_dict:
        from_dict_data = from_dict[data_key]
        to_dict[file_key] = TempFileHelper.createTempFileFromData(from_dict_data, file_name)
    elif key in from_dict:
        to_dict[file_key] = from_dict[key]
    else:
        raise ValueError("Unable to find either keys: {} or {} in dictionary: {}".format(data_key, key, str(from_dict)))


def get_real_str_from_base64_str(base64str):
    return base64.b64decode(base64str).decode('ascii')


def get_by_key_value(l1, key, value, local_config):
    for obj in local_config[l1]:
        if obj[key] == value:
            return obj
    logging.info("unable to find key value pair in obj list")
    logging.info("key: " + key + " value: " + value)
    logging.info("list: " + str(local_config[l1]))
    return None  # key value not found


def get_obj_from_yaml(path):
    with open(path, 'r') as file:
        yaml_config = yaml.load(file, Loader=yaml.FullLoader)
        return yaml_config
