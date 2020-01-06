#!/usr/bin/env python
"""
PrismCentral external inventory script
======================================

Generates Ansible inventory of PrismCentral AHV VMs.

In addition to the --list and --host options used by Ansible, there are options
for generating JSON of other PrismCentral data. This is useful when creating
VMs. For example, --clusters will return all the PrismCentral Clusters.
This information can also be easily found in the cache file, whose default
location is /tmp/ansible-prism_central.cache).

The --pretty option pretty-prints the output for better human readability.

----
Although the cache stores all the information received from PrismCentral,
the cache is not used for current VM information (in --list, --host,
--all, and --vms). This is so that accurate VM information is always
found. You can force this script to use the cache with --force-cache.

----
Configuration is read from `prism_central.ini`, then from environment variables,
and then from command-line arguments.

Most notably, the PrismCentral IP and Credentials must be specified. It can be specified
in the INI file or with the following environment variables:
    export PC_IP_ADDR='1.2.3.4'
    export PC_USERNAME='user'
    export PC_PASSWORD='password'

Alternatively, it can be passed on the command-line with --ip-addr (-i) --username (-u) --password (-p).

If you specify PrismCentral credentials in the INI file, a handy way to
get them into your environment (e.g., to use the prism_central module)
is to use the output of the --env option with export:
    export $(prism_central.py --env)

----
The following groups are generated from --list:
 - UUID    (VM UUID)
 - NAME  (VM NAME)
 - prism_central
 - cluster_NAME
 - project_NAME
 - owner_NAME
 - hypervisor_NAME
 - status_STATUS
 - category_NAME_VALUES

-----
```
usage: prism_central.py [-h] [--list] [--host HOST] [--all] [--vms]
                        [--clusters] [--projects] [--categories] [--nodes]
                        [--pretty]
                        [--cache-path CACHE_PATH]
                        [--cache-max_age CACHE_MAX_AGE] [--force-cache]
                        [--refresh-cache] [--env] [--ip-addr PC_IP_ADDR]
                        [--username PC_USERNAME] [--password PC_PASSWORD]

Produce an Ansible Inventory file based on PrismCentral credentials

optional arguments:
  -h, --help            show this help message and exit
  --list                List all active VMs as Ansible inventory
                        (default: True)
  --host HOST           Get all Ansible inventory variables about a specific
                        VM
  --all                 List all PrismCentral information as JSON
  --vms, -v             List VMs as JSON
  --clusters            List Clusters as JSON
  --projects            List Projects as JSON
  --categories          List Categories as JSON
  --nodes               List Nodes as JSON
  --pretty              Pretty-print results
  --cache-path CACHE_PATH
                        Path to the cache files (default: .)
  --cache-max_age CACHE_MAX_AGE
                        Maximum age of the cached items (default: 0)
  --force-cache         Only use data from the cache
  --refresh-cache, -r   Force refresh of cache by making API requests to
                        PrismCentral (default: False - use cache files)
  --env, -e             Display PC_IP_ADDR, PC_USERNAME and PC_PASSWORD
  --ip-addr PC_IP_ADDR, -i PC_IP_ADDR
                        PrismCentral IP Address
  --username PC_USERNAME, -u PC_USERNAME
                        PrismCentral Username
  --password PC_PASSWORD, -p PC_PASSWORD
                        PrismCentral Password
```

"""

# (c) 2018, Jose Gomez <jose.gomez@nutanix.com>
#
# Inspired by the DigitalOcean inventory plugin:
# https://raw.githubusercontent.com/ansible/ansible/devel/contrib/inventory/digital_ocean.py

######################################################################


import requests
from requests.auth import HTTPBasicAuth
#prevent insecure warnings
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
# import base64
import socket
import sys
import pprint
import time
import ssl
import argparse
import ast
import os
import re

from time import time

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

import json

# socket timeout in seconds
TIMEOUT = 60
socket.setdefaulttimeout(TIMEOUT)
pp = pprint.PrettyPrinter(indent=4)


