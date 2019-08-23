FROM fedora:31

ARG src_path

RUN dnf install -y \
        # python
        python3 \
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
        # find
        findutils

# Specific pylint and tornado version is required
RUN pip3 install pylint==2.3.1 tornado==6.0.3

COPY . $src_path

