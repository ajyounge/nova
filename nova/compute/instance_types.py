# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# Copyright (c) 2010 Citrix Systems, Inc.
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

"""
The built-in instance properties.
"""

from nova import flags
from nova import exception

FLAGS = flags.FLAGS
INSTANCE_TYPES = {
    'm1.tiny': dict(memory_mb=512, vcpus=1, local_gb=0, 
                    cpu_arch='i386', flavorid=1),
    'm1.small': dict(memory_mb=2048, vcpus=1, local_gb=20, 
                     cpu_arch='i386', flavorid=2),
    'm1.medium': dict(memory_mb=4096, vcpus=2, local_gb=40, 
                      cpu_arch='i386', flavorid=3),
    'm1.large': dict(memory_mb=8192, vcpus=4, local_gb=80, 
                     cpu_arch='x86_64', flavorid=4),
    'm1.xlarge': dict(memory_mb=16384, vcpus=8, local_gb=160, 
                      cpu_arch='x86_64', flavorid=5),
     # Tilera
    'tp.8x8': dict(memory_mb=16384, vcpus=64, local_gb=500, 
                   cpu_arch='tilera', flavorid=6),
     # x86+GPU
    'g1.small': dict(memory_mb=5120, vcpus=2, local_gb=225, 
                     cpu_arch='x86_64', gpu_arch='fermi', gcpus=448, flavorid=7),
    'g1.medium': dict(memory_mb=10240, vcpus=4, local_gb=450, 
                      cpu_arch='x86_64', gpu_arch='fermi', gcpus=448, flavorid=8),
    'g1.large': dict(memory_mb=20480, vcpus=8, local_gb=900, 
                     cpu_arch='x86_64', gpu_arch='fermi', gcpus=448, flavorid=9),

    # Shared-memory (SGI UV)
    'sh1.large': dict(memory_mb=65024, vcpus=16, local_gb=62, 
                      cpu_arch='x86_64', flavorid=10),
    'sh1.xlarge': dict(memory_mb=130048, vcpus=32, local_gb=125, 
                       cpu_arch='x86_64', flavorid=11),
    'sh1.2xlarge': dict(memory_mb=260096, vcpus=64, local_gb=250,  
                        cpu_arch='x86_64', flavorid=12),
    'sh1.4xlarge': dict(memory_mb=520192, vcpus=128, local_gb=500, 
                        cpu_arch='x86_64', flavorid=13)
    }


def get_by_type(instance_type):
    """Build instance data structure and save it to the data store."""
    if instance_type is None:
        return FLAGS.default_instance_type
    if instance_type not in INSTANCE_TYPES:
        raise exception.ApiError(_("Unknown instance type: %s") % \
                                 instance_type, "Invalid")
    return instance_type


def get_by_flavor_id(flavor_id):
    for instance_type, details in INSTANCE_TYPES.iteritems():
        if details['flavorid'] == flavor_id:
            return instance_type
    return FLAGS.default_instance_type
