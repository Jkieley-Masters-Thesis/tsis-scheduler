import yaml


def read_text_file(filename):
    with open(filename, 'r') as file:
        data = file.read()
        return data


def read_yaml_file(filename):
    with open(filename, 'r') as file:
        yaml_data = yaml.load(file, Loader=yaml.FullLoader)
        return yaml_data
