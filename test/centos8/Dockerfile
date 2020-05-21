FROM centos:8

ARG src_path

RUN dnf install -y \
        --enablerepo=HighAvailability \
        --enablerepo=PowerTools \
        # python
        python3 \
        python3-lxml \
        python3-mock \
        python3-pip \
        python3-pycurl \
        python3-pyOpenSSL \
        python3-pyparsing \
        # ruby
        ruby \
        ruby-devel \
        rubygems \
        rubygem-bundler \
        rubygem-test-unit \
        # rubygems dependencies
        gcc \
        gcc-c++ \
        redhat-rpm-config \
        pam-devel \
        libffi-devel \
        # cluster stack
        corosync \
        pacemaker \
        pacemaker-cli \
        fence-agents-scsi \
        fence-agents-apc \
        fence-agents-ipmilan \
        fence-virt \
        booth-site \
        # utils
        findutils \
        git \
        make \
        tar \
        time \
        wget \
        which

COPY . $src_path

# install python packages required for tests and static code analysis checks
RUN make -C $src_path python_static_code_analysis_reqirements

# create bundler config file
RUN make -C $src_path rpm_build/pcsd-bundle-config && \
    mkdir -p $src_path/pcsd/.bundle && \
    mv $src_path/rpm_build/pcsd-bundle-config $src_path/pcsd/.bundle/config

# build ruby gems locally
RUN cd $src_path/pcsd; bundle package && make build_gems_without_bundler
