import logging

from sflower import Clusters
from sflower import OverflowScalingPolicy


def single_check():
    logging.info('performing single check')
    OverflowScalingPolicy.overflow_scale_policy()
