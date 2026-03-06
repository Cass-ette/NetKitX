"""SSL/TLS Certificate Inspector plugin."""

import ssl
import socket
import datetime
from app.plugins.base import PluginBase, PluginEvent


class Plugin(PluginBase):
    async def execute(self, params: dict):
        target = params.get("target", "").strip().removeprefix("https://").removeprefix("http://").split("/")[0]
        port = int(params.get("port", 443))

        if not target:
            yield PluginEvent(type="error", data={"message": "target is required"})
            return

        yield PluginEvent(type="log", data={"message": f"Connecting to {target}:{port}..."})

        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((target, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
        except ssl.SSLCertVerificationError as e:
            yield PluginEvent(type="log", data={"message": f"Certificate verification failed: {e}"})
            # Retry without verification to still show cert info
            try:
                ctx2 = ssl.create_default_context()
                ctx2.check_hostname = False
                ctx2.verify_mode = ssl.CERT_NONE
                with socket.create_connection((target, port), timeout=10) as sock:
                    with ctx2.wrap_socket(sock, server_hostname=target) as ssock:
                        cert = ssock.getpeercert()
                        cipher = ssock.cipher()
                        version = ssock.version()
            except Exception as e2:
                yield PluginEvent(type="error", data={"message": str(e2)})
                return
        except Exception as e:
            yield PluginEvent(type="error", data={"message": str(e)})
            return

        # Parse dates
        not_before_str = cert.get("notBefore", "")
        not_after_str = cert.get("notAfter", "")
        fmt = "%b %d %H:%M:%S %Y %Z"
        now = datetime.datetime.utcnow()

        try:
            not_after = datetime.datetime.strptime(not_after_str, fmt)
            days_left = (not_after - now).days
            expiry_display = f"{not_after_str} ({days_left}d remaining)" if days_left >= 0 else f"{not_after_str} (EXPIRED {-days_left}d ago)"
        except Exception:
            expiry_display = not_after_str
            days_left = 999

        # Subject
        subject = dict(x[0] for x in cert.get("subject", []))
        cn = subject.get("commonName", "N/A")
        org = subject.get("organizationName", "N/A")

        # Issuer
        issuer = dict(x[0] for x in cert.get("issuer", []))
        issuer_cn = issuer.get("commonName", "N/A")
        issuer_org = issuer.get("organizationName", "N/A")

        # SANs
        sans = [v for t, v in cert.get("subjectAltName", []) if t == "DNS"]
        san_display = ", ".join(sans[:10]) + ("..." if len(sans) > 10 else "") if sans else "N/A"

        # Weak config checks
        warnings = []
        if days_left < 30:
            warnings.append("⚠ Certificate expires soon" if days_left >= 0 else "✗ Certificate EXPIRED")
        if version in ("TLSv1", "TLSv1.1", "SSLv3"):
            warnings.append(f"⚠ Weak protocol: {version}")
        if cipher and cipher[2] and cipher[2] < 128:
            warnings.append(f"⚠ Weak cipher key size: {cipher[2]} bits")

        rows = [
            {"field": "Host", "value": f"{target}:{port}"},
            {"field": "Common Name", "value": cn},
            {"field": "Organization", "value": org},
            {"field": "Issuer", "value": f"{issuer_cn} ({issuer_org})"},
            {"field": "Valid From", "value": not_before_str},
            {"field": "Valid Until", "value": expiry_display},
            {"field": "TLS Version", "value": version or "N/A"},
            {"field": "Cipher Suite", "value": cipher[0] if cipher else "N/A"},
            {"field": "Key Bits", "value": str(cipher[2]) if cipher and cipher[2] else "N/A"},
            {"field": "SANs", "value": san_display},
            {"field": "Serial Number", "value": cert.get("serialNumber", "N/A")},
            {"field": "Warnings", "value": " | ".join(warnings) if warnings else "✓ None"},
        ]

        for row in rows:
            yield PluginEvent(type="result", data=row)
