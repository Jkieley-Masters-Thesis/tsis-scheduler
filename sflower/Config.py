import logging
import os

import yaml

clusters = None
settings = None
cluster_config_path_str = os.environ["MCS_CONFIG_FILE"]
logging.info('loading config file: ' + cluster_config_path_str)

with open(cluster_config_path_str, 'r') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    yaml_config = yaml.load(file, Loader=yaml.FullLoader)

    logging.info('config file contents: ' + str(yaml_config))
    clusters = yaml_config['clusters']
    settings = yaml_config['settings']
