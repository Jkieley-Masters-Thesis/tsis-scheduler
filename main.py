import logging
import os

from pclusterutils import LogUtil

LogUtil.config_loggin("mcs.log")

import threading
from sflower import PolicyHandler

watch_interval = 60.0  # seconds


def main():
    logging.info('starting')
    threading.Timer(0, start_watch).start()


def start_watch():
    PolicyHandler.single_check()
    threading.Timer(watch_interval, start_watch).start()


if __name__ == '__main__': main()
