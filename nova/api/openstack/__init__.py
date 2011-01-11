# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""
WSGI middleware for OpenStack API controllers.
"""

import routes
import webob.dec
import webob.exc
import webob

from nova import flags
from nova import log as logging
from nova import utils
from nova import wsgi
from nova.api.openstack import faults
from nova.api.openstack import backup_schedules
from nova.api.openstack import consoles
from nova.api.openstack import flavors
from nova.api.openstack import images
from nova.api.openstack import servers
from nova.api.openstack import sharedipgroups


LOG = logging.getLogger('nova.api.openstack')
FLAGS = flags.FLAGS
flags.DEFINE_string('os_api_auth',
    'nova.api.openstack.auth.AuthMiddleware',
    'The auth mechanism to use for the OpenStack API implemenation')

flags.DEFINE_string('os_api_ratelimiting',
    'nova.api.openstack.ratelimiting.RateLimitingMiddleware',
    'Default ratelimiting implementation for the Openstack API')

flags.DEFINE_bool('allow_admin_api',
    False,
    'When True, this API service will accept admin operations.')


class API(wsgi.Middleware):
    """WSGI entry point for all OpenStack API requests."""

    def __init__(self):
        auth_middleware = utils.import_class(FLAGS.os_api_auth)
        ratelimiting_middleware = \
            utils.import_class(FLAGS.os_api_ratelimiting)
        app = auth_middleware(ratelimiting_middleware(APIRouter()))
        super(API, self).__init__(app)

    @webob.dec.wsgify
    def __call__(self, req):
        try:
            return req.get_response(self.application)
        except Exception as ex:
            LOG.exception(_("Caught error: %s"), str(ex))
            exc = webob.exc.HTTPInternalServerError(explanation=str(ex))
            return faults.Fault(exc)


class APIRouter(wsgi.Router):
    """
    Routes requests on the OpenStack API to the appropriate controller
    and method.
    """

    def __init__(self):
        mapper = routes.Mapper()

        server_members = {'action': 'POST'}
        if FLAGS.allow_admin_api:
            LOG.debug(_("Including admin operations in API."))
            server_members['pause'] = 'POST'
            server_members['unpause'] = 'POST'
            server_members["diagnostics"] = "GET"
            server_members["actions"] = "GET"
            server_members['suspend'] = 'POST'
            server_members['resume'] = 'POST'

        mapper.resource("server", "servers", controller=servers.Controller(),
                        collection={'detail': 'GET'},
                        member=server_members)

        mapper.resource("backup_schedule", "backup_schedule",
                        controller=backup_schedules.Controller(),
                        parent_resource=dict(member_name='server',
                        collection_name='servers'))

        mapper.resource("console", "consoles",
                        controller=consoles.Controller(),
                        parent_resource=dict(member_name='server',
                        collection_name='servers'))

        mapper.resource("image", "images", controller=images.Controller(),
                        collection={'detail': 'GET'})
        mapper.resource("flavor", "flavors", controller=flavors.Controller(),
                        collection={'detail': 'GET'})
        mapper.resource("sharedipgroup", "sharedipgroups",
                        controller=sharedipgroups.Controller())

        super(APIRouter, self).__init__(mapper)


class Versions(wsgi.Application):
    @webob.dec.wsgify
    def __call__(self, req):
        """Respond to a request for all OpenStack API versions."""
        response = {
                "versions": [
                    dict(status="CURRENT", id="v1.0")]}
        metadata = {
            "application/xml": {
                "attributes": dict(version=["status", "id"])}}
        return wsgi.Serializer(req.environ, metadata).to_content_type(response)


def router_factory(global_cof, **local_conf):
    return APIRouter()


def versions_factory(global_conf, **local_conf):
    return Versions()
