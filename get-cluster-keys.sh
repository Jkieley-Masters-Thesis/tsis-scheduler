#!/bin/bash

aws s3 cp s3://thesis-cluster-creation/id_rsa ./cluster-keys/id_rsa
aws s3 cp s3://thesis-cluster-creation/id_rsa.pub ./cluster-keys/id_rsa.pub
aws s3 cp s3://thesis-cluster-creation/kube_config ./cluster-keys/kube_config
aws s3 cp s3://thesis-cluster-creation/ip-address.txt ./cluster-keys/ip-address.txt