class PcManager():

    def __init__(self, ip_addr, username, password):
        # Initialise the options.
        self.ip_addr = ip_addr
        self.username = username
        self.password = password
        self.rest_params_init()

    # Initialize REST API parameters
    def rest_params_init(self, sub_url="", method="",
                         body=None, content_type="application/json", response_file=None):
        self.sub_url = sub_url
        self.body = body
        self.method = method
        self.content_type = content_type
        self.response_file = response_file

    # Create a REST client session.
    def rest_call(self):
        base_url = 'https://%s:9440/api/nutanix/v3/%s' % (
            self.ip_addr, self.sub_url)
        if self.body and self.content_type == "application/json":
            self.body = json.dumps(self.body)
        headers = {
            'Content-Type': '%s; charset=utf-8' % self.content_type,
        }
        #Get de desired action GET/POST/PUT/... from requests module. Return None if not found
        action = getattr(requests, self.method.lower(), None)
        if action:
            #If body None, init default dict
            if not self.body:
                self.body = {}
            #Invoke requests module
            response = action(
                base_url,
                headers=headers,
                auth= HTTPBasicAuth(
                    self.username, 
                    self.password
                ),
                verify=False,
                json=json.loads(self.body)
            )
            #Read status code
            status_code = response.status_code
            response_json = response.json()
            if status_code < 200 or status_code > 299:
                print("Request to {} failed with status code {}. Error: {}".format(
                    base_url, status_code, response_json))
                return status_code, None
            return response_json
        else:
            print("Error: Invalid HTTP method requested %s" % self.method)
            return "400", None

    def list_vms(self):
        body = {
            "length": 15000,
            "offset": 0,
            "filter": ""
        }
        self.rest_params_init(sub_url="vms/list", method="POST", body=body)
        return self.rest_call()

    def list_clusters(self):
        body = {
            "length": 1000,
            "offset": 0,
            "filter": ""
        }
        self.rest_params_init(sub_url="clusters/list", method="POST", body=body)
        return self.rest_call()

    def list_projects(self):
        body = {
            "length": 1000,
            "offset": 0,
            "filter": ""
        }
        self.rest_params_init(sub_url="projects/list", method="POST", body=body)
        return self.rest_call()

    def list_categories(self):
        body = {}
        self.rest_params_init(sub_url="categories/list", method="POST", body=body)
        return self.rest_call()

    def list_nodes(self):
        body = {
            "length": 15000,
            "offset": 0,
            "filter": ""
        }
        self.rest_params_init(sub_url="hosts/list", method="POST", body=body)
        return self.rest_call()

    def get_vm(self, vm_uuid):
        sub_url = 'vms/%s' % vm_uuid
        self.rest_params_init(sub_url=sub_url, method="GET")
        return self.rest_call()

    def search(self, user_query):
        body = {
            "user_query": str(user_query),
            "explicit_query": True,
            "generate_autocompletions_only": True,
            "is_autocomplete_selection": False
        }
        self.rest_params_init(sub_url="search", method="POST", body=body)
        return self.rest_call()

