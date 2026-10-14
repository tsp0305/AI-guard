"""Local UI demo. Uses ephemeral identities, a simulated brain, and mock tools."""
from .api import create_app
from .system import HelpdeskSystem, SimulatedBrain

_demo_system = HelpdeskSystem(mode="delegateguard", brain=SimulatedBrain(p=1.0))
app = create_app(_demo_system.gw, demo_system=_demo_system)
