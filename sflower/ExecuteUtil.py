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
        raise Exception(f'Command returned a non-successful status code, command: {command}, status: {process.returncode}')
    return output


def execute_cwd(command, cwd):
    logging.info("executing command: " + "\"" + command + "\"")
    output = ""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=cwd)
    for c in iter(lambda: process.stdout.readline(), b''):  # replace '' with b'' for Python 3
        output_line = c.decode('utf-8')
        output += output_line
        logging.info(output_line.replace("\n", ""))
    return output

def execute_env(command, env):
    logging.info("executing command: " + "\"" + command + "\"")
    output = ""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, env=env)
    for c in iter(lambda: process.stdout.readline(), b''):  # replace '' with b'' for Python 3
        output_line = c.decode('utf-8')
        output += output_line
        logging.info(output_line.replace("\n", ""))
    return output
