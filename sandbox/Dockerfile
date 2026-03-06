FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap curl wget python3 python3-pip git \
    netcat-openbsd whois dnsutils traceroute \
    iputils-ping net-tools tcpdump \
    jq vim less file \
    sqlmap hydra gobuster \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir httpx requests 2>/dev/null || true

COPY netkitx /usr/local/bin/netkitx
RUN chmod +x /usr/local/bin/netkitx

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /home/user
RUN useradd -m -s /bin/bash user

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
