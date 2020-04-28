FROM fedora:30

ARG src_path

RUN dnf install -y \
        # python
        python3 \
        python3-distro \
        python3-lxml \
        python3-mock \
        python3-pycurl \
        python3-pyOpenSSL \
        # ruby
        ruby \
        ruby-devel \
        rubygem-bundler \
        rubygem-backports \
        rubygem-ethon \
        rubygem-ffi \
        rubygem-io-console \
        rubygem-json \
        rubygem-open4 \
        rubygem-rack \
        rubygem-rack-protection \
        rubygem-rack-test \
        rubygem-sinatra \
        rubygem-tilt \
        rubygem-test-unit \
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
