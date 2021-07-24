import logging
import subprocess


def execute(command):
    logging.info("executing command: " + "\"" + command + "\"")
    output = ""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    for c in iter(lambda: process.stdout.readline(), b''):  # replace '' with b'' for Python 3
        output_line = c.decode('utf-8')
        output += output_line
        logging.info(output_line.replace("\n", ""))

    streamdata = process.communicate()[0]
    logging.info("Subprocess return code: " + str(process.returncode))
    if process.returncode != 0:
        raise Exception(
            f'Command returned a non-successful status code, command: {command}, status: {process.returncode}')
    return output


def execute_with_retry(command):
    unsuccessful = True
    attempt_count = 0
    max_attempts = 5
    output = ''
    while unsuccessful and attempt_count < max_attempts:
        logging.info("attempting command with retry")
        output, process = execute_command_internal(command)
        if process.returncode == 0:
            unsuccessful = False
        attempt_count += 1

        if attempt_count == max_attempts and unsuccessful:
            raise Exception(
                f'Command returned a non-successful status code, command: {command}, status: {process.returncode}')

    return output


def execute_command_internal(command):
    logging.info("executing command: " + "\"" + command + "\"")
    output = ""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    for c in iter(lambda: process.stdout.readline(), b''):  # replace '' with b'' for Python 3
        output_line = c.decode('utf-8')
        output += output_line
        logging.info(output_line.replace("\n", ""))
    streamdata = process.communicate()[0]
    logging.info("Subprocess return code: " + str(process.returncode))
    return output, process


def execute_cwd(command, cwd):
    logging.info("executing command: " + "\"" + command + "\"")
    output = ""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=cwd)
    for c in iter(lambda: process.stdout.readline(), b''):  # replace '' with b'' for Python 3
        output_line = c.decode('utf-8')
        output += output_line
        logging.info(output_line.replace("\n", ""))
    return output
