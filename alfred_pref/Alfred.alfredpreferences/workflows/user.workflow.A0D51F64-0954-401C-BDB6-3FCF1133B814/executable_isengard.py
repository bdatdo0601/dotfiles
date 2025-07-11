"""Do Isengard stuff"""

import os
import subprocess32 as subprocess


def using_isengardcli():  # type: () -> bool
    """Check if the environment suggests we should be using isengardcli"""
    if _isengardcli_path and len(_isengardcli_path) > 0:
        return True
    return False


def check_valid_mwinit():  # type: () -> bool
    """Check if mwinit cookie looks valid"""
    try:
        result = subprocess.run(
            ["mwinit", "-l"], stdout=subprocess.PIPE, universal_newlines=True
        )
        if result.returncode == 12:
            # present but expired
            return False
        if result.stdout is None or result.stdout.strip() == "":
            # no cookie
            return False
        return True
    except subprocess.SubprocessError:
        # something else went wrong
        return False


def get_isengard_accounts():  # type: () -> list
    return []


_isengardcli_path = os.environ.get("ISENGARDCLI_PATH", None)
if using_isengardcli():
    assert _isengardcli_path is not None  # for type checker
    if _isengardcli_path not in os.environ["PATH"]:
        os.environ["PATH"] = "%s:%s:/usr/local/bin" % (
            os.environ["PATH"],
            _isengardcli_path,
        )
