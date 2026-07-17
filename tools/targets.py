""" Probes the Docker environment and config files to extract information about running services. """
import dataclasses
import os
from pathlib import Path

import docker  # type: ignore
import yaml

# Correspondance entre les noms de services et les ports exposés sur l'hôte
HOST_PORTS = {
    "hyper": 8080,
    "nginx": 8081,
    "gunicorn": 8082,
    "nginx_proxy": 8083,
    "haproxy": 8084,
}

_DEFAULT_SERVER_TIMEOUT: float = 5.0
_DEFAULT_TRANSDUCER_TIMEOUT: float = 1.0

_BASE_DIR = Path(__file__).resolve().parent.parent
_NETWORK_NAME: str = f"{os.path.basename(_BASE_DIR)}_default"

_COMPOSE_YML_PATH = _BASE_DIR / "docker-compose.yml"
_EXTERNAL_YML_PATH = _BASE_DIR / "external-services.yml"
_ANOMALIES_YML_PATH = _BASE_DIR / "anomalies.yml"


@dataclasses.dataclass
class Service:
    """Service (server/proxy) configuration dataclass"""

    name: str
    container: docker.models.containers.Container | None
    address: str
    port: int
    requires_tls: bool
    timeout: float
    is_traced: bool
    dump_count: int
    allows_http_0_9: bool
    added_headers: list[tuple[bytes, bytes]]
    translates_chunked_to_cl: bool
    requires_length_in_post: bool
    allows_missing_host_header: bool
    header_name_translation: dict[bytes, bytes]
    doesnt_support_version: bool
    method_whitelist: list[bytes] | None


def _make_container_dict(network_name: str) -> dict[str, docker.models.containers.Container]:
    """Constructs a dict that maps Docker aliases to their local IPs."""
    try:
        client = docker.from_env()
        network = client.networks.get(network_name)
        if network is None:
            print(f"[DEBUG] Network '{network_name}' not found")
            return {}
        containers = {c.labels["com.docker.compose.service"]: c for c in network.containers}
        print(f"[DEBUG] Found {len(containers)} containers in network '{network_name}'")
        return containers
    except docker.errors.NotFound:
        print(f"[DEBUG] Network '{network_name}' not found (docker.errors.NotFound)")
        return {}
    except Exception as e:
        print(f"[DEBUG] Docker error in _make_container_dict: {e}")
        return {}


def _get_container_ip(container: docker.models.containers.Container, network_name: str) -> str | None:
    if container is None:
        return None
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    # Chercher d'abord dans le réseau spécifié
    if network_name in networks:
        return networks[network_name].get("IPAddress")
    # Sinon, prendre la première IP disponible
    for net in networks.values():
        ip = net.get("IPAddress")
        if ip:
            return ip
    return None


def _extract_services(role: str) -> list[Service]:
    """Returns a list of the running services with the requested role as Service objects."""
    print(f"[DEBUG] Extracting services with role '{role}'")
    print(f"[DEBUG] Compose path: {_COMPOSE_YML_PATH}")
    print(f"[DEBUG] Anomalies path: {_ANOMALIES_YML_PATH}")
    print(f"[DEBUG] External path: {_EXTERNAL_YML_PATH}")

    try:
        with open(_ANOMALIES_YML_PATH, encoding="latin1") as f:
            anomalies_dict: dict = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("[DEBUG] anomalies.yml not found, using empty dict")
        anomalies_dict = {}

    try:
        with open(_COMPOSE_YML_PATH, encoding="latin1") as f:
            services: dict = yaml.safe_load(f).get("services") or {}
    except FileNotFoundError:
        print(f"[DEBUG] {_COMPOSE_YML_PATH} not found")
        services = {}

    try:
        with open(_EXTERNAL_YML_PATH, encoding="latin1") as f:
            external = yaml.safe_load(f) or {}
            services.update(external)
    except FileNotFoundError:
        print("[DEBUG] external-services.yml not found, ignoring")

    print(f"[DEBUG] Total services after merging: {len(services)}")

    result: list[Service] = []
    for svc_name, svc_data in services.items():
        x_props = svc_data.get("x-props") or {}
        if x_props.get("role") != role:
            continue

        container = _CONTAINER_DICT.get(svc_name)
        requires_tls = x_props.get("requires-tls") or False

        # Gestion des ports exposés sur l'hôte
        if svc_name in HOST_PORTS:
            address = "127.0.0.1"
            port = HOST_PORTS[svc_name]
        else:
            address = x_props.get("address") or _get_container_ip(container, _NETWORK_NAME)
            port = x_props.get("port") or (443 if requires_tls else 80)

        if address is None:
            print(f"[DEBUG] Service '{svc_name}' has no address (not running or external without address)")
            continue

        anomalies = anomalies_dict.get(svc_name) or {}
        is_traced = x_props.get("is-traced") or False
        dump_count = 0
        if is_traced:
            try:
                with open(f"/tmp/{svc_name}/dump_count", "rb") as f:
                    dump_count = f.read(1)[0] + 1
            except FileNotFoundError:
                pass

        result.append(
            Service(
                name=svc_name,
                container=container,
                address=address,
                port=port,
                requires_tls=requires_tls,
                timeout=float(
                    x_props.get("timeout")
                    or (_DEFAULT_SERVER_TIMEOUT if role == "server" else _DEFAULT_TRANSDUCER_TIMEOUT)
                ),
                is_traced=is_traced,
                dump_count=dump_count,
                allows_http_0_9=anomalies.get("allows-http-0-9") or False,
                added_headers=[
                    (k.encode("latin1"), v.encode("latin1"))
                    for k, v in (anomalies.get("added-headers") or [])
                ],
                translates_chunked_to_cl=anomalies.get("translates-chunked-to-cl") or False,
                requires_length_in_post=anomalies.get("requires-length-in-post") or False,
                allows_missing_host_header=anomalies.get("allows-missing-host-header") or False,
                header_name_translation={
                    k.encode("latin1"): v.encode("latin1")
                    for k, v in (anomalies.get("header-name-translation") or {}).items()
                },
                doesnt_support_version=anomalies.get("doesnt-support-version") or False,
                method_whitelist=[s.encode("latin1") for s in anomalies.get("method-whitelist") or []]
                or None,
            )
        )

    print(f"[DEBUG] Found {len(result)} services with role '{role}'")
    return result


# Construction du dictionnaire des conteneurs
_CONTAINER_DICT: dict[str, docker.models.containers.Container] = _make_container_dict(_NETWORK_NAME)

SERVER_DICT: dict[str, Service] = {server.name: server for server in _extract_services("server")}
TRANSDUCER_DICT: dict[str, Service] = {t.name: t for t in _extract_services("transducer")}