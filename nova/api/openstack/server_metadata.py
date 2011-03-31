# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

from webob import exc

from nova import compute
from nova import wsgi
from nova.api.openstack import faults


class Controller(wsgi.Controller):
    """ The server metadata API controller for the Openstack API """

    def __init__(self):
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def _get_metadata(self, context, server_id):
        metadata = self.compute_api.get_instance_metadata(context, server_id)
        meta_dict = {}
        for key, value in metadata.iteritems():
            meta_dict[key] = value
        return dict(metadata=meta_dict)

    def index(self, req, server_id):
        """ Returns the list of metadata for a given instance """
        context = req.environ['nova.context']
        return self._get_metadata(context, server_id)

    def create(self, req, server_id):
        context = req.environ['nova.context']
        body = self._deserialize(req.body, req.get_content_type())
        self.compute_api.update_or_create_instance_metadata(context,
                                                            server_id,
                                                            body['metadata'])
        return req.body

    def update(self, req, server_id, id):
        context = req.environ['nova.context']
        body = self._deserialize(req.body, req.get_content_type())
        if not id in body:
            expl = _('Request body and URI mismatch')
            raise exc.HTTPBadRequest(explanation=expl)
        if len(body) > 1:
            expl = _('Request body contains too many items')
            raise exc.HTTPBadRequest(explanation=expl)
        self.compute_api.update_or_create_instance_metadata(context,
                                                            server_id,
                                                            body)
        return req.body

    def show(self, req, server_id, id):
        """ Return a single metadata item """
        context = req.environ['nova.context']
        data = self._get_metadata(context, server_id)
        if id in data['metadata']:
            return {id: data['metadata'][id]}
        else:
            return faults.Fault(exc.HTTPNotFound())

    def delete(self, req, server_id, id):
        """ Deletes an existing metadata """
        context = req.environ['nova.context']
        self.compute_api.delete_instance_metadata(context, server_id, id)
