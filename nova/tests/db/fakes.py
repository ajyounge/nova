# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Stubouts, mocks and fixtures for the test suite"""

import time

from nova import db
from nova import test
from nova import utils


def stub_out_db_instance_api(stubs, injected=True):
    """Stubs out the db API for creating Instances."""

    INSTANCE_TYPES = {
        'm1.tiny': dict(id=2,
                        memory_mb=512,
                        vcpus=1,
                        local_gb=0,
                        flavorid=1,
                        rxtx_cap=1),
        'm1.small': dict(id=5,
                         memory_mb=2048,
                         vcpus=1,
                         local_gb=20,
                         flavorid=2,
                         rxtx_cap=2),
        'm1.medium':
            dict(id=1,
                 memory_mb=4096,
                 vcpus=2,
                 local_gb=40,
                 flavorid=3,
                 rxtx_cap=3),
        'm1.large': dict(id=3,
                         memory_mb=8192,
                         vcpus=4,
                         local_gb=80,
                         flavorid=4,
                         rxtx_cap=4),
        'm1.xlarge':
            dict(id=4,
                 memory_mb=16384,
                 vcpus=8,
                 local_gb=160,
                 flavorid=5,
                 rxtx_cap=5)}

    flat_network_fields = {'id': 'fake_flat',
                           'bridge': 'xenbr0',
                           'label': 'fake_flat_network',
                           'netmask': '255.255.255.0',
                           'cidr_v6': 'fe80::a00:0/120',
                           'netmask_v6': '120',
                           'gateway': '10.0.0.1',
                           'gateway_v6': 'fe80::a00:1',
                           'broadcast': '10.0.0.255',
                           'dns': '10.0.0.2',
                           'ra_server': None,
                           'injected': injected}

    vlan_network_fields = {'id': 'fake_vlan',
                           'bridge': 'br111',
                           'label': 'fake_vlan_network',
                           'netmask': '255.255.255.0',
                           'cidr_v6': 'fe80::a00:0/120',
                           'netmask_v6': '120',
                           'gateway': '10.0.0.1',
                           'gateway_v6': 'fe80::a00:1',
                           'broadcast': '10.0.0.255',
                           'dns': '10.0.0.2',
                           'ra_server': None,
                           'vlan': 111,
                           'injected': False}

    fixed_ip_fields = {'address': '10.0.0.3',
                       'address_v6': 'fe80::a00:3',
                       'network_id': 'fake_flat'}

    class FakeModel(object):
        """Stubs out for model."""
        def __init__(self, values):
            self.values = values

        def __getattr__(self, name):
            return self.values[name]

        def __getitem__(self, key):
            if key in self.values:
                return self.values[key]
            else:
                raise NotImplementedError()

    def fake_instance_type_get_all(context, inactive=0):
        return INSTANCE_TYPES

    def fake_instance_type_get_by_name(context, name):
        return INSTANCE_TYPES[name]

    def fake_instance_type_get_by_id(context, id):
        for name, inst_type in INSTANCE_TYPES.iteritems():
            if str(inst_type['id']) == str(id):
                return inst_type
        return None

    def fake_network_get_by_instance(context, instance_id):
        # Even instance numbers are on vlan networks
        if instance_id % 2 == 0:
            return FakeModel(vlan_network_fields)
        else:
            return FakeModel(flat_network_fields)
        return FakeModel(network_fields)

    def fake_network_get_all_by_instance(context, instance_id):
        # Even instance numbers are on vlan networks
        if instance_id % 2 == 0:
            return [FakeModel(vlan_network_fields)]
        else:
            return [FakeModel(flat_network_fields)]

    def fake_instance_get_fixed_address(context, instance_id):
        return FakeModel(fixed_ip_fields).address

    def fake_instance_get_fixed_address_v6(context, instance_id):
        return FakeModel(fixed_ip_fields).address

    def fake_fixed_ip_get_all_by_instance(context, instance_id):
        return [FakeModel(fixed_ip_fields)]

    stubs.Set(db, 'network_get_by_instance', fake_network_get_by_instance)
    stubs.Set(db, 'network_get_all_by_instance',
              fake_network_get_all_by_instance)
    stubs.Set(db, 'instance_type_get_all', fake_instance_type_get_all)
    stubs.Set(db, 'instance_type_get_by_name', fake_instance_type_get_by_name)
    stubs.Set(db, 'instance_type_get_by_id', fake_instance_type_get_by_id)
    stubs.Set(db, 'instance_get_fixed_address',
        fake_instance_get_fixed_address)
    stubs.Set(db, 'instance_get_fixed_address_v6',
        fake_instance_get_fixed_address_v6)
    stubs.Set(db, 'network_get_all_by_instance',
        fake_network_get_all_by_instance)
    stubs.Set(db, 'fixed_ip_get_all_by_instance',
        fake_fixed_ip_get_all_by_instance)
