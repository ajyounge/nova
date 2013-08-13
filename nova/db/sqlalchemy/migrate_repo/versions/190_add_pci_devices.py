# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 ISP RAS.
# Copyright (c) 2013 Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the 'License'); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# @author: Boris Pavlovic, Mirantis Inc

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint

from nova.db.sqlalchemy import api
from nova.db.sqlalchemy import utils
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    compute_nodes = Table('compute_nodes', meta, autoload=True)

    pci_devices_uc_name = 'uniq_pci_devices0host0address0deleted'
    pci_devices = Table('pci_devices', meta,
                        Column('created_at', DateTime),
                        Column('updated_at', DateTime),
                        Column('deleted_at', DateTime),
                        Column('deleted', Integer, default=0, nullable=False),
                        Column('id', Integer, primary_key=True,
                                nullable=False),
                        Column('address', String(12), nullable=False),
                        Column('product_id', String(4)),
                        Column('vendor_id', String(4)),
                        Column('label', String(255), nullable=False),
                        Column('host', String(255), nullable=False),
                        Column('status',
                               Enum('in_use', 'available', 'to_delete',
                                    name='pci_devices_status_enum'),
                               nullable=False),
                        Column('instance_uuid', String(36)),
                        Column('compute_id', Integer,
                               ForeignKey('compute_nodes.id'), nullable=False),
                        Index('ix_pci_devices_host_deleted',
                              'host', 'deleted'),
                        Index('ix_pci_devices_instance_uuid_deleted',
                              'instance_uuid', 'deleted'),
                        Index('ix_pci_devices_compute_id_deleted',
                              'compute_id', 'deleted'),
                        UniqueConstraint('host', 'address', 'deleted',
                                         name=pci_devices_uc_name),
                        mysql_engine='InnoDB',
                        mysql_charset='utf8')

    try:
        pci_devices.create()
        utils.create_shadow_table(migrate_engine, table=pci_devices)
    except Exception:
        LOG.exception(_('Exception while creating table `pci_devices`.'))
        raise


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)

    try:
        pci_device = Table('pci_devices', meta, autoload=True)
        pci_device.drop()
        shadow_pci_device = Table(api._SHADOW_TABLE_PREFIX + 'pci_devices',
                                  meta, autoload=True)
        shadow_pci_device.drop()
    except Exception:
        LOG.exception(_('Exception while dropping `pci_devices` tables.'))
        raise
