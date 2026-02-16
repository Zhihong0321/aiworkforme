# Ensure routers is a package and expose all route modules.
from . import agents, chat, knowledge, mcp, settings  # noqa: F401
from . import analytics, auth, platform, playground, policy, workspaces  # noqa: F401
