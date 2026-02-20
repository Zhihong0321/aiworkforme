# Ensure routers is a package and expose all route modules.
from . import agents, chat, knowledge, mcp, settings  # noqa: F401
from . import analytics, auth, messaging, platform, playground, policy, workspaces  # noqa: F401
from . import debug  # noqa: F401
from . import ai_crm  # noqa: F401
