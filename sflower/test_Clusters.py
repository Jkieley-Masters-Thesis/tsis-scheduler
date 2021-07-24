from unittest import TestCase

from pclusterutils import LogUtil
from sflower import Clusters
LogUtil.config_loggin("tests.log")


class Test(TestCase):
    def test_trigger_circle_ci_get_workflow(self):
        response_json = Clusters.wait_for_workload_complete("46db8f85-93a6-494f-a99e-96a51af7a424")
        self.assertEqual(response_json['items'][0]['status'], 'success')
