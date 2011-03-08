# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Brian Schott
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

from sqlalchemy import *
from migrate import *

from nova import log as logging


meta = MetaData()


# Table stub-definitions
# Just for the ForeignKey and column creation to succeed, these are not the
# actual definitions of instances or services.
#
instances = Table('instances', meta,
                  Column('id', Integer(),
                         primary_key=True, nullable=False))

#
# New Tables
#
# None

#
# Tables to alter
#
# None

#
# Columns to add to existing tables
#


instances_cpu_arch = Column('cpu_arch',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_cpu_info = Column('cpu_info',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_xpu_arch = Column('xpu_arch',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_xpu_info = Column('xpu_info',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_xpus = Column('xpus', Integer())

instances_net_arch = Column('net_arch',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_net_info = Column('net_info',
                            String(length=255,
                                   convert_unicode=False,
                                   assert_unicode=None,
                                   unicode_error=None,
                                   _warn_on_bytestring=False))

instances_net_mbps = Column('net_mbps', Integer())


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine;
    # bind migrate_engine to your metadata
    meta.bind = migrate_engine

    # Add columns to existing tables
    instances.create_column(instances_cpu_arch)
    instances.create_column(instances_cpu_info)
    instances.create_column(instances_xpu_arch)
    instances.create_column(instances_xpu_info)
    instances.create_column(instances_xpus)
    instances.create_column(instances_net_arch)
    instances.create_column(instances_net_info)
    instances.create_column(instances_net_mbps)
