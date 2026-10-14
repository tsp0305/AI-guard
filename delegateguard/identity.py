"""Agent identities: one Ed25519 keypair per agent, plus a public-key registry."""
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.exceptions import InvalidSignature


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def unb64(s: str) -> bytes:
    return base64.b64decode(s.encode())


class Identity:
    def __init__(self, name: str, private_key=None):
        """Pass PEM bytes from a managed secret provider for stable deployments.
        Omitting the key creates an ephemeral identity for local demos only.
        """
        self.name = name
        if private_key is None:
            self._key = Ed25519PrivateKey.generate()
        else:
            self._key = load_pem_private_key(private_key, password=None)
            if not isinstance(self._key, Ed25519PrivateKey):
                raise ValueError("identity key must be Ed25519")
        self.public = self._key.public_key()

    def sign(self, data: bytes) -> str:
        return b64(self._key.sign(data))


class Registry:
    """Maps agent name -> public key. Stands in for a PKI / SPIFFE trust bundle."""
    def __init__(self):
        self._pub = {}

    def register(self, ident: Identity):
        self._pub[ident.name] = ident.public

    def register_public(self, name: str, public_key):
        """Register a trusted Ed25519 public key from the deployment trust bundle."""
        self._pub[name] = public_key

    def verify(self, name: str, data: bytes, sig_b64: str) -> bool:
        pub = self._pub.get(name)
        if pub is None:
            return False
        try:
            pub.verify(unb64(sig_b64), data)
            return True
        except (InvalidSignature, ValueError):
            return False
