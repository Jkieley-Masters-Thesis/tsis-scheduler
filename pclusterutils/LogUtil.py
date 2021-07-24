import logging


def config_loggin(log_file_name):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(process)d:%(thread)d %(filename)s:%(funcName)s:%(lineno)d: %(message)s",
        handlers=[
            logging.FileHandler(log_file_name),
            logging.StreamHandler()
        ]
    )
