from backend.Keyter import KeyterCarel

BACKENDS = {
    "keyter": {
        "permission_function": KeyterCarel.get_row_permissions,
        "sampling_map": KeyterCarel.SAMPLING_MAP,
        "default_view": {"STATUS": "basic", "ALARM": "simple"}
    }
}