class PrismCentralInventory(object):

    ###########################################################################
    # Main execution path
    ###########################################################################

    def __init__(self):
        """Main execution path """

        # PrismCentralInventory data
        self.data = {}  # All PrismCentral data
        self.inventory = {}  # Ansible Inventory

        # Define defaults
        self.cache_path = '.'
        self.cache_max_age = 0
        self.group_variables = {}

        # Read settings, environment variables, and CLI arguments
        self.read_settings()
        self.read_environment()
        self.read_cli_args()

        # Verify Prism Central IP was set
        if not hasattr(self, 'ip_addr'):
            msg = 'Could not find values for PrismCentral ip_addr. They must be specified via either ini file, ' \
                  'command line argument (--ip-addr, -i), or environment variables (PC_IP_ADDR)\n'
            sys.stderr.write(msg)
            sys.exit(-1)

        # Verify credentials were set
        if not hasattr(self, 'username'):
            msg = 'Could not find values for PrismCentral username. They must be specified via either ini file, ' \
                  'command line argument (--username, -u), or environment variables (PC_USERNAME)\n'
            sys.stderr.write(msg)
            sys.exit(-1)
        if not hasattr(self, 'password'):
            msg = 'Could not find values for PrismCentral password. They must be specified via either ini file, ' \
                  'command line argument (--password, -p), or environment variables (PC_PASSWORD)\n'
            sys.stderr.write(msg)
            sys.exit(-1)

        # env command, show PrismCentral credentials
        if self.args.env:
            print("PC_IP_ADDR=%s" % self.ip_addr)
            print("PC_USERNAME=%s" % self.username)
            print("PC_PASSWORD=%s" % self.password)
            sys.exit(0)

        # Manage cache
        self.cache_filename = self.cache_path + "/ansible-prism_central.cache"
        self.cache_refreshed = False

        if self.is_cache_valid():
            self.load_from_cache()
            if len(self.data) == 0:
                if self.args.force_cache:
                    sys.stderr.write('Cache is empty and --force-cache was specified\n')
                    sys.exit(-1)

        self.manager = PcManager(self.ip_addr, self.username, self.password)

        # Pick the json_data to print based on the CLI command
        if self.args.vms:
            self.load_from_prism_central('vms')
            json_data = {'vms': self.data['vms']}
        elif self.args.clusters:
            self.load_from_prism_central('clusters')
            json_data = {'clusters': self.data['clusters']}
        elif self.args.projects:
            self.load_from_prism_central('projects')
            json_data = {'projects': self.data['projects']}
        elif self.args.categories:
            self.load_from_prism_central('categories')
            json_data = {'categories': self.data['categories']}
        elif self.args.nodes:
            self.load_from_prism_central('nodes')
            json_data = {'nodes': self.data['nodes']}
        elif self.args.all:
            self.load_from_prism_central()
            json_data = self.data
        elif self.args.host:
            json_data = self.load_vm_variables_for_host()
        else:    # '--list' this is last to make it default
            self.load_from_prism_central('vms')
            self.build_inventory()
            json_data = self.inventory

        if self.cache_refreshed:
            self.write_to_cache()

        if self.args.pretty:
            print(json.dumps(json_data, indent=2))
        else:
            print(json.dumps(json_data))

    ###########################################################################
    # Script configuration
    ###########################################################################

    def read_settings(self):
        """ Reads the settings from the prism_central.ini file """
        config = ConfigParser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'prism_central.ini')
        config.read(config_path)

        # Prism Central IP
        if config.has_option('prism_central', 'ip_addr'):
            self.ip_addr = config.get('prism_central', 'ip_addr')
            
        # Credentials
        if config.has_option('prism_central', 'username'):
            self.username = config.get('prism_central', 'username')
        if config.has_option('prism_central', 'password'):
            self.password = config.get('prism_central', 'password')

        # Cache related
        if config.has_option('prism_central', 'cache_path'):
            self.cache_path = config.get('prism_central', 'cache_path')
        if config.has_option('prism_central', 'cache_max_age'):
            self.cache_max_age = config.getint('prism_central', 'cache_max_age')

        # Group variables
        if config.has_option('prism_central', 'group_variables'):
            self.group_variables = ast.literal_eval(config.get('prism_central', 'group_variables'))

    def read_environment(self):
        """ Reads the settings from environment variables """
        # Setup PC IP
        if os.getenv("PC_IP_ADDR"):
            self.ip_addr = os.getenv("PC_IP_ADDR")
        # Setup credentials
        if os.getenv("PC_USERNAME"):
            self.username = os.getenv("PC_USERNAME")
        if os.getenv("PC_PASSWORD"):
            self.password = os.getenv("PC_PASSWORD")

    def read_cli_args(self):
        """ Command line argument processing """
        parser = argparse.ArgumentParser(description='Produce an Ansible Inventory file based on PrismCentral credentials')

        parser.add_argument('--list', action='store_true', help='List all active VMs as Ansible inventory (default: True)')
        parser.add_argument('--host', action='store', help='Get all Ansible inventory variables about a specific VM')

        parser.add_argument('--all', action='store_true', help='List all PrismCentral information as JSON')
        parser.add_argument('--vms', '-v', action='store_true', help='List all PrismCentral VMs as JSON')
        parser.add_argument('--clusters', action='store_true', help='List Clusters as JSON')
        parser.add_argument('--projects', action='store_true', help='List Projects as JSON')
        parser.add_argument('--categories', action='store_true', help='List Categories as JSON')
        parser.add_argument('--nodes', action='store_true', help='List Nodes as JSON')

        parser.add_argument('--pretty', action='store_true', help='Pretty-print results')

        parser.add_argument('--cache-path', action='store', help='Path to the cache files (default: .)')
        parser.add_argument('--cache-max_age', action='store', help='Maximum age of the cached items (default: 0)')
        parser.add_argument('--force-cache', action='store_true', default=False, help='Only use data from the cache')
        parser.add_argument('--refresh-cache', '-r', action='store_true', default=False,
                            help='Force refresh of cache by making API requests to PrismCentral (default: False - use cache files)')

        parser.add_argument('--env', '-e', action='store_true', help='Display PC_IP_ADDR, PC_USERNAME, PC_PASSWORD')
        parser.add_argument('--ip-addr', '-i', action='store', help='PrismCentral IP Address')
        parser.add_argument('--username', '-u', action='store', help='PrismCentral Username')
        parser.add_argument('--password', '-p', action='store', help='PrismCentral Password')



        self.args = parser.parse_args()

        if self.args.ip_addr:
            self.ip_addr = self.args.ip_addr
        if self.args.username:
            self.username = self.args.username
        if self.args.password:
            self.password = self.args.password

        # Make --list default if none of the other commands are specified
        if (not self.args.vms and
                not self.args.all and not self.args.host):
            self.args.list = True

    ###########################################################################
    # Data Management
    ###########################################################################

    def load_from_prism_central(self, resource=None):
        """Get JSON from PrismCentral API """
        if self.args.force_cache and os.path.isfile(self.cache_filename):
            return
        # We always get fresh vms
        if self.is_cache_valid() and not (resource == 'vms' or resource is None):
            return
        if self.args.refresh_cache:
            resource = None

        if resource == 'vms' or resource is None:
            self.data['vms'] = self.manager.list_vms()
            self.cache_refreshed = True
        if resource == 'clusters' or resource is None:
            self.data['clusters'] = self.manager.list_clusters()
            self.cache_refreshed = True
        if resource == 'projects' or resource is None:
            self.data['projects'] = self.manager.list_projects()
            self.cache_refreshed = True
        if resource == 'categories' or resource is None:
            self.data['categories'] = self.manager.list_categories()
            self.cache_refreshed = True
        if resource == 'nodes' or resource is None:
            self.data['nodes'] = self.manager.list_nodes()
            self.cache_refreshed = True

    def add_inventory_group(self, key):
        """ Method to create group dict """
        host_dict = {'hosts': [], 'vars': {}}
        self.inventory[key] = host_dict
        return

    def add_host(self, group, host):
        """ Helper method to reduce host duplication """
        if group not in self.inventory:
            self.add_inventory_group(group)

        if host not in self.inventory[group]['hosts']:
            self.inventory[group]['hosts'].append(host)
        return

    def build_inventory(self):
        """ Build Ansible inventory of vms """
        self.inventory = {
            'all': {
                'hosts': [],
                'vars': self.group_variables
            },
            '_meta': {'hostvars': {}}
        }

        # add all vms by id and name
        # print("data: {}".format(json.dumps(self.data)))
        for vm in self.data['vms']['entities']:
            for net in vm['status']['resources']['nic_list']:
                if net['ip_endpoint_list']:
                    dest = net['ip_endpoint_list'][0]['ip']
                else:
                    continue
        
            self.inventory['all']['hosts'].append(dest)

            self.add_host(vm['metadata']['uuid'], dest)

            self.add_host(vm['status']['name'], dest)

            #added for vms that do not have owner_references or project_references
            unknown = {"name": "unknown"}
            ## groups that are always present
            for group in (['prism_central',
                           'cluster_' + vm['status']['cluster_reference']['name'].lower(),
                           'project_' + vm['metadata'].get('project_reference',unknown)['name'].lower(),
                           'owner_' + vm['metadata'].get('owner_reference',unknown)['name'].lower(),
                           'hypervisor_' + vm['status']['resources']['hypervisor_type'].lower(),
                           'status_' + vm['status']['resources']['power_state'].lower()]):
                self.add_host(group, dest)
   
            ## groups that are not always present
            for group in (vm['metadata']['categories']):
                if group:
                    category = 'category_' + group.lower() + "_" + PrismCentralInventory.to_safe(vm['metadata']['categories'][group]).lower()
                    self.add_host(category, dest)
   
            #if vm['labels']:
            #    for tag in vm['labels']:
            #        self.add_host(tag, dest)

            # hostvars
            #info = self.pc_namespace(vm)
            self.inventory['_meta']['hostvars'][dest] = vm

    def load_vm_variables_for_host(self):
        """ Generate a JSON response to a --host call """
        host = self.args.host
        result = self.manager.search(host)
        vm_uuid = result['query_term_list'][0]['token_list'][0]['identifier']['value']
        vm = self.manager.get_vm(vm_uuid)
        #info = self.pc_namespace(vm)
        return {'vm': vm}

    ###########################################################################
    # Cache Management
    ###########################################################################

    def is_cache_valid(self):
        """ Determines if the cache files have expired, or if it is still valid """
        if os.path.isfile(self.cache_filename):
            mod_time = os.path.getmtime(self.cache_filename)
            current_time = time()
            if (mod_time + self.cache_max_age) > current_time:
                return True
        return False

    def load_from_cache(self):
        """ Reads the data from the cache file and assigns it to member variables as Python Objects """
        try:
            with open(self.cache_filename, 'r') as cache:
                json_data = cache.read()
            data = json.loads(json_data)
        except IOError:
            data = {'data': {}, 'inventory': {}}

        self.data = data['data']
        self.inventory = data['inventory']

    def write_to_cache(self):
        """ Writes data in JSON format to a file """
        data = {'data': self.data, 'inventory': self.inventory}
        json_data = json.dumps(data, indent=2)

        with open(self.cache_filename, 'w') as cache:
            cache.write(json_data)

    ###########################################################################
    # Utilities
    ###########################################################################
    @staticmethod
    def to_safe(word):
        """ Converts 'bad' characters in a string to underscores so they can be used as Ansible groups """
        return re.sub(r"[^A-Za-z0-9\-.]", "_", word)

    #@staticmethod
    #def pc_namespace(data):
    #    """ Returns a copy of the dictionary with all the keys put in a 'pc_' namespace """
    #    info = {}
    #    for k, v in data.items():
    #        info['pc_' + k] = v
    #    return info


###########################################################################
# Run the script
PrismCentralInventory()