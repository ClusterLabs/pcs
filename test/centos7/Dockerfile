FROM centos:7

ARG src_path

# enable EPEL repo, we need python-mock
RUN yum install -y epel-release

RUN yum install -y \
        # python
        python \
        python-devel \
        python-lxml \
        python-mock \
        python-pycurl \
        # ruby
        ruby \
        rubygems \
        ruby-devel \
        rubygem-bundler \
        rubygem-json \
        rubygem-minitest \
        # rubygems dependencies
        gcc \
        gcc-c++ \
        coreutils \
        redhat-rpm-config \
        wget \
        pam-devel \
        libffi-devel \
        # cluster stack
        corosync \
        pacemaker \
        pacemaker-cli \
        fence-agents-scsi \
        fence-agents-apc \
        fence-agents-ilo2 \
        fence-agents-ipmilan \
        fence-agents-compute \
        fence-virt \
        booth-site

COPY . $src_path

# build ruby gems
RUN cd $src_path/pcsd; make build_gems
