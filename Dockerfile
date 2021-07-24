FROM python:3.8.10-alpine3.13

WORKDIR /app

# install awscli v2 on alpine
# https://stackoverflow.com/questions/61918972/how-to-install-aws-cli-on-alpine
RUN apk --no-cache add \
    binutils \
    curl \
    && GLIBC_VER=$(curl -s https://api.github.com/repos/sgerrand/alpine-pkg-glibc/releases/latest | grep tag_name | cut -d : -f 2,3 | tr -d \",' ') \
    && curl -sL https://alpine-pkgs.sgerrand.com/sgerrand.rsa.pub -o /etc/apk/keys/sgerrand.rsa.pub \
    && curl -sLO https://github.com/sgerrand/alpine-pkg-glibc/releases/download/${GLIBC_VER}/glibc-${GLIBC_VER}.apk \
    && curl -sLO https://github.com/sgerrand/alpine-pkg-glibc/releases/download/${GLIBC_VER}/glibc-bin-${GLIBC_VER}.apk \
    && apk add --no-cache \
    glibc-${GLIBC_VER}.apk \
    glibc-bin-${GLIBC_VER}.apk \
    && curl -sL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip \
    && unzip awscliv2.zip \
    && aws/install \
    && rm -rf \
    awscliv2.zip \
    aws \
    /usr/local/aws-cli/v2/*/dist/aws_completer \
    /usr/local/aws-cli/v2/*/dist/awscli/data/ac.index \
    /usr/local/aws-cli/v2/*/dist/awscli/examples \
    && apk --no-cache del \
    binutils \
    curl \
    && rm glibc-${GLIBC_VER}.apk \
    && rm glibc-bin-${GLIBC_VER}.apk \
    && rm -rf /var/cache/apk/*

RUN aws --version   # Just to make sure its installed alright

ADD ./requirements.txt /app/requirements.txt
ADD ./asu-ssh-config/jkieley_asu /app/jkieley_asu
ADD ./asu-ssh-config/ssh-config.txt /app/ssh-config.txt
ADD ./asu-ssh-config/prepare-config.sh /app/prepare-config.sh

RUN apk add --update --no-cache openssh
RUN apk add --update --no-cache bash

RUN mkdir /root/.ssh
#RUN echo '127.0.0.1 jamesk-kubernetes-master' >> /etc/hosts

RUN PATH_TO_SSH_KEY=/app/jkieley_asu SRC_FILE=/app/ssh-config.txt OUTPUT_FILE=/root/.ssh/config bash -c '/app/prepare-config.sh'
RUN chmod 400 /app/jkieley_asu

RUN pip install -r requirements.txt

COPY . /app

RUN chmod +x /app/entrypoint-scheduler.sh
RUN cp /app/config/known_hosts /root/.ssh/

ENV FROM_CLUSTER_KUBE_CONFIG_FILE=/app/config/asu-on-prem-config
ENV SAVEDI_JOB_YAML=/app/config/deployment_yamls/savedi_job.yaml
ENV ARPUT_JOB_YAML=/app/config/deployment_yamls/arput_job.yaml
ENV ARPUI_JOB_YAML=/app/config/deployment_yamls/arpui_job.yaml
ENV SAVEDT_JOB_YAML=/app/config/deployment_yamls/savedt_job.yaml
ENV CFDWID_LR_TRAIN_JOB_YAML=/app/config/deployment_yamls/cfdwid_lr_train_job.yaml
ENV CFDWID_LR_INFERENCE_JOB_YAML=/app/config/deployment_yamls/cfdwid_lr_inference_job.yaml


ENTRYPOINT /app/entrypoint-scheduler.sh