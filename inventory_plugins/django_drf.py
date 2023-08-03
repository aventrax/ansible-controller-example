from __future__ import absolute_import, division, print_function
from types import resolve_bases

__metaclass__ = type

DOCUMENTATION = r"""
    name: django_drf
    plugin_type: inventory
    short_description: Returns Ansible inventory from a Django DRF
    description: Returns Ansible inventory from a custom app made with Django DRF
    extends_documentation_fragment:
        - constructed
        - inventory_cache
    options:
        plugin:
            description: Name of the plugin
            required: true
            choices: ['django_drf']
        customer_id:
            description: Customer identification number
            required: true
            type: int
        groups:
            description: Uses Jinja2 to construct hosts and groups from patterns
            type: dict
            default: {}
        compose:
            description: List of custom ansible host vars to create from the device object fetched from NetBox
            default: {}
            type: dict
"""

import json
import os
from getpass import getpass
from sys import version as python_version

from ansible.module_utils._text import to_text, to_native
from ansible.module_utils.six.moves.urllib import error as urllib_error
from ansible.module_utils.urls import open_url
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.module_utils.ansible_release import __version__ as ansible_version
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.utils.vars import combine_vars


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "django_drf"

    def _fetch_information(self, url):

        results = None
        cache_key = self.get_cache_key(url)

        # get the user's cache option to see if we should save the cache if it is changing
        user_cache_setting = self.get_option("cache")

        # read if the user has caching enabled and the cache isn't being refreshed
        attempt_to_read_cache = user_cache_setting and self.use_cache

        # attempt to read the cache if inventory isn't being refreshed and the user has caching enabled
        if attempt_to_read_cache:
            try:
                results = self._cache[cache_key]
                need_to_fetch = False
            except KeyError:
                # occurs if the cache_key is not in the cache or if the cache_key expired
                # we need to fetch the URL now
                need_to_fetch = True

        else:
            # not reading from cache so do fetch
            need_to_fetch = True

        try:
            # When we use the cached inventory the token must still be valid, otherwise on the
            # playbook calls to django_drf could fail.
            if self.token:
                self._refresh_token()
        except:
            pass

        if need_to_fetch:
            self.display.v("Fetching: " + url)

            # Refresh if token is not expired
            if not self.token:
                self._get_token()

            try:
                response = open_url(
                    url, headers=self.headers, method="GET", validate_certs=False
                )

            except urllib_error.HTTPError as e:
                if e.code == 403:
                    self.display.display(
                        "Permission denied: {0}. This may impair functionality of the inventory plugin.".format(
                            url
                        ),
                        color="red",
                    )

                raise AnsibleError(to_native(e.fp.read()))

            try:
                raw_data = to_text(response.read(), errors="surrogate_or_strict")
            except UnicodeError:
                raise AnsibleError(
                    "Incorrect encoding of fetched payload from django_drf API."
                )

            try:
                results = json.loads(raw_data)
            except ValueError:
                raise AnsibleError("Incorrect JSON payload: %s" % raw_data)

            # put result in cache if enabled
            if user_cache_setting:
                self._cache[cache_key] = results

        return results["data"] if "data" in results.keys() else results

    def verify_file(self, path):

        self.token = None
        self.tokenfile = os.path.join(os.path.expanduser("~"), ".django_drf-tokenfile")

        # Load token if exists
        if os.path.isfile(self.tokenfile):
            try:
                with open(self.tokenfile, "r") as fh:
                    self.token = json.loads(fh.readline())

            except:
                # Load failed, is the tokenfile corrupted?
                os.remove(self.tokenfile)

        return True

    def get_cache_key(self, path):
        return "{0}_{1}_{2}".format(
            self.NAME, self.customer_id, self._get_cache_prefix(path)
        )

    def _get_token(self):

        token_url = self.api_url + "/token/"

        username = input("Enter username for django_drf: ")
        password = getpass("Password: ")

        data = {"username": username, "password": password}

        try:
            response = open_url(
                token_url,
                headers=self.headers,
                method="POST",
                data=json.dumps(data),
                validate_certs=False,
            )

        except urllib_error.HTTPError as e:
            if e.code == 403:
                self.display.display(
                    "Permission denied: {0}. This may impair functionality of the inventory plugin.".format(
                        token_url
                    ),
                    color="red",
                )

            raise AnsibleError(to_native(e.fp.read()))

        try:
            raw_data = to_text(response.read(), errors="surrogate_or_strict")
        except UnicodeError:
            raise AnsibleError(
                "Incorrect encoding of fetched payload from django_drf API."
            )

        try:
            results = json.loads(raw_data)
        except ValueError:
            raise AnsibleError("Incorrect JSON payload: %s" % raw_data)

        self.token = results
        self.headers.update({"Authorization": "Bearer %s" % self.token["access"]})
        self._save_token()

    def _refresh_token(self):

        refresh_url = self.api_url + "/token/refresh/"

        data = {"refresh": self.token["refresh"]}

        del self.headers['Authorization']

        try:
            response = open_url(
                refresh_url,
                headers=self.headers,
                method="POST",
                data=json.dumps(data),
                validate_certs=False,
            )

        except urllib_error.HTTPError as e:

            if e.code == 401:
                self._get_token()
            
            if e.code == 403:
                self.display.display(
                    "Permission denied: {0}. This may impair functionality of the inventory plugin.".format(
                        refresh_url
                    ),
                    color="red",
                )

            raise AnsibleError(to_native(e.fp.read()))

        try:
            raw_data = to_text(response.read(), errors="surrogate_or_strict")
        except UnicodeError:
            raise AnsibleError(
                "Incorrect encoding of fetched payload from django_drf API."
            )

        try:
            results = json.loads(raw_data)
        except ValueError:
            raise AnsibleError("Incorrect JSON payload: %s" % raw_data)

        self.token["access"] = results["access"]
        self.headers.update({"Authorization": "Bearer %s" % self.token["access"]})
        self._save_token()

    def _save_token(self):
        with open(self.tokenfile, "w") as f:
            f.write(json.dumps(self.token))

    def _test_api(self, url):

        try:
            response = open_url(url, headers=self.headers, validate_certs=False)

        except Exception as e:
            return False

        return True if response.code == 200 else False

    def _fill_host_variables(self, server, hostname):

        self.inventory.set_variable(hostname, "ansible_host", server["ip"])
        self.inventory.set_variable(hostname, "hostname", server["hostname"])
        self.inventory.set_variable(hostname, "server", {
            'id': server['id'],
            'hostname': server["hostname"],
            'ip': server['ip'],
            'description': server['description'],
            'is_manageable': server['is_manageable']
        })
        self.inventory.set_variable(
            hostname,
            "operating_system",
            next(
                x
                for x in self.operating_systems
                if x["id"] == server["operating_system"]
            ),
        )

    def _set_composite_vars(
        self, compose, variables, host, strict=False, fetch_hostvars=True
    ):
        """loops over compose entries to create vars for hosts"""
        if compose and isinstance(compose, dict):
            if fetch_hostvars:
                variables = combine_vars(
                    variables, self.inventory.get_host(host).get_vars()
                )
            for varname in compose:
                try:
                    composite = self._compose(compose[varname], variables)
                except Exception as e:
                    if strict:
                        raise AnsibleError(
                            "Could not set %s for host %s: %s"
                            % (varname, host, to_native(e))
                        )
                    continue
                self.inventory.set_variable(host, varname, composite)

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path)
        self._read_config_data(path=path)
        self.use_cache = cache

        # Config options
        self.plugin = self.get_option("plugin")
        self.customer_id = self.get_option("customer_id")

        # django_drf access
        self.base_url = "https://django_drf.local"
        self.api_url = self.base_url + "/api"
        self.headers = {
            "User-Agent": "ansible %s Python %s"
            % (ansible_version, python_version.split(" ")[0]),
            "Content-type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            self.headers.update({"Authorization": "Bearer %s" % self.token["access"]})

        # Fetch Customer
        url = self.api_url + "/customers/{}/".format(self.customer_id)
        self.customer = self._fetch_information(url)

        # Fetch Operating Systems
        url = self.api_url + "/operating-systems/"
        self.operating_systems = self._fetch_information(url)

        # Fetch Servers
        url = self.api_url + "/servers/?customer_id={}".format(self.customer_id)
        self.servers = self._fetch_information(url)

        # Set global (group: all) variables
        self.inventory.groups["all"].set_variable("django_drf_url", self.base_url)
        self.inventory.groups["all"].set_variable("django_drf_token", self.token["access"])
        self.inventory.groups["all"].set_variable("customer", self.customer)

        strict = self.get_option("strict")

        try:
            # Go over hosts (less var copies)
            for server in self.servers:

                hostname = server["ip"]
                self.inventory.add_host(host=hostname)
                self._fill_host_variables(server=server, hostname=hostname)

                # Composed variables
                self._set_composite_vars(
                    self.get_option("compose"), server, hostname, strict=strict
                )

                # Complex groups based on jinja2 conditionals, hosts that meet the conditional are added to group
                self._add_host_to_composed_groups(
                    self.get_option("groups"), server, hostname, strict=strict
                )

                # Create groups based on variable values and add the corresponding hosts to it
                self._add_host_to_keyed_groups(
                    self.get_option("keyed_groups"), server, hostname, strict=strict
                )

        except Exception as e:
            raise AnsibleParserError(
                "failed to parse %s: %s " % (to_native(path), to_native(e)), orig_exc=e
            )
