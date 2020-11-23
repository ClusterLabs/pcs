FROM fedora:31

ARG src_path

RUN dnf install -y \
        # python
        python3 \
        python3-lxml \
        python3-pip \
        python3-pycurl \
        python3-pyOpenSSL \
        python3-pyparsing \
        python3-setuptools \
        python3-tornado \
        python3-dateutil \
        python3-distro \
        # ruby
        ruby \
        ruby-devel \
        rubygems \
        rubygem-bundler \
        rubygem-backports \
        rubygem-daemons \
        rubygem-ethon \
        rubygem-ffi \
        rubygem-eventmachine \
        rubygem-json \
        rubygem-mustermann \
        rubygem-open4 \
        rubygem-power_assert \
        rubygem-rack \
        rubygem-rack-protection \
        rubygem-rack-test \
        rubygem-sinatra \
        rubygem-tilt \
        rubygem-test-unit \
        rubygem-thin \
        # cluster stack
        corosync \
        pacemaker \
        pacemaker-cli \
        pacemaker-libs-devel \
        fence-agents-scsi \
        fence-agents-apc \
        fence-agents-ipmilan \
        fence-virt \
        booth-site \
        # utils
        initscripts \
        fontconfig \
        findutils \
        make \
        tar \
        time \
        wget \
        which

COPY . $src_path

# configure and install dependencies not available in the BaseOS
RUN cd $src_path && \
    ./autogen.sh && \
    ./configure --enable-local-build --enable-dev-tests --enable-destructive-tests \
	PCMKEXECPREFIX=/usr \
	PCMKPREFIX=/usr \
	COROLOGDIR=/var/log/corosync \
	COROQDEVEXECPREFIX=/usr \
	COROQDEVCONFDIR=/etc/corosync \
	SBDCONFDIR=/etc/sysconfig \
	SBDEXECPREFIX=/usr \
	FASEXECPREFIX=/usr \
	OCFROOT=/usr/lib/ocf/resource.d \
	RA_API_DTD=/usr/share/resource-agents/ra-api-1.dtd \
	RA_TMP_DIR=/run/resource-agents \
	BOOTHCONFDIR=/etc/booth \
	BOOTHEXECPREFIX=/usr && \
    make check-local-deps
