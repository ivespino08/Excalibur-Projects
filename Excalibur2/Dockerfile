# Excalibur Docker Image
# Lightweight penetration testing environment with Excalibur

FROM ubuntu:24.04

LABEL description="Excalibur - AI-Powered Penetration Testing Agent"
LABEL version="1.0.0"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Update and install system dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    # Build essentials
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    # Python
    python3.12 \
    python3-pip \
    python3-venv \
    python3-dev \
    # Essential pentesting tools
    nmap \
    netcat-openbsd \
    curl \
    wget \
    git \
    sudo \
    unzip \
    # Network utilities
    net-tools \
    dnsutils \
    whois \
    # VPN (for HackTheBox/TryHackMe connectivity)
    openvpn \
    # Text processing
    jq \
    ripgrep \
    # Terminal
    tmux \
    && apt-get autoremove -y \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/*

# Install additional security/pentesting tools
RUN apt-get update && \
    apt-get install -y \
    # Web fuzzing/brute-forcing
    gobuster \
    dirb \
    # Web vulnerability scanning
    nikto \
    whatweb \
    # SQL injection
    sqlmap \
    # Credential attacks
    hydra \
    john \
    # Network scanning
    masscan \
    # SMB/Samba enumeration -- enum4linux itself is NOT an apt package on
    # Ubuntu (only Kali packages it); these are its real dependencies
    # (nmblookup/smbclient from smbclient, net/rpcclient from
    # samba-common-bin). enum4linux.pl itself is git-cloned below.
    smbclient \
    samba-common-bin \
    # Network analysis
    tcpdump \
    # Additional utilities
    sshpass \
    proxychains4 \
    socat \
    # Ruby + native-extension build deps (evil-winrm gem needs these for nokogiri)
    ruby-full \
    ruby-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libssl-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install ffuf (architecture-aware)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then FFUF_ARCH="linux_amd64"; \
    elif [ "$ARCH" = "arm64" ]; then FFUF_ARCH="linux_arm64"; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    wget -q "https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_${FFUF_ARCH}.tar.gz" -O /tmp/ffuf.tar.gz && \
    tar -xzf /tmp/ffuf.tar.gz -C /tmp && \
    mv /tmp/ffuf /usr/local/bin/ && \
    chmod +x /usr/local/bin/ffuf && \
    rm /tmp/ffuf.tar.gz

# Download common wordlists from SecLists with retry logic
# Falls back gracefully if downloads fail (users can download manually)
RUN mkdir -p /usr/share/wordlists && \
    (curl -fsSL --retry 3 --retry-delay 5 \
        "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt" \
        -o /usr/share/wordlists/common.txt || echo "Warning: Failed to download common.txt") && \
    (curl -fsSL --retry 3 --retry-delay 5 \
        "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/raft-medium-directories.txt" \
        -o /usr/share/wordlists/raft-medium-directories.txt || echo "Warning: Failed to download raft-medium-directories.txt") && \
    (curl -fsSL --retry 3 --retry-delay 5 \
        "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10-million-password-list-top-10000.txt" \
        -o /usr/share/wordlists/top-10000-passwords.txt || echo "Warning: Failed to download top-10000-passwords.txt")

# Install linpeas for Linux privilege escalation enumeration (uploaded to and
# run on compromised Linux targets, not executed inside this container).
RUN mkdir -p /opt/peass && \
    wget -q https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -O /opt/peass/linpeas.sh && \
    chmod +x /opt/peass/linpeas.sh

# Install Metasploit Framework via the official Rapid7 installer (adds the
# apt.metasploit.com repo and installs msfconsole + friends).
RUN curl -fsSL https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb \
        -o /tmp/msfinstall && \
    chmod 755 /tmp/msfinstall && \
    /tmp/msfinstall && \
    rm -f /tmp/msfinstall

# Install exploitdb (provides `searchsploit`) as the fallback exploit-lookup
# source for the excalibur-exploit_lookup skill, alongside msfconsole's
# built-in `search` command.
#
# NOTE: `exploitdb` is NOT an Ubuntu apt package -- it's Kali-only (same
# situation as enum4linux above). The project's own docs say non-Kali users
# should git-clone the upstream repo and add it to PATH, rather than
# symlinking the searchsploit script elsewhere, since it locates its CSV/
# database files relative to its own script location.
# Staleness of the cloned snapshot is an accepted tradeoff here (an
# operator can `searchsploit -u` manually -- not something to run
# mid-engagement).
RUN git clone --depth 1 https://github.com/offensive-security/exploitdb.git /opt/exploitdb
ENV PATH="/opt/exploitdb:${PATH}"

# Install single-binary Go-based tools (architecture-aware): nuclei
# (template CVE/misconfig scanner), feroxbuster (recursive web content
# discovery), chisel (HTTP tunneling for pivoting), kerbrute (Kerberos user
# enumeration/password spraying).
#
# NOTE: this used to hardcode each tool's download URL/filename directly,
# but 3 of the 4 were wrong: nuclei was pinned to a stale v3.3.9 tag that no
# longer exists as a release, feroxbuster's actual release assets are .zip
# (not .tar.gz), and chisel's asset filename embeds its version number
# (e.g. chisel_1.11.8_linux_amd64.gz) rather than being version-less. Only
# kerbrute's plain kerbrute_linux_amd64 filename was actually right. Given
# that hit rate, resolving the real asset URL via the GitHub API (like the
# AD-tools block below already does) is safer than hand-guessing a filename
# per repo, and self-heals as each project's releases change over time.
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then GOARCH="amd64"; FEROX_ARCH="x86_64"; \
    elif [ "$ARCH" = "arm64" ]; then GOARCH="arm64"; FEROX_ARCH="aarch64"; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    gh_asset() { \
        curl -fsSL "https://api.github.com/repos/$1/releases/latest" \
        | jq -r --arg pat "$2" '.assets[] | select(.name | test($pat)) | .browser_download_url' \
        | head -n1; \
    } && \
    # nuclei -- asset e.g. nuclei_3.5.1_linux_amd64.zip
    url=$(gh_asset "projectdiscovery/nuclei" "_linux_${GOARCH}\\.zip$") && \
    curl -fsSL "$url" -o /tmp/nuclei.zip && \
    unzip -q /tmp/nuclei.zip -d /tmp/nuclei && \
    mv /tmp/nuclei/nuclei /usr/local/bin/ && \
    chmod +x /usr/local/bin/nuclei && \
    rm -rf /tmp/nuclei.zip /tmp/nuclei && \
    # feroxbuster -- asset e.g. x86_64-linux-feroxbuster.zip
    url=$(gh_asset "epi052/feroxbuster" "^${FEROX_ARCH}-linux-feroxbuster\\.zip$") && \
    curl -fsSL "$url" -o /tmp/ferox.zip && \
    unzip -q /tmp/ferox.zip -d /tmp && \
    mv /tmp/feroxbuster /usr/local/bin/ && \
    chmod +x /usr/local/bin/feroxbuster && \
    rm -f /tmp/ferox.zip && \
    # chisel -- asset e.g. chisel_1.11.8_linux_amd64.gz (version embedded)
    url=$(gh_asset "jpillora/chisel" "_linux_${GOARCH}\\.gz$") && \
    curl -fsSL "$url" -o /tmp/chisel.gz && \
    gunzip /tmp/chisel.gz && \
    mv /tmp/chisel /usr/local/bin/chisel && \
    chmod +x /usr/local/bin/chisel && \
    # kerbrute
    wget -q "https://github.com/ropnop/kerbrute/releases/latest/download/kerbrute_linux_${GOARCH}" -O /usr/local/bin/kerbrute && \
    chmod +x /usr/local/bin/kerbrute

# Install pip-distributed offensive tools (impacket, ldapdomaindump, wfuzz).
# Requires the EXTERNALLY-MANAGED marker removed (below) so system pip works
# in this container.
#
# NOTE: deliberately NOT installing PyPI's "crackmapexec" package here --
# it's unmaintained since 2024 and its cme/loaders/protocol_loader.py does
# `import imp`, a stdlib module removed in Python 3.12 (the exact Python
# version this image uses), so it would install successfully and then fail
# at every invocation. See the pipx/NetExec block below instead.
RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED && \
    pip install --no-cache-dir --break-system-packages --ignore-installed \
        impacket \
        ldapdomaindump \
        wfuzz && \
    # impacket's wheel only ships the importable library, not the
    # examples/*.py scripts as callable commands -- clone just the scripts
    # and symlink them to match the exact "impacket-{script}" naming (with
    # the .py suffix included, since {script} in the tool interface's
    # choices list already carries it) that credential_attacks.py's
    # command_template calls.
    git clone --depth 1 --filter=blob:none --sparse https://github.com/fortra/impacket.git /tmp/impacket-src && \
    (cd /tmp/impacket-src && git sparse-checkout set examples) && \
    mkdir -p /opt/impacket-scripts && \
    cp /tmp/impacket-src/examples/*.py /opt/impacket-scripts/ && \
    rm -rf /tmp/impacket-src && \
    for f in secretsdump psexec wmiexec smbexec atexec dcomexec \
             GetNPUsers GetUserSPNs getTGT getST smbclient mssqlclient ntlmrelayx; do \
        printf '#!/bin/sh\nexec python3 /opt/impacket-scripts/%s.py "$@"\n' "$f" \
            > "/usr/local/bin/impacket-${f}.py"; \
        chmod +x "/usr/local/bin/impacket-${f}.py"; \
    done && \
    chmod -R a+rX /opt/impacket-scripts

# NetExec (actively-maintained fork of crackmapexec) via pipx, kept in its
# own isolated venv so its pinned impacket dependency can't collide with the
# impacket version installed system-wide above. PIPX_HOME/PIPX_BIN_DIR are
# set so the shim lands in a location every user (not just root, who's
# running this build stage) can reach.
#
# NOTE: NetExec is NOT published to plain PyPI under the name "netexec" --
# `pipx install netexec` fails with "from versions: none" because no such
# PyPI package exists (the Kali *apt* package happens to share that name,
# which is a different install path). The project's own docs install
# straight from the GitHub repo instead.
#
# NOTE: one of NetExec's dependencies, `aardwolf`, builds a Rust extension
# from source, and Ubuntu's apt-packaged rustc is too old for it -- NetExec's
# own official Dockerfile installs Rust via rustup for exactly this reason,
# so we do the same here rather than relying on apt's rustc. The toolchain
# is removed again afterward since nothing needs it at runtime.
ENV PIPX_HOME=/opt/pipx
ENV PIPX_BIN_DIR=/usr/local/bin
RUN apt-get update && apt-get install -y pipx && rm -rf /var/lib/apt/lists/* && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal && \
    . /root/.cargo/env && \
    pipx install git+https://github.com/Pennyw0rth/NetExec && \
    ln -sf /usr/local/bin/nxc /usr/local/bin/crackmapexec && \
    chmod -R a+rX /opt/pipx && \
    rustup self uninstall -y

# Install evil-winrm (Ruby gem; needs the ruby-dev/nokogiri build deps
# installed in the apt block above).
RUN gem install evil-winrm --no-document

# Install commix and Responder from source (not packaged for apt/pip).
# Responder ships as Responder.py, not a "responder" command, so wrap it to
# match network_exploitation.py's command_template (which calls "responder").
RUN git clone --depth 1 https://github.com/commixproject/commix.git /opt/commix && \
    ln -s /opt/commix/commix.py /usr/local/bin/commix && \
    chmod +x /opt/commix/commix.py && \
    git clone --depth 1 https://github.com/lgandx/Responder.git /opt/responder && \
    printf '#!/bin/sh\nexec python3 /opt/responder/Responder.py "$@"\n' > /usr/local/bin/responder && \
    chmod +x /usr/local/bin/responder && \
    chmod -R a+rX /opt/commix /opt/responder

# Install enum4linux (classic Perl version) from its actual upstream --
# there is no Ubuntu apt package for it (only Kali packages it). Depends
# on smbclient/samba-common-bin, installed above.
RUN git clone --depth 1 https://github.com/CiscoCXSecurity/enum4linux.git /opt/enum4linux && \
    ln -s /opt/enum4linux/enum4linux.pl /usr/local/bin/enum4linux && \
    chmod +x /opt/enum4linux/enum4linux.pl && \
    chmod -R a+rX /opt/enum4linux

# Fetch Windows/AD offensive binaries and scripts for upload to compromised
# Windows/AD targets (same pattern as linpeas above -- these run on the
# target, not inside this container). GitHub release asset filenames are
# version-suffixed for several of these, so resolve them via the GitHub API
# (jq is already installed) rather than guessing a "latest/download/<name>"
# URL.
RUN mkdir -p /opt/ad-tools && \
    gh_asset() { \
        curl -fsSL "https://api.github.com/repos/$1/releases/latest" \
        | jq -r --arg pat "$2" '.assets[] | select(.name | test($pat)) | .browser_download_url' \
        | head -n1; \
    } && \
    # SharpHound (BloodHound collector) -- current maintained repo is
    # SpecterOps/SharpHound (formerly BloodHoundAD/SharpHound).
    url=$(gh_asset "SpecterOps/SharpHound" "\\.zip$") && \
    curl -fsSL "$url" -o /tmp/sharphound.zip && unzip -q /tmp/sharphound.zip -d /opt/ad-tools/sharphound && rm -f /tmp/sharphound.zip && \
    # Rubeus / Seatbelt -- GhostPack explicitly does not publish compiled
    # binary releases ("we are not planning on releasing binaries, build
    # them yourself"), so pull from the community-maintained compiled-
    # binaries mirror instead of the (empty) GhostPack releases API.
    curl -fsSL "https://github.com/r3motecontrol/Ghostpack-CompiledBinaries/raw/master/Rubeus.exe" -o /opt/ad-tools/Rubeus.exe && \
    curl -fsSL "https://github.com/r3motecontrol/Ghostpack-CompiledBinaries/raw/master/Seatbelt.exe" -o /opt/ad-tools/Seatbelt.exe && \
    # mimikatz
    url=$(gh_asset "gentilkiwi/mimikatz" "trunk\\.zip$") && \
    curl -fsSL "$url" -o /tmp/mimikatz.zip && unzip -q /tmp/mimikatz.zip -d /opt/ad-tools/mimikatz && rm -f /tmp/mimikatz.zip && \
    # winPEAS (same PEASS-ng repo as linpeas)
    curl -fsSL "https://github.com/peass-ng/PEASS-ng/releases/latest/download/winPEASx64.exe" -o /opt/ad-tools/winPEASx64.exe && \
    # PingCastle -- project moved from vletoux/pingcastle to
    # netwrix/pingcastle (Netwrix took over maintenance); the old repo's
    # releases are stale, so point at the actively-maintained one.
    url=$(gh_asset "netwrix/pingcastle" "\\.zip$") && \
    curl -fsSL "$url" -o /tmp/pingcastle.zip && unzip -q /tmp/pingcastle.zip -d /opt/ad-tools/pingcastle && rm -f /tmp/pingcastle.zip && \
    # PowerView (PowerSploit) and ADRecon -- plain scripts, no releases/zips.
    # ADRecon's default branch is "master", not "main".
    curl -fsSL "https://raw.githubusercontent.com/PowerShellMafia/PowerSploit/master/Recon/PowerView.ps1" -o /opt/ad-tools/PowerView.ps1 && \
    curl -fsSL "https://raw.githubusercontent.com/adrecon/ADRecon/master/ADRecon.ps1" -o /opt/ad-tools/ADRecon.ps1 && \
    chmod -R a+rX /opt/ad-tools
# NOTE: this covers SharpHound (the collector, which runs on/uploads to a
# Windows target). BloodHound analysis itself is now BloodHound CE -- a
# Postgres + Neo4j + web-UI stack, not a single binary -- and doesn't fit
# into this image as a drop-in file. If path analysis is needed, run
# BloodHound CE as a separate docker-compose service and feed it the zip
# SharpHound produces.

# Install Node.js v20 (required for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Remove EXTERNALLY-MANAGED marker to allow pip/poetry in Docker
# Also remove system Python packages that conflict with Poetry dependencies.
#
# python3-pygments: rich>=13.7.0 (pyproject.toml) needs a newer pygments than
# Ubuntu's apt-provided one.
#
# python3-packaging / python3-platformdirs / python3-click / python3-colorama
# / python3-psutil / python3-argcomplete / python3-userpath: these came in
# as apt dependencies of pipx itself (installed earlier, for the NetExec
# block) -- Poetry's resolved dependency tree needs newer versions of at
# least packaging and platformdirs than what pipx dragged in, and the same
# "Cannot uninstall X, RECORD file not found... installed by debian"
# conflict surfaced for each one in turn across separate build attempts.
# Removing the whole known-contaminated set at once instead of finding them
# one at a time. NOTE: apt will likely also cascade-remove the pipx package
# itself here, since pipx depends on several of these -- that's fine, pipx
# already did its one job earlier (installing NetExec) and isn't invoked
# again anywhere below.
RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED && \
    apt-get remove -y \
        python3-cryptography \
        python3-pygments \
        python3-packaging \
        python3-platformdirs \
        python3-click \
        python3-colorama \
        python3-psutil \
        python3-argcomplete \
        python3-userpath && \
    apt-get autoremove -y

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install Claude Code Router globally (for OpenRouter support)
RUN npm install -g @musistudio/claude-code-router

# Create non-root user
RUN useradd -m -s /bin/bash pentester && \
    usermod -aG sudo pentester && \
    echo "pentester ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up working directories (including ccr config)
RUN mkdir -p /workspace /app /home/pentester/.claude /home/pentester/.claude-code-router && \
    chown -R pentester:pentester /workspace /app /home/pentester/.claude /home/pentester/.claude-code-router

# Switch to pentester user
USER pentester
WORKDIR /app

# Install Poetry for Python dependency management
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    echo 'export PATH="/home/pentester/.local/bin:$PATH"' >> /home/pentester/.bashrc

ENV PATH="/home/pentester/.local/bin:$PATH"

# Copy project files
COPY --chown=pentester:pentester pyproject.toml README.md /app/
COPY --chown=pentester:pentester excalibur/ /app/excalibur/
COPY --chown=pentester:pentester scripts/entrypoint.sh /home/pentester/entrypoint.sh
COPY --chown=pentester:pentester scripts/ccr-config-template.json /app/scripts/ccr-config-template.json

# Install the composed attack-pattern Agent Skills (kerberoasting,
# full_port_scan, etc.) as user Skills so the Claude Agent SDK discovers
# them automatically (see backend.py's setting_sources=["user"]). Expects
# the build context to contain an agent_skills/ directory holding only the
# excalibur-<name>/ skill folders themselves -- keep convert_to_agent_skills.py
# (or wherever it lives in your repo, e.g. scripts/) out of this directory,
# since anything copied here that isn't a <name>/SKILL.md folder is just
# clutter under ~/.claude/skills/, not a functional problem, but avoid it.
COPY --chown=pentester:pentester agent_skills/ /home/pentester/.claude/skills/

# Install Python dependencies as root to system Python
# Allow pip to override system packages in Docker
ENV PIP_BREAK_SYSTEM_PACKAGES=1
USER root
RUN poetry config virtualenvs.create false && \
    poetry install --only main && \
    chmod +x /home/pentester/entrypoint.sh

# Switch back to pentester user for runtime
USER pentester

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default working directory for penetration tests
WORKDIR /workspace

# Use entrypoint script for auth setup
ENTRYPOINT ["/home/pentester/entrypoint.sh"]

# Default command - interactive bash
# Users can run: excalibur --target X
CMD ["/bin/bash"]
