from netbox.api.authentication import TokenPermissions


class TokenWriteOnlyPermission(TokenPermissions):
    """Enforce token write-ability for unsafe methods without mapping POST to a model permission.

    The custom generate/reset actions are gated by explicit permission checks in the action itself,
    so the stock POST -> add_<model> requirement (add_maintenance, add_preparednotification) would be
    wrong for them. Unlike TokenWritePermission this tolerates session and non-token authentication.
    """

    perms_map = {**TokenPermissions.perms_map, "POST": []}
