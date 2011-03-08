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
instance_types = Table('instance_types', meta,
        Column('id', Integer(),  primary_key=True, nullable=False))

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

instance_types_cpu_arch = Column(String(255), default='x86_64')
instance_types_cpu_info = Column(String(255), default='')
instance_types_xpu_arch = Column(String(255), default='')
instance_types_xpu_info = Column(String(255), default='')
instance_types_xpus = Column(Integer, nullable=false, default=0)
instance_types_net_arch = Column(String(255), default='')
instance_types_net_info = Column(String(255), default='')
instance_types_net_mbps = Column(Integer, nullable=false, default=0)

def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine;
    # bind migrate_engine to your metadata
    meta.bind = migrate_engine

    # Add columns to existing tables
    instance_types.create_column(instance_types_cpu_arch)
    instance_types.create_column(instance_types_cpu_info)
    instance_types.create_column(instance_types_xpu_arch)
    instance_types.create_column(instance_types_xpu_info)
    instance_types.create_column(instance_types_xpus)
    instance_types.create_column(instance_types_net_arch)
    instance_types.create_column(instance_types_net_info)
    instance_types.create_column(instance_types_net_mbps)

