# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
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

import stubout

from nova import test
from nova.api.openstack import shared_ip_groups


class SharedIpGroupsTest(test.TestCase):
    def setUp(self):
        super(SharedIpGroupsTest, self).setUp()
        self.stubs = stubout.StubOutForTesting()

    def tearDown(self):
        self.stubs.UnsetAll()
        super(SharedIpGroupsTest, self).tearDown()

    def test_get_shared_ip_groups(self):
        pass

    def test_create_shared_ip_group(self):
        pass

    def test_delete_shared_ip_group(self):
        pass
