"""Egress network context manager (Spec B steps 2-4).

EgressNetwork creates an internal-only Docker network + a deny-by-default
tinyproxy sidecar. The eval container routes all outbound HTTPS through the
proxy, which allows CONNECT only to the configured agent API host on port 443.

If proxy setup fails, falls back to open-bridge with egress_enforced=False
and logs a prominent warning. Never sets egress_enforced=True optimistically.
"""
from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import docker
import docker.errors

if TYPE_CHECKING:
    from primer.config import Settings

log = logging.getLogger(__name__)

# Tinyproxy config template (deny-by-default + single host allowlist)
_TINYPROXY_CONF = """\
Port 8888
Listen 0.0.0.0
Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
MaxClients 10
MinSpareServers 1
MaxSpareServers 3
StartServers 2
MaxRequestsPerChild 0
LogLevel Error
FilterDefaultDeny Yes
ConnectPort 443
Filter "/etc/tinyproxy/allow.txt"
"""

_PROXY_PORT = 8888


@dataclass
class EgressInfo:
    """Info about the active egress network / proxy."""
    network_name: str
    proxy_url: str           # e.g. "http://<proxy_container_ip>:8888"
    allowed_host: str        # the single permitted egress host
    enforced: bool           # False ⇒ open-bridge fallback was used


class EgressNetwork:
    """Context manager that creates an isolated internal network + egress proxy.

    Usage:
        with EgressNetwork(config, client) as egress_info:
            # start eval container on egress_info.network_name
            # set HTTPS_PROXY=egress_info.proxy_url

    Teardown is idempotent and defensive (Spec D / Spec B step 12).
    """

    def __init__(self, config: "Settings", client: docker.DockerClient) -> None:
        self._config = config
        self._client = client
        self._network = None
        self._proxy_container = None
        self._network_name = f"primer-internal-{_short_id()}"

    def __enter__(self) -> EgressInfo:
        try:
            return self._setup()
        except Exception as exc:
            log.warning(
                "EgressNetwork setup failed (%s) — falling back to open-bridge. "
                "egress_enforced will be False.", exc
            )
            self._teardown_partial()
            # Return open-bridge fallback info
            return EgressInfo(
                network_name="bridge",
                proxy_url="",
                allowed_host=self._config.primer_agent_api_host,
                enforced=False,
            )

    def __exit__(self, *exc) -> None:
        self._teardown()

    # -------------------------------------------------------------------------

    def _setup(self) -> EgressInfo:
        """Spec B steps 2–4: create internal net + proxy sidecar."""
        allowed_host = self._config.primer_agent_api_host

        # Step 2: Create internal network (internal=True → no external route)
        self._network = self._client.networks.create(
            self._network_name,
            driver="bridge",
            internal=True,
            check_duplicate=True,
        )
        log.debug("created internal network: %s", self._network_name)

        # Step 3: Build + start the tinyproxy sidecar
        # The proxy is the ONLY container also connected to bridge (outbound leg)
        proxy_container = self._start_proxy(allowed_host)
        self._proxy_container = proxy_container

        # Get proxy's IP on the internal network
        proxy_container.reload()
        networks = proxy_container.attrs["NetworkSettings"]["Networks"]
        if self._network_name not in networks:
            raise RuntimeError(
                f"Proxy container not on network {self._network_name}"
            )
        proxy_ip = networks[self._network_name]["IPAddress"]
        if not proxy_ip:
            raise RuntimeError("Could not determine proxy container IP")

        proxy_url = f"http://{proxy_ip}:{_PROXY_PORT}"
        log.debug("proxy IP on internal net: %s → %s", proxy_ip, proxy_url)

        # Wait for proxy to be ready
        _wait_for_proxy(proxy_ip, _PROXY_PORT)

        return EgressInfo(
            network_name=self._network_name,
            proxy_url=proxy_url,
            allowed_host=allowed_host,
            enforced=True,   # Step 11: set True only when 2–4 succeeded
        )

    def _start_proxy(self, allowed_host: str):
        """Start the tinyproxy sidecar on primer-internal + bridge."""
        proxy_image = self._config.proxy_image

        # Build the proxy image if it doesn't exist
        try:
            self._client.images.get(proxy_image)
        except docker.errors.ImageNotFound:
            log.info("proxy image %s not found — building it...", proxy_image)
            _build_proxy_image(self._client, proxy_image)

        # Write allow.txt content (single host)
        allow_txt = allowed_host + "\n"

        container = self._client.containers.run(
            proxy_image,
            detach=True,
            network=self._network_name,
            environment={
                "ALLOW_HOST": allowed_host,
                "TINYPROXY_ALLOW_TXT": allow_txt,
            },
            # Also connect to default bridge for the outbound leg
            # (done via network connect after creation)
            remove=False,
            name=f"primer-proxy-{_short_id()}",
        )

        # Connect proxy to the default bridge for external access
        try:
            bridge_net = self._client.networks.get("bridge")
            bridge_net.connect(container)
        except Exception as exc:
            log.warning("could not connect proxy to bridge: %s", exc)
            # This is a warning not a fatal — proxy may still work on some configs

        return container

    def _teardown(self) -> None:
        """Remove proxy container and network (idempotent)."""
        if self._proxy_container is not None:
            try:
                self._proxy_container.remove(force=True)
                log.debug("removed proxy container")
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                log.warning("proxy container remove failed: %s", exc)
            self._proxy_container = None

        if self._network is not None:
            try:
                self._network.remove()
                log.debug("removed internal network: %s", self._network_name)
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                log.warning("network remove failed: %s", exc)
            self._network = None

    def _teardown_partial(self) -> None:
        """Best-effort cleanup after a failed setup."""
        self._teardown()


def _wait_for_proxy(host: str, port: int, timeout: float = 10.0) -> None:
    """Wait until the proxy TCP port is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.5)
    log.warning("proxy at %s:%d not ready within %.1fs — proceeding anyway", host, port, timeout)


def _short_id() -> str:
    """Generate a short random hex id for naming containers/networks."""
    import os
    return os.urandom(4).hex()


def _build_proxy_image(client: docker.DockerClient, tag: str) -> None:
    """Build the tinyproxy proxy image inline (fallback if pre-built image missing)."""
    import tempfile, os
    from pathlib import Path

    dockerfile = """\
FROM alpine:3.18
RUN apk add --no-cache tinyproxy
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8888
ENTRYPOINT ["/entrypoint.sh"]
"""
    entrypoint = """\
#!/bin/sh
set -e
# Write allow list from env
echo "${ALLOW_HOST}" > /etc/tinyproxy/allow.txt

# Write tinyproxy config
cat > /etc/tinyproxy/tinyproxy.conf << 'EOF'
Port 8888
Listen 0.0.0.0
Timeout 600
MaxClients 10
LogLevel Error
FilterDefaultDeny Yes
ConnectPort 443
Filter "/etc/tinyproxy/allow.txt"
EOF

exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf
"""
    with tempfile.TemporaryDirectory(prefix="primer_proxy_build_") as ctx_dir:
        Path(ctx_dir, "Dockerfile").write_text(dockerfile)
        Path(ctx_dir, "entrypoint.sh").write_text(entrypoint)
        image, logs = client.images.build(path=ctx_dir, tag=tag, rm=True)
        for entry in logs:
            if "stream" in entry:
                log.debug("proxy build: %s", entry["stream"].rstrip())
    log.info("built proxy image: %s", tag)
