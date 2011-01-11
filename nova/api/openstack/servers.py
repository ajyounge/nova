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

import traceback

from webob import exc

from nova import compute
from nova import exception
from nova import log as logging
from nova import wsgi
from nova.api.openstack import common
from nova.api.openstack import faults
from nova.auth import manager as auth_manager
from nova.compute import instance_types
from nova.compute import power_state
import nova.api.openstack


LOG = logging.getLogger('server')
LOG.setLevel(logging.DEBUG)


def _translate_detail_keys(inst):
    """ Coerces into dictionary format, mapping everything to Rackspace-like
    attributes for return"""
    power_mapping = {
        None: 'build',
        power_state.NOSTATE: 'build',
        power_state.RUNNING: 'active',
        power_state.BLOCKED: 'active',
        power_state.SUSPENDED: 'suspended',
        power_state.PAUSED: 'error',
        power_state.SHUTDOWN: 'active',
        power_state.SHUTOFF: 'active',
        power_state.CRASHED: 'error'}
    inst_dict = {}

    mapped_keys = dict(status='state', imageId='image_id',
        flavorId='instance_type', name='display_name', id='id')

    for k, v in mapped_keys.iteritems():
        inst_dict[k] = inst[v]

    inst_dict['status'] = power_mapping[inst_dict['status']]
    inst_dict['addresses'] = dict(public=[], private=[])
    inst_dict['metadata'] = {}
    inst_dict['hostId'] = ''

    return dict(server=inst_dict)


def _translate_keys(inst):
    """ Coerces into dictionary format, excluding all model attributes
    save for id and name """
    return dict(server=dict(id=inst['id'], name=inst['display_name']))


class Controller(wsgi.Controller):
    """ The Server API controller for the OpenStack API """

    _serialization_metadata = {
        'application/xml': {
            "attributes": {
                "server": ["id", "imageId", "name", "flavorId", "hostId",
                           "status", "progress"]}}}

    def __init__(self):
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def index(self, req):
        """ Returns a list of server names and ids for a given user """
        return self._items(req, entity_maker=_translate_keys)

    def detail(self, req):
        """ Returns a list of server details for a given user """
        return self._items(req, entity_maker=_translate_detail_keys)

    def _items(self, req, entity_maker):
        """Returns a list of servers for a given user.

        entity_maker - either _translate_detail_keys or _translate_keys
        """
        instance_list = self.compute_api.get_all(req.environ['nova.context'])
        limited_list = common.limited(instance_list, req)
        res = [entity_maker(inst)['server'] for inst in limited_list]
        return dict(servers=res)

    def show(self, req, id):
        """ Returns server details by server id """
        try:
            instance = self.compute_api.get(req.environ['nova.context'], id)
            return _translate_detail_keys(instance)
        except exception.NotFound:
            return faults.Fault(exc.HTTPNotFound())

    def delete(self, req, id):
        """ Destroys a server """
        try:
            self.compute_api.delete(req.environ['nova.context'], id)
        except exception.NotFound:
            return faults.Fault(exc.HTTPNotFound())
        return exc.HTTPAccepted()

    def create(self, req):
        """ Creates a new server for a given user """
        env = self._deserialize(req.body, req)
        if not env:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        key_pair = auth_manager.AuthManager.get_key_pairs(
            req.environ['nova.context'])[0]
        instances = self.compute_api.create(
            req.environ['nova.context'],
            instance_types.get_by_flavor_id(env['server']['flavorId']),
            env['server']['imageId'],
            display_name=env['server']['name'],
            display_description=env['server']['name'],
            key_name=key_pair['name'],
            key_data=key_pair['public_key'])
        return _translate_keys(instances[0])

    def update(self, req, id):
        """ Updates the server name or password """
        inst_dict = self._deserialize(req.body, req)
        if not inst_dict:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        update_dict = {}
        if 'adminPass' in inst_dict['server']:
            update_dict['admin_pass'] = inst_dict['server']['adminPass']
        if 'name' in inst_dict['server']:
            update_dict['display_name'] = inst_dict['server']['name']

        try:
            self.compute_api.update(req.environ['nova.context'], id,
                                    **update_dict)
        except exception.NotFound:
            return faults.Fault(exc.HTTPNotFound())
        return exc.HTTPNoContent()

    def action(self, req, id):
        """ Multi-purpose method used to reboot, rebuild, and
        resize a server """
        input_dict = self._deserialize(req.body, req)
        try:
            reboot_type = input_dict['reboot']['type']
        except Exception:
            raise faults.Fault(exc.HTTPNotImplemented())
        try:
            # TODO(gundlach): pass reboot_type, support soft reboot in
            # virt driver
            self.compute_api.reboot(req.environ['nova.context'], id)
        except:
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def lock(self, req, id):
        """
        lock the instance with id
        admin only operation

        """
        context = req.environ['nova.context']
        try:
            self.compute_api.lock(context, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("Compute.api::lock %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def unlock(self, req, id):
        """
        unlock the instance with id
        admin only operation

        """
        context = req.environ['nova.context']
        try:
            self.compute_api.unlock(context, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("Compute.api::unlock %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def get_lock(self, req, id):
        """
        return the boolean state of (instance with id)'s lock

        """
        context = req.environ['nova.context']
        try:
            self.compute_api.get_lock(context, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("Compute.api::get_lock %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def pause(self, req, id):
        """ Permit Admins to Pause the server. """
        ctxt = req.environ['nova.context']
        try:
            self.compute_api.pause(ctxt, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("Compute.api::pause %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def unpause(self, req, id):
        """ Permit Admins to Unpause the server. """
        ctxt = req.environ['nova.context']
        try:
            self.compute_api.unpause(ctxt, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("Compute.api::unpause %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def suspend(self, req, id):
        """permit admins to suspend the server"""
        context = req.environ['nova.context']
        try:
            self.compute_api.suspend(context, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("compute.api::suspend %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def resume(self, req, id):
        """permit admins to resume the server from suspend"""
        context = req.environ['nova.context']
        try:
            self.compute_api.resume(context, id)
        except:
            readable = traceback.format_exc()
            LOG.exception(_("compute.api::resume %s"), readable)
            return faults.Fault(exc.HTTPUnprocessableEntity())
        return exc.HTTPAccepted()

    def diagnostics(self, req, id):
        """Permit Admins to retrieve server diagnostics."""
        ctxt = req.environ["nova.context"]
        return self.compute_api.get_diagnostics(ctxt, id)

    def actions(self, req, id):
        """Permit Admins to retrieve server actions."""
        ctxt = req.environ["nova.context"]
        items = self.compute_api.get_actions(ctxt, id)
        actions = []
        # TODO(jk0): Do not do pre-serialization here once the default
        # serializer is updated
        for item in items:
            actions.append(dict(
                created_at=str(item.created_at),
                action=item.action,
                error=item.error))
        return dict(actions=actions)
