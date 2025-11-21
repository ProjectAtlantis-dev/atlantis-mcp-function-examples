import atlantis
import logging

logger = logging.getLogger("mcp_server")


@visible
async def demo_group(user: str):
    """
    Protection function for demo_group - checks if user is allowed to use protected functions

    This is an example of how to implement custom authorization for @protected functions.
    When a function is decorated with @protected("demo_group"), this function is called
    first to check if the user is authorized. It receives the username and returns True/False.
    """
    await atlantis.client_log("demo_group is checking permission for " + user)

    # Add allowed usernames here - replace with your actual usernames
    allowed_users = ["user123", "user456", "alice", "bob", "admin"]

    if user in allowed_users:
        return True
    else:
        return False
