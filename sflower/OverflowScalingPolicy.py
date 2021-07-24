import concurrent
import logging
import math
import os
import sys
import threading

from pclusterutils import ExecuteUtil
from sflower import Clusters
from datetime import datetime
from time import time


# todo: move trained models back to the on-prem cluster
# can be done in workload deployer, before deploying a training job, check both clusters for the most up-to-date trained model
def overflow_scale_policy():
    f_cluster = Clusters.get_scale_from_cluster()
    pending_pods, is_cluster_overwhelmed_bool = is_cluster_overwhelmed(f_cluster)
    if is_cluster_overwhelmed_bool:
        if os.environ['CLUSTER_IS_CREATED'] != "1":
            Clusters.create_scale_to_cluster(pending_pods, 1.0)
            start_scale_watcher()
            start_miss_scheduled_resolver()
        else:  # these two conditional are mutually exclusive, either one runs or the other, both should not be run
            if os.environ['CLUSTER_FILES_ARE_DOWNLOADED'] != "1":
                # todo: for naive overflow baseline, cluster is created ahead of time
                Clusters.get_cluster_files_and_set_vars()

                # todo: do not do the two below, when doing naive
                if 'NAIVE_EXP' not in os.environ:
                    start_scale_watcher()
                    start_miss_scheduled_resolver()

        # cluster creation takes on avg 8mins, alot can change in 8mins and we should refetch the pending pods
        # before we proceed.
        pending_pods, is_cluster_overwhelmed_bool = is_cluster_overwhelmed(f_cluster)

        # Clusters.copy_aws_to_cluster_data()
        t_clusters = Clusters.get_scale_to_cluster()
        pending_jobs = get_jobs_from_pods(f_cluster, pending_pods)

        spread_jobs(pending_jobs, f_cluster, t_clusters, 1.0)


def is_cluster_overwhelmed(cluster):
    pending_pods = cluster.get_pending_pods()
    pending_pod_len = len(pending_pods)
    is_cluster_overwhelmed_bool = pending_pod_len > 0

    logging.info("pending_pods len: " + str(pending_pod_len))
    logging.info("is_cluster_overwhelmed_bool: " + str(is_cluster_overwhelmed_bool))

    return pending_pods, is_cluster_overwhelmed_bool


def start_miss_scheduled_resolver():
    logging.info("starting")
    threading.Timer(5, miss_scheduled_resolver).start()


def miss_scheduled_resolver():
    logging.info("starting")
    miss_scheduled_resolve_action()
    threading.Timer(5, miss_scheduled_resolver).start()


def miss_scheduled_resolve_action():
    logging.info("starting")
    t_clusters = Clusters.get_scale_to_cluster()
    pods = t_clusters.get_failed_pods()
    logging.info("failed pod len: " + str(pods))
    for pod in pods:
        t_clusters.delete_pod(pod)


def start_scale_watcher():
    logging.info("starting scale watcher in 60 seconds")
    threading.Timer(60, scale_watcher).start()


def scale_watcher():
    logging.info("scale watcher has started")
    check_if_scaling_is_needed()
    threading.Timer(60, scale_watcher).start()


def check_if_scaling_is_needed():
    t_clusters = Clusters.get_scale_to_cluster()
    logging.info("check if scale to cluster is overwhelmed")
    pending_pods, is_cluster_overwhelmed_bool = is_cluster_overwhelmed(t_clusters)
    if is_cluster_overwhelmed_bool:
        response_json = Clusters.trigger_circle_ci_tsis_scale_cluster()
        Clusters.wait_for_workload_complete(response_json['id'])


def move_load_to_from(deployment_clustera, clustera_client, clusterb_client):
    deployment_clusterb = clusterb_client.duplicate_deployment(deployment_clustera)
    clusterb_client.increment_replica(deployment_clusterb)
    clustera_client.decrement_replica(deployment_clustera)


def onschedule_cheapest_cluster():
    # are there any mcs-deployments, that have not been scheduled (cluster attribute is not populated)?
    clusters = Clusters.get_scale_to_clusters()  # get clusters crds
    if Clusters.scale_to_cluster_exists(clusters):  # checks if crds exist
        scale_to_cluster, scale_to_crd = Clusters.get_scale_to_cluster(clusters)
        description = Clusters.get_cluster_description(scale_to_crd)
        logging.info("scale to cluster already exists: " + description)
    else:
        logging.info("creating scale to cluster")
        clusters = Clusters.create_scale_to_cluster_cheapest_by_instance_region()

    # spread_deployments(cluster_scale_from, clusters, pending_pods, pod_mapping)
    return None


def spread_jobs(pending_jobs, f_cluster, t_clusters, percent_to_move):
    move_jobs(f_cluster, pending_jobs, t_clusters, percent_to_move)


def move_jobs(f_cluster, pending_jobs, t_clusters, percent_to_move):
    pending_jobs_len = len(pending_jobs)
    number_of_pods_to_move = math.ceil(pending_jobs_len * percent_to_move)
    move_cursor = 0

    logging.info("pending_jobs_len: " + str(pending_jobs_len))
    logging.info("number_of_pods_to_move: " + str(number_of_pods_to_move))
    logging.info("move_cursor: " + str(move_cursor))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(move_single_job, f_cluster, move_cursor, number_of_pods_to_move, pending_jobs[x],
                            t_clusters)
            for x in range(0, pending_jobs_len)]
        results = [f.result() for f in futures]

    logging.info("results: " + str(len(results)))


def move_single_job(f_cluster, move_cursor, number_of_pods_to_move, job, t_clusters):
    if move_cursor < number_of_pods_to_move:
        logging.info("move_cursor: " + str(move_cursor) + ", moving job to cluster: " + job.metadata.name)

        t_clusters.duplicate_job(job)
        f_cluster.delete_job(job)
        f_cluster.delete_pods_from_job(job)  # this is critical
        logging.info("successfully moved job: move_cursor: " + str(
            move_cursor) + ", moving job to cluster: " + job.metadata.name)
    else:
        logging.info("move_cursor: " + str(move_cursor) + ", job staying queued: " + job.metadata.name)
    move_cursor = move_cursor + 1


def get_env_by_key(env_key, job):
    for env in job.spec.template.spec.containers[0].env:
        if env.name == env_key:
            return env

    raise Exception("unable to find environment key: " + env_key + " for job: " + job.metadata.name)


def get_jobs_from_pods(scale_from_cluster, pending_pods):
    logging.info("pending pods")
    pods_by_job_name = {}
    for pending_pod in pending_pods:
        pods_by_job_name[pending_pod.metadata.labels['job-name']] = ''

    pending_jobs = []
    jobs = scale_from_cluster.get_jobs()
    for job in jobs:
        # pending pod matches job
        if job.metadata.name in pods_by_job_name:
            pending_jobs.append(job)
    return pending_jobs
