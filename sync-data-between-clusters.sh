#!/bin/bash

# example ssh config for asu-worker
#
# Host asu-aws-worker
#        HostName 35.161.182.45
#        User root
#        IdentityFile /Users/James.Kieley/git/tsis-scheduler/cluster-keys/id_rsa


while true
do
    echo "Syncing both dirs"
    rsync -ra --progress asu-worker:/to-mount-data-dir/ ~/Desktop/to-mount-data-dir
    rsync -ra --progress ~/Desktop/to-mount-data-dir asu-aws-worker:/to-mount-data-dir
    echo "complete and sleeping..."
    sleep 10
done
