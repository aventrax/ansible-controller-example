from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from ansible.module_utils._text import to_text, to_native
from ansible.errors import AnsibleFilterError


def win_path_join(value):

    try:
        paths = list(map(lambda x: str(x), value))
        fullpath = os.path.join(*paths)
        return fullpath.replace('\\\\', '\\').replace('/', '\\')

    except Exception as e:
        raise AnsibleFilterError(to_native(e))


class FilterModule(object):

    def filters(self):
        return {
            'win_path_join': win_path_join,
        }
