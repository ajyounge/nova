# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Citrix Systems, Inc.
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

import StringIO

import glance.client


def stubout_glance_client(stubs, cls):
    """Stubs out glance.client.Client"""
    stubs.Set(glance.client, 'Client',
              lambda *args, **kwargs: cls(*args, **kwargs))


class FakeGlance(object):
    IMAGE_MACHINE = 1
    IMAGE_KERNEL = 2
    IMAGE_RAMDISK = 3
    IMAGE_RAW = 4
    IMAGE_VHD = 5

    IMAGE_FIXTURES = {
        IMAGE_MACHINE: {
            'image_meta': {'name': 'fakemachine', 'size': 0,
                           'type': 'machine'},
            'image_data': StringIO.StringIO('')},
        IMAGE_KERNEL: {
            'image_meta': {'name': 'fakekernel', 'size': 0,
                           'type': 'kernel'},
            'image_data': StringIO.StringIO('')},
        IMAGE_RAMDISK: {
            'image_meta': {'name': 'fakeramdisk', 'size': 0,
                           'type': 'ramdisk'},
            'image_data': StringIO.StringIO('')},
        IMAGE_RAW: {
            'image_meta': {'name': 'fakeraw', 'size': 0,
                           'type': 'raw'},
            'image_data': StringIO.StringIO('')},
        IMAGE_VHD: {
            'image_meta': {'name': 'fakevhd', 'size': 0,
                           'type': 'vhd'},
            'image_data': StringIO.StringIO('')}}

    def __init__(self, host, port=None, use_ssl=False):
        pass

    def get_image_meta(self, image_id):
        return self.IMAGE_FIXTURES[image_id]['image_meta']

    def get_image(self, image_id):
        image = self.IMAGE_FIXTURES[image_id]
        return image['image_meta'], image['image_data']
