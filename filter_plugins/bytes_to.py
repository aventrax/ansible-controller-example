from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from ansible.module_utils._text import to_text, to_native
from ansible.errors import AnsibleFilterError


def bytes_to_gb(value):

    try:
        return round(value / 1024 / 1024 / 1024)

    except Exception as e:
        raise AnsibleFilterError(to_native(e))

def bytes_to_mb(value):

    try:
        return round(value / 1024 / 1024)

    except Exception as e:
        raise AnsibleFilterError(to_native(e))


class FilterModule(object):

    def filters(self):
        return {
            'bytes_to_gb': bytes_to_gb,
            'bytes_to_mb': bytes_to_mb,
        }
