from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from ansible.module_utils._text import to_text, to_native
from ansible.errors import AnsibleFilterError


def get_index_of(data, item, filters):

    if not isinstance(data, list) or not isinstance(item, dict) or not isinstance(filters, list):
        return None

    try:
        return  data.index(next(filter(lambda n: all(n.get(f) == item[f] for f in filters), data)))
        
    except Exception as e:
        raise AnsibleFilterError(to_native(e))


class FilterModule(object):

    def filters(self):
        return {
            'get_index_of': get_index_of,
        }
