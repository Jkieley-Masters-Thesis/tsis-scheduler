import base64
import logging
import tempfile


def get():
    return None


def createTempFileFromData(file_data, logKey):
    temporary_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    temporary_file.write(base64.b64decode(file_data).decode('ascii'))
    temporary_file.close()
    file_name = temporary_file.name
    logging.info("creating temporary file: " + file_name + " for: " + logKey)
    return file_name


def createTempFile(file_data, logKey):
    temporary_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    temporary_file.write(file_data)
    temporary_file.close()
    file_name = temporary_file.name
    logging.info("creating temporary file: " + file_name + " for: " + logKey)
    return file_name
