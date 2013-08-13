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

from oslo.config import cfg

from nova import context
from nova import db
from nova import exception
from nova import pci
from nova import test


CONF = cfg.CONF
CONF.import_opt('pci_passthrough_devices', 'nova.pci')


class PCIModuleTestCase(test.TestCase):

    def setUp(self):
        super(PCIModuleTestCase, self).setUp()
        self.ctx = context.get_admin_context()
        self.flags(use_local=True, group='conductor')
        self.conductor = self.start_service('conductor',
                                            manager=CONF.conductor.manager)

    def test_parse_address(self):
        addresses = [
            ("1000:10:10.1", ('1000', '10', '10', '1')),
            ("EEE0:EE:FF.7", ('EEE0', 'EE', 'FF', '7'))
        ]
        for addr in addresses:
            self.assertEqual(pci.parse_address(addr[0]), addr[1])

    def test_parse_invalid_address(self):
        invalid_addresses = [
            "10000:10:10.1",
            "1000:1:10.1",
            "1000:10:1.1",
            "1000:10:100.1",
            "1000:10:10.A",
            "100:10:100.1",
            "G000:10:10.1",
            "1000:G0:10.1",
            "1000:10:1G.1",
            "1000:10:10.9",
            "",
            "fdFDvVvVvVD"
        ]
        for address in invalid_addresses:
            self.assertRaises(exception.PciDeviceWrongAddressFormat,
                              pci.parse_address, address)

    def test_init_no_pci_devices(self):
        self.flags(pci_passthrough_devices='[]')
        pci.sync_pci_devices(self.ctx, "fake_host", 100500, init_once=False)
        self.assertEqual([],
                         db.pci_device_get_all_by_host(self.ctx, "fake_host"))

    def test_init_pci_devices(self):
        pci_devices = """[
            {
                "label": "first",
                "address": "AAAA:AA:AA.1"
            },
            {
                "label": "first",
                "address": "BBBB:BB:BB.1",
                "vendor_id": "cccc"
            },
            {
                "label": "second",
                "address": "CCCC:CC:CC.1",
                "product_id": "dddd"
            },
            {
                "label": "last",
                "address": "DDDD:DD:DD.1",
                "vendor_id": "1cEF",
                "product_id": "1ABF"

            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        pci.sync_pci_devices(self.ctx, "fake_host", 100500, init_once=False)
        actual_devices = db.pci_device_get_all_by_host(self.ctx, "fake_host")
        self.assertEqual(len(actual_devices), 4)

    def test_re_init_pci_devices(self):
        pci_devices = """[
            {
                "label": "first",
                "address": "AAAA:AA:AA.1"
            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        pci.sync_pci_devices(self.ctx, "fake_host", 100500, init_once=False)
        pci.sync_pci_devices(self.ctx, "fake_host", 100500, init_once=False)
        actual_devices = db.pci_device_get_all_by_host(self.ctx, "fake_host")
        self.assertEqual(len(actual_devices), 1)

    def test_pci_devices_from_confg_with_wrong_pci_device_address(self):
        pci_devices = """[
            {
                "label": "first",
                "address": "AAA33:AA:AA.1"
            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_config_with_missing_label_name(self):
        pci_devices = """[
            {
                "address": "AAA3:AA:AA.1"
            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_config_with_missing_address(self):
        pci_devices = """[
            {
                "label": "fake"
            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_init_pci_from_config_with_duplicated_addresses(self):
        pci_devices = """[
            {
                "label": "first",
                "address": "AAAA:AA:AA.1"
            },
            {
                "label": "second",
                "address": "BBBB:BB:BB.1"
            },
            {
                "label": "last",
                "address": "AAAA:AA:AA.1"
            }
        ]"""
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def _get_config_with_custom_field(self, name, value):
        conf = """[
            {
                "label": "first",
                "address": "AAA3:AA:AA.1",
                "%(name)s": "%(value)s"
            }
        ]"""
        return conf % {'name': name, 'value': value}

    def test_pci_devices_from_confg_with_wrong_pci_vendor_id_too_long(self):
        pci_devices = self._get_config_with_custom_field("vendor_id", "12345")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_confg_with_wrong_pci_vendor_id_too_short(self):
        pci_devices = self._get_config_with_custom_field("vendor_id", "123")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_confg_with_wrong_pci_vendor_id_not_hex(self):
        pci_devices = self._get_config_with_custom_field("vendor_id", "aaZb")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_confg_with_wrong_pci_product_id_too_long(self):
        pci_devices = self._get_config_with_custom_field("product_id", "12345")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_confg_with_wrong_pci_product_id_too_short(self):
        pci_devices = self._get_config_with_custom_field("product_id", "123")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)

    def test_pci_devices_from_confg_with_wrong_pci_product_id_not_hex(self):
        pci_devices = self._get_config_with_custom_field("product_id", "aaZb")
        self.flags(pci_passthrough_devices=pci_devices)
        self.assertRaises(exception.PciDeviceInvalidConfig,
                          pci.sync_pci_devices,
                          self.ctx, "fake_host", 100500, init_once=False)
