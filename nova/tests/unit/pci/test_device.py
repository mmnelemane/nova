# Copyright 2014 Intel Corporation
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

from nova import context
from nova import exception
from nova import objects
from nova.objects import fields
from nova.pci import device
from nova import test


dev_dict = {
    'created_at': None,
    'updated_at': None,
    'deleted_at': None,
    'deleted': None,
    'id': 1,
    'compute_node_id': 1,
    'address': 'a',
    'vendor_id': 'v',
    'product_id': 'p',
    'numa_node': 1,
    'dev_type': fields.PciDeviceType.STANDARD,
    'status': fields.PciDeviceStatus.AVAILABLE,
    'dev_id': 'i',
    'label': 'l',
    'instance_uuid': None,
    'extra_info': '{}',
    'request_id': None,
    }


class PciDeviceTestCase(test.NoDBTestCase):
    def setUp(self):
        super(PciDeviceTestCase, self).setUp()
        self.ctxt = context.get_admin_context()
        self.inst = objects.Instance()
        self.inst.uuid = 'fake-inst-uuid'
        self.inst.pci_devices = objects.PciDeviceList()
        self.devobj = objects.PciDevice._from_db_object(
            self.ctxt,
            objects.PciDevice(),
            dev_dict)

    def test_claim_device(self):
        device.claim(self.devobj, self.inst)
        self.assertEqual(self.devobj.status,
                         fields.PciDeviceStatus.CLAIMED)
        self.assertEqual(self.devobj.instance_uuid,
                         self.inst.uuid)
        self.assertEqual(len(self.inst.pci_devices), 0)

    def test_claim_device_fail(self):
        self.devobj.status = fields.PciDeviceStatus.ALLOCATED
        self.assertRaises(exception.PciDeviceInvalidStatus,
                          device.claim, self.devobj, self.inst)

    def test_allocate_device(self):
        device.claim(self.devobj, self.inst)
        device.allocate(self.devobj, self.inst)
        self.assertEqual(self.devobj.status,
                         fields.PciDeviceStatus.ALLOCATED)
        self.assertEqual(self.devobj.instance_uuid, 'fake-inst-uuid')
        self.assertEqual(len(self.inst.pci_devices), 1)
        self.assertEqual(self.inst.pci_devices[0].vendor_id,
                         'v')
        self.assertEqual(self.inst.pci_devices[0].status,
                         fields.PciDeviceStatus.ALLOCATED)

    def test_allocacte_device_fail_status(self):
        self.devobj.status = 'removed'
        self.assertRaises(exception.PciDeviceInvalidStatus,
                          device.allocate,
                          self.devobj,
                          self.inst)

    def test_allocacte_device_fail_owner(self):
        inst_2 = objects.Instance()
        inst_2.uuid = 'fake-inst-uuid-2'
        device.claim(self.devobj, self.inst)
        self.assertRaises(exception.PciDeviceInvalidOwner,
                          device.allocate,
                          self.devobj, inst_2)

    def test_free_claimed_device(self):
        device.claim(self.devobj, self.inst)
        device.free(self.devobj, self.inst)
        self.assertEqual(self.devobj.status,
                         fields.PciDeviceStatus.AVAILABLE)
        self.assertIsNone(self.devobj.instance_uuid)

    def test_free_allocated_device(self):
        device.claim(self.devobj, self.inst)
        device.allocate(self.devobj, self.inst)
        self.assertEqual(len(self.inst.pci_devices), 1)
        device.free(self.devobj, self.inst)
        self.assertEqual(len(self.inst.pci_devices), 0)
        self.assertEqual(self.devobj.status,
                         fields.PciDeviceStatus.AVAILABLE)
        self.assertIsNone(self.devobj.instance_uuid)

    def test_free_device_fail(self):
        self.devobj.status = 'removed'
        self.assertRaises(exception.PciDeviceInvalidStatus,
                          device.free, self.devobj)

    def test_remove_device(self):
        device.remove(self.devobj)
        self.assertEqual(self.devobj.status, 'removed')
        self.assertIsNone(self.devobj.instance_uuid)

    def test_remove_device_fail(self):
        device.claim(self.devobj, self.inst)
        self.assertRaises(exception.PciDeviceInvalidStatus,
                          device.remove, self.devobj)
