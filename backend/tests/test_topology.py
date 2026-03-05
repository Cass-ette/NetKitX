"""Tests for topology service."""

from app.services.topology_service import build_topology


class TestBuildTopology:
    def test_empty_result(self):
        assert build_topology(None) == {"nodes": [], "edges": []}
        assert build_topology({}) == {"nodes": [], "edges": []}
        assert build_topology({"items": []}) == {"nodes": [], "edges": []}

    def test_single_host(self):
        result = {
            "items": [
                {"host": "10.0.0.1", "port": 22, "service": "ssh"},
                {"host": "10.0.0.1", "port": 80, "service": "http"},
            ]
        }
        topo = build_topology(result)

        assert len(topo["nodes"]) == 2  # scanner + 1 host
        assert len(topo["edges"]) == 1

        scanner = next(n for n in topo["nodes"] if n["type"] == "scanner")
        assert scanner["data"]["total_results"] == 2

        host = next(n for n in topo["nodes"] if n["type"] == "host")
        assert host["label"] == "10.0.0.1"
        assert 22 in host["data"]["ports"]
        assert 80 in host["data"]["ports"]
        assert "ssh" in host["data"]["services"]
        assert "http" in host["data"]["services"]

    def test_multiple_hosts(self):
        result = {
            "items": [
                {"host": "10.0.0.1", "port": 22, "service": "ssh"},
                {"host": "10.0.0.2", "port": 80, "service": "http"},
                {"host": "10.0.0.3", "port": 443, "service": "https"},
            ]
        }
        topo = build_topology(result)

        assert len(topo["nodes"]) == 4  # scanner + 3 hosts
        assert len(topo["edges"]) == 3

    def test_ip_field_alias(self):
        result = {"items": [{"ip": "192.168.1.1", "port": 8080}]}
        topo = build_topology(result)
        assert len(topo["nodes"]) == 2
        host = next(n for n in topo["nodes"] if n["type"] == "host")
        assert host["label"] == "192.168.1.1"

    def test_address_field_alias(self):
        result = {"items": [{"address": "172.16.0.1", "port": 3306, "service": "mysql"}]}
        topo = build_topology(result)
        host = next(n for n in topo["nodes"] if n["type"] == "host")
        assert host["label"] == "172.16.0.1"
        assert "mysql" in host["data"]["services"]

    def test_dedup_ports_services(self):
        result = {
            "items": [
                {"host": "10.0.0.1", "port": 80, "service": "http"},
                {"host": "10.0.0.1", "port": 80, "service": "http"},
            ]
        }
        topo = build_topology(result)
        host = next(n for n in topo["nodes"] if n["type"] == "host")
        assert host["data"]["ports"] == [80]
        assert host["data"]["services"] == ["http"]

    def test_items_without_host_skipped(self):
        result = {"items": [{"status": "up"}, {"host": "10.0.0.1", "port": 22}]}
        topo = build_topology(result)
        assert len(topo["nodes"]) == 2  # scanner + 1 host

    def test_edge_ids_unique(self):
        result = {
            "items": [
                {"host": "10.0.0.1", "port": 22},
                {"host": "10.0.0.2", "port": 80},
            ]
        }
        topo = build_topology(result)
        edge_ids = [e["id"] for e in topo["edges"]]
        assert len(edge_ids) == len(set(edge_ids))
