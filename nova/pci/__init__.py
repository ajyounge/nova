# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 ISP RAS.
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

"""Module for PCI passthrough."""

import jsonschema
import re

from oslo.config import cfg

from nova import conductor
from nova import exception
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging


# NOTE(boris-42): DB access from compute nodes have to be through conductor.
conductor_api = conductor.API()

LOG = logging.getLogger(__name__)

pci_opts = [
    cfg.StrOpt('pci_passthrough_devices',
            default='[]',
            help='List of avaiable for PCI passthrough devices as list of '
                 'json objects: '
                 ' {"label": string, '
                 '  "address": string in format domain:bus:slot.function}')
]
CONF = cfg.CONF
CONF.register_opts(pci_opts)


_PCI_ADDRESS_PATTERN = "^(hex{4}):(hex{2}):(hex{2}).(oct{1})$".\
                            replace("hex", "[\da-fA-F]").\
                            replace("oct", "[0-7]")
_PCI_ADDRESS_REGEX = re.compile(_PCI_ADDRESS_PATTERN)
_PCI_PASSTHROUGH_DEVICES_SCHEMA = {
    "title": "Available PCI devices",
    "type": "array",
    "items": {
        "title": "PCI device",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200
            },
            "address": {
                "type": "string",
                "pattern": _PCI_ADDRESS_PATTERN
            },
            "vendor_id": {
                "type": "string",
                "pattern": "^[\da-fA-F]{4}$"
            },
            "product_id": {
                "type": "string",
                "pattern": "^[\da-fA-F]{4}$"
            }
        },
        "required": ["label", "address"]
    }
}


def get_labels_from_instance_type(instance_type):
    specs = instance_type["extra_specs"]
    return jsonutils.loads(specs.get('pci_passthrough:labels', '[]'))


def check_pci_device_address(address):
    if _PCI_ADDRESS_REGEX.match(address) is None:
        raise exception.PciDeviceWrongAddressFormat(address=address)


def parse_address(address):
    """
    Returns (domain, bus, slot, function) from PCI address that is stored in
    PciDevice DB table.
    """
    m = _PCI_ADDRESS_REGEX.match(address)
    if not m:
        raise exception.PciDeviceWrongAddressFormat(address=address)
    return m.groups()


def _validate_and_parse_pci_devices_from_config(host=None):
    """Validate PCI devices that are in CONF.pci_passthrough.devices."""
    devs = CONF.pci_passthrough_devices
    try:
        devs = jsonutils.loads(devs)
        jsonschema.validate(devs, _PCI_PASSTHROUGH_DEVICES_SCHEMA)

        addresses = set()
        for addr in [dev['address'] for dev in devs]:
            if addr in addresses:
                raise exception.PciDeviceAlreadyExistsOnHost(host=host,
                                                             address=addr)
            addresses.add(addr)
    except Exception as e:
        raise exception.PciDeviceInvalidConfig(error_msg=str(e))
    return devs

_WAS_INITED = False
_UNCREATED_PCI_DEVS = []


def _create_pci_devices(context, host, compute_id, devs=None):
    """
    Try to create devices that are in devs param. If devs is None try to create
    it from _UNCREATED_PCI_DEVS.
    """
    global _UNCREATED_PCI_DEVS
    if not devs:
        devs = _UNCREATED_PCI_DEVS
        _UNCREATED_PCI_DEVS = []

    for dev in devs:
        dev['host'] = host
        dev['compute_id'] = compute_id
        try:
            conductor_api.pci_device_create(context, dev)
        except exception.PciDeviceAlreadyExistsOnHost:
            _UNCREATED_PCI_DEVS.append(dev)
            LOG.info(_("Couldn't update PCI device with address: %(address)s."
                       " PCI device is busy."), {'address': dev['address']})


def sync_pci_devices(context, host, compute_id, init_once=True):
    """
    This method is called on each call of update_available_resource in
    resource_tracker.
    When it is called first time it will remove previous PCI devices from DB
    and populate it with new pci devices that are specified in CONF.

    Other calls are required because we are not able to delete devices that
    are used by instance. We should wait until they are released and then
    create (if they are in conf).
    """
    global _WAS_INITED

    if _WAS_INITED and init_once:
        _WAS_INITED = True
        _create_pci_devices(context, host, compute_id)
        return

    _WAS_INITED = True

    conductor_api.pci_device_destroy_all_on_host(context, host)
    _create_pci_devices(context, host, compute_id,
                        devs=_validate_and_parse_pci_devices_from_config(host))
