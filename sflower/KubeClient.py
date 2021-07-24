import copy
import json
import logging
import sys

import kubernetes
import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException

from sflower import DeploymentPodMapping


class KubeClient:

    def __init__(self, configuration):
        self.configuration = configuration
        self.CoreV1ApiInstance = client.CoreV1Api(kubernetes.client.ApiClient(self.configuration))
        self.AppsV1ApiInstance = client.AppsV1Api(kubernetes.client.ApiClient(self.configuration))
        self.CustomApiInstance = client.CustomObjectsApi(kubernetes.client.ApiClient(self.configuration))
        self.BatchV1ApiInstance = client.BatchV1Api(kubernetes.client.ApiClient(self.configuration))

    def get_all_pods(self):
        field_selector = 'metadata.namespace=default'
        api_response = self.CoreV1ApiInstance.list_pod_for_all_namespaces(timeout_seconds=60, watch=False,
                                                                          field_selector=field_selector)
        pods = api_response.items
        num_of_pods = len(pods)
        if num_of_pods > 0:
            return pods
        else:
            return None

    def get_pending_pods(self):
        # pods that are pending have not been assigned a node (spec.nodeName==)
        field_selector = 'spec.nodeName==,metadata.namespace=default'
        api_response = self.CoreV1ApiInstance.list_pod_for_all_namespaces(timeout_seconds=60, watch=False,
                                                                          field_selector=field_selector)
        pods = api_response.items
        num_of_pods = len(pods)
        if num_of_pods > 0:
            return pods
        else:
            return []

    def get_failed_pods(self):
        # pods that are pending have not been assigned a node (spec.nodeName==)
        # kubectl delete pods --field-selector=status.phase=Failed
        field_selector = 'status.phase=Failed,metadata.namespace=default'
        api_response = self.CoreV1ApiInstance.list_pod_for_all_namespaces(timeout_seconds=60, watch=False,
                                                                          field_selector=field_selector)
        pods = api_response.items
        num_of_pods = len(pods)
        if num_of_pods > 0:
            return pods
        else:
            return []

    def get_pods_by_job(self, job):
        # pods that are pending have not been assigned a node (spec.nodeName==)
        label_selector = 'job-name='+job.metadata.name
        api_response = self.CoreV1ApiInstance.list_namespaced_pod('default',timeout_seconds=60, watch=False,
                                                                          label_selector=label_selector)
        pods = api_response.items
        num_of_pods = len(pods)
        if num_of_pods > 0:
            return pods
        else:
            return []

    def get_jobs(self):
        # jobs that are pending have not been assigned a node (spec.nodeName==)
        api_response = self.BatchV1ApiInstance.list_namespaced_job('default', timeout_seconds=60, watch=False)
        jobs = api_response.items
        num_of_jobs = len(jobs)
        if num_of_jobs > 0:
            return jobs
        else:
            return None

    def get_deployments(self):
        api_response = self.AppsV1ApiInstance.list_deployment_for_all_namespaces(timeout_seconds=60, watch=False)
        deployments = api_response.items
        num_of_deployments = len(deployments)
        if num_of_deployments > 0:
            return deployments
        else:
            return None

    def create_deployment(self, deployment):
        return self.AppsV1ApiInstance.create_namespaced_deployment(body=deployment, namespace="default")

    def create_job(self, job):
        job.metadata.resource_version = None  # required to clear out this value to create a new deployment
        job.spec.selector = None
        job.spec.template.metadata = None
        return self.BatchV1ApiInstance.create_namespaced_job(body=job, namespace="default")

    def create_job_from_yaml(self, job):
        return self.BatchV1ApiInstance.create_namespaced_job(body=job, namespace="default")


    def delete_job(self, job):
        logging.info("deleting job: " + job.metadata.name)
        return self.BatchV1ApiInstance.delete_namespaced_job(job.metadata.name, "default")

    def delete_pod(self, pod):
        logging.info("deleting pod: "+ pod.metadata.name)
        return self.CoreV1ApiInstance.delete_namespaced_pod(pod.metadata.name, "default")

    def delete_pods_from_job(self, job):
        # get all pods for a given job
        pods = self.get_pods_by_job(job)
        for pod in pods:
            self.delete_pod(pod)

    def remove_null_values(self, dictionary):
        for key in list(dictionary.keys()):
            value = dictionary[key]
            if value is None:
                del dictionary[key]
            if type(value) is dict:
                self.remove_null_values(value)
            if isinstance(value, list):
                for e in value:
                    self.remove_null_values(e)

    def remove_keys_except(self, dictionary, remove_except_keys):
        for key in list(dictionary.keys()):
            if key not in remove_except_keys:
              del dictionary[key]

    def deployment_match_key(self, deployment):
        """
        deployment_match_key = lambda x : x.spec.selector.match_labels['app']
        pod_match_key = lambda x : x.metadata.labels['app']

        :param deployment:
        :return:
        """
        if 'app' in deployment.spec.selector.match_labels:
            return deployment.spec.selector.match_labels['app']
        else:
            return None

    def pod_match_key(self, pod):
        try:
            if 'app' in pod.metadata.labels:
                return pod.metadata.labels['app']
            else:
                return None
        except:
            return None

    def get_deployment_pod_mapping(self, deployments, pods):
        deployment_keys = list(map(self.deployment_match_key, deployments))
        pod_keys = list(map(self.pod_match_key, pods))

        deploy_to_pod_mapping = []
        for i, deployment_key in enumerate(deployment_keys):
            if deployment_key is None: continue
            dtpm = DeploymentPodMapping(deployments[i])
            pods_that_map = []
            for i, pod_key in enumerate(pod_keys):
                if pod_key is None: continue
                if pod_key == deployment_key:
                    pods_that_map.append(pods[i])
            if pods_that_map:
                dtpm.pods = pods_that_map
                deploy_to_pod_mapping.append(dtpm)

        return deploy_to_pod_mapping

    def get_mapping_for_pod(self, pod, deploy_to_pod_mapping):
        for mapping in deploy_to_pod_mapping:
            for cpod in mapping.pods:
                if pod is cpod:
                    return mapping.deployment
        return None

    def duplicate_deployment(self, deployment_to_copy):
        '''
        Creates the given deployment, and returns the created deployment, if it already exists it finds the existing
        deployment by deployment_clustera.metadata.name and returns that so it can be updated.
        :param deployment_clustera:
        :return:
        '''
        deploy = copy.deepcopy(deployment_to_copy)
        deploy.metadata.resource_version = None  # required to clear out this value to create a new deployment
        deploy.spec.replicas = 0  # always init deployment with 0 replicas, to be incremented later

        deploy_result = None
        try:
            deploy_result = self.create_deployment(deploy)
        except ApiException as e:
            if e.status == 409 and 'Conflict' in e.reason:
                logging.info("Deployment already existed by name: " + deploy.metadata.name)
            else:
                raise e
        if deploy_result is None:
            deployments = self.get_deployments()
            deploys_by_name = [x for x in deployments if deploy.metadata.name in x.metadata.name]
            if len(deploys_by_name) == 1:
                deploy_result = deploys_by_name[0]
        if deploy_result is None:
            raise RuntimeError("Unable to find deployment by name: " + deploy.metadata.name)
        return deploy_result

    def duplicate_job(self, job_to_copy):
        '''
        Creates the given deployment, and returns the created deployment, if it already exists it finds the existing
        deployment by deployment_clustera.metadata.name and returns that so it can be updated.
        :param deployment_clustera:
        :return:
        '''
        job = copy.deepcopy(job_to_copy)
        create_job = self.create_job(job)
        return create_job

    def update_deployment(self, deployment):
        '''
        Update deployment example https://github.com/kubernetes-client/python/blob/master/examples/deployment_crud.py
        :param deployment:
        :return:
        '''
        return self.AppsV1ApiInstance.patch_namespaced_deployment(
            name=deployment.metadata.name,
            namespace=deployment.metadata.namespace,
            body=deployment)

    def increment_replica(self, deploy):
        deploy.spec.replicas += 1
        self.update_deployment(deploy)

    def decrement_replica(self, deploy):
        deploy.spec.replicas -= 1
        self.update_deployment(deploy)

    def get_mcs_policy(self):
        '''
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CustomObjectsApi.md
        :return:
        '''
        group = 'mcs.james.com'
        version = 'v1'
        namespace = 'mcs'
        plural = 'scalingpolicies'
        name = 'test-scaling-policy'
        return self.CustomApiInstance.get_namespaced_custom_object(group, version, namespace, plural, name)

    def get_mcs_clusters(self):
        '''
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CustomObjectsApi.md
        :return:
        '''
        group = 'mcs.james.com'
        version = 'v1'
        namespace = 'mcs'
        plural = 'mcsclusters'
        return self.CustomApiInstance.list_namespaced_custom_object(group, version, namespace, plural)

    def create_mcs_clusters(self, body):
        '''
        https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CustomObjectsApi.md
        :return:
        '''
        group = 'mcs.james.com'
        version = 'v1'
        namespace = 'mcs'
        plural = 'mcsclusters'
        return self.CustomApiInstance.create_namespaced_custom_object(group, version, namespace, plural, body)

