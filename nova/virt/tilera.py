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
A connection to a tilera.

Supports tilera board only

**Related Flags**

:tilera_type:  tilera domain type.
:tilera_uri:  Override for the default libvirt URI (depends on libvirt_type).
:tilera_xml_template:  tilera XML Template.
:tilera_rescue_image_id:  Rescue ami image (default: ami-rescue).
:tilera_rescue_kernel_id:  Rescue aki image (default: aki-rescue).
:tilera_rescue_ramdisk_id:  Rescue ari image (default: ari-rescue).
:tilera_injected_network_template:  Template file for injected network
:tilera_allow_project_net_traffic:  Whether to allow in project network traffic

"""

import multiprocessing
import os
import shutil
import sys
import pickle  # MK
import time  # MK
import random
import subprocess
import uuid
from xml.dom import minidom

from eventlet import greenthread
from eventlet import event
from eventlet import tpool
import IPy

from nova import context
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
#from nova.api import context
from nova.auth import manager
#from nova.compute import disk
from nova.compute import instance_types
from nova.compute import power_state
from nova.virt import disk
from nova.virt import images

tilera = None
libxml2 = None
Template = None

LOG = logging.getLogger('nova.virt.tilera')

FLAGS = flags.FLAGS
# TODO(vish): These flags should probably go into a shared location
flags.DEFINE_string('tilera_injected_network_template',
                    utils.abspath('virt/tilera_interfaces.template'),
                    'Template file for injected network')
flags.DEFINE_string('tilera_xml_template',
                    utils.abspath('virt/tilera.xml.template'),
                    'tilera XML Template')
flags.DEFINE_string('tilera_type',
                    'tilera',
                    'tielra domain type')
flags.DEFINE_string('tilera_uri',
                    '',
                    'Override the default tilera URI (which is dependent'
                    ' on tilera_type)')
flags.DEFINE_bool('tilera_allow_project_net_traffic',
                  True,
                  'Whether to allow in project network traffic')

#MK
global tilera_boards
global fake_doms


class _tilera_board(object):
    """Manages tilera board information"""
    file_name = "/tftpboot/tilera_boards"
    boards = []
    BOARD_ID = 0
    IP_ADDR = 1
    MAC_ADDR = 2
    #BOARD_STATUS = 3
    VCPUS = 3
    MEMORY_MB = 4
    LOCAL_GB = 5
    MEMORY_MB_USED = 6
    LOCAL_GB_USED = 7
    HYPERVISOR_TYPE = 8
    HYPERVISOR_VER = 9
    CPU_INFO = 10

    def __init__(self):
        self.fp = open(self.file_name, "r")
        for item in self.fp:
            l = item.split()
            if l[0] == '#':
                continue
            l_d = {'board_id': int(l[self.BOARD_ID]),
                    'ip_addr': l[self.IP_ADDR],
                    'mac_addr': l[self.MAC_ADDR],
                    'status': power_state.NOSTATE,
                    'vcpus': l[self.VCPUS],
                    'memory_mb': l[self.MEMORY_MB],
                    'local_gb': l[self.LOCAL_GB],
                    'memory_mb_used': l[self.MEMORY_MB_USED],
                    'local_gb_used': l[self.LOCAL_GB_USED],
                    'hypervisor_type': l[self.HYPERVISOR_TYPE],
                    'hypervisor_version': l[self.HYPERVISOR_VER],
                    'cpu_info': l[self.CPU_INFO]
                  }
            self.boards.append(l_d)
        #print self.boards

    def get_tilera_hw_info(self, field):
        for board in self.boards:
            if board['board_id'] == 2:
                if field == 'vcpus':
                    return board['vcpus']
                elif field == 'memory_mb':
                    return board['memory_mb']
                elif field == 'local_gb':
                    return board['local_gb']
                elif field == 'memory_mb_used':
                    return board['memory_mb_used']
                elif field == 'local_gb_used':
                    return board['local_gb_used']
                elif field == 'hypervisor_type':
                    return board['hypervisor_type']
                elif field == 'hypervisor_version':
                    return board['hypervisor_version']
                elif field == 'cpu_info':
                    return board['cpu_info']

    def set_status(self, board_id, status):
        for board in self.boards:
            if board['board_id'] == board_id:
                board['board_id'] = status
                return 1
        return 0

    def get_idle_board(self):
        """get an idle board"""
        for item in self.boards:
            if item['status'] == 0:
                item['status'] = 1      # make status RUNNING
                return item['board_id']
        return -1

    #MK
    def find_ip_w_id(self, id):
        for item in self.boards:
            if item['board_id'] == id:
                return item['ip_addr']
    #_MK

    def free_board(self, board_id):
        print("free_board....\n")
        for item in self.boards:
            if item['board_id'] == str(board_id):
                item['status'] = 0  # make status IDLE
                return
        return -1

    def deactivate_board(self, board_id):
        board_ip = tilera_boards.find_ip_w_id(board_id)
        #print("deactivate_board is not implemented yet, \
        print("deactivate_board is called for \
               board_id = %s board_ip = %s\n", str(board_id), board_ip)
        #MK
        for item in self.boards:
            if item['board_id'] == board_id:
                print "status of board is set to 0"
                item['status'] = 0
        #_MK

        #MK: PDU control
        if board_id < 5:
            pdu_num = 1
            pdu_outlet_num = board_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = board_id
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
            + str(pdu_outlet_num) + " 2 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            '2', '>>', 'pdu_output')

        return []
        #raise

    #def activate_board(self, board_id, board_ip, name, mac_address):  # MK
    def activate_board(self, board_id, board_ip, name, mac_address, \
        ip_address):  # MK
        print("activate_board \n")

        target = os.path.join(FLAGS.instances_path, name)
        print target

        cmd = "cp /tftpboot/vmlinux_" + str(board_id) + \
            "_1 /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id) + "_1"
        path2 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('cp', path1, path2)

        #MK: PDU control
        if board_id < 5:
            pdu_num = 1
            pdu_outlet_num = board_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = board_id
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
        + str(pdu_outlet_num) + " 3 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            '3', '>>', 'pdu_output')
        #_MK

        cmd = "sleep 60"
        print cmd
        utils.execute('sleep', '60')
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --upload /tftpboot/tilera_fs_" \
            + str(board_id) + ".tar.gz /tilera_fs.tar.gz --quit"
        print cmd
        path1 = "/tftpboot/tilera_fs_" + str(board_id) + ".tar.gz"
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--upload', path1, \
            '/tilera_fs.tar.gz', '--quit')
        utils.execute('rm', path1)
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - mount /dev/sda1 /mnt - --wait " \
            + "--run - tar -xzpf /tilera_fs.tar.gz -C /mnt/ " \
            + "- --wait --quit"
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', 'mount', \
            '/dev/sda1', '/mnt', '-', '--wait', '--run', '-', 'tar', \
            '-xzpf', '/tilera_fs.tar.gz', '-C', '/mnt/', '-', \
            '--wait', '--quit')

        cmd = "cp /tftpboot/vmlinux_" + str(board_id) + \
            "_2 /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id) + "_2"
        path2 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('cp', path1, path2)
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
            + str(pdu_outlet_num) + " 3 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            '3', '>>', 'pdu_output')
        cmd = "sleep 80"
        print cmd
        utils.execute('sleep', '80')

        #cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net "
        # + board_ip + " --run - /usr/sbin/sshd - --wait -- ls
        #| grep bin >> tile_output"
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - /usr/sbin/sshd - --wait --quit"
        print cmd
        #utils.execute('/usr/local/TileraMDE/bin/tile-monitor',
        #'--resume', '--net', board_ip, '--run', '-', '/usr/sbin/sshd', \
        #'-', '--wait', '--', 'ls', '|', 'grep', 'bin', \
        #'>>', 'tile_output')
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            '/usr/sbin/sshd', '-', '--wait', '--quit')

        #file = open("./tile_output")
        #out_msg = file.readline()
        #print "tile_output: " + out_msg
        #utils.execute('rm', './tile_output')
        #file.close()
        #if out_msg.find("bin") < 0:
        #    cmd = "TILERA_BOARD_#" + str(board_id) + " " \
        #+ board_ip + " is not ready, out_msg=" + out_msg
        #    print cmd
        #    return power_state.NOSTATE
        #else:
        cmd = "TILERA_BOARD_#" + str(board_id) + " " + board_ip \
            + " is ready"
        print cmd
        cmd = "rm /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('rm', path1)
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - ifconfig xgbe0 hw ether " \
            + mac_address + " - --wait --run - ifconfig xgbe0 " \
            + ip_address + " - --wait --quit"
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            'ifconfig', 'xgbe0', 'hw', 'ether', mac_address, '-', \
            '--wait', '--run', '-', 'ifconfig', 'xgbe0', ip_address, \
            '-', '--wait', '--quit')
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - iptables -A INPUT -p tcp " \
            + "! -s 10.0.11.1 --dport 963 -j DROP - --wait " \
            + "--quit"
            #+ "--run - rm -rf /usr/sbin/iptables* - --wait \
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            'iptables', '-A', 'INPUT', '-p', 'tcp', '!', '-s', \
            '10.0.11.1', '--dport', '963', '-j', 'DROP', '-', '--wait', \
            #'--run', '-', 'rm', '-rf', '/usr/sbin/iptables*', \
            #'-', '--wait', \
            '--quit')
        return power_state.RUNNING


class _fake_dom(object):
    """Fake domain for Tilera to avoid using tilera"""
    fake_dom_file = "/tftpboot/test_fake_dom_file"
    fake_dom_nums = 0
    domains = []
    fp = 0

    def __init__(self):
        self.domains = []
        utils.execute('rm', self.fake_dom_file)
        print "open %s" % self.fake_dom_file
        try:
            self.fp = open(self.fake_dom_file, "r+")
            print "fp = "
            print self.fp
        except IOError:
            print ("%s file does not exist, but is created\n" \
                % self.fake_dom_file)
            self.fp = open(self.fake_dom_file, "w")
            self.fp.close()
            self.fp = open(self.fake_dom_file, "r+")
        self.read_domain_from_file()
        # (TODO) read pre-existing fake domains

    def read_domain_from_file(self):
        try:
            self.domains = pickle.load(self.fp)
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
        except EOFError:
            dom = []
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
            print "No domains exist."
            return
        print "============= initial domains ==========="
        print self.domains
        print "========================================="
        for dom in self.domains:
            if dom['status'] != power_state.RUNNING:
                print "Not running domain: remove"
                self.domains.remove(dom)
                continue
            res = tilera_boards.set_status(dom['board_id'], \
                                    dom['status'])
            if res > 0:  # no such board exixts
                self.fake_dom_nums = self.fake_dom_nums + 1
            else:
                print "domain running on an unknown board: discarded"
                self.domains.remove(dom)
                continue

        print "--> domains after reading"
        print self.domains

    def reboot_domain(self, name):
        fd = self.find_domain(name)
        if fd == []:
            raise exception.NotFound("No such domain (%s)" % name)
        board_ip = tilera_boards.find_ip_w_id(fd['board_id'])  # MK

        try:
            tilera_boards.deactivate_board(fd['board_id'])
        except:
            raise exception.NotFound("Failed power down \
                                      Tilera board %s" % fd['board_id'])
        self.change_domain_state(name, power_state.NOSTATE)
        try:
            state = tilera_boards.activate_board(fd['board_id'], \
                board_ip, name, fd['mac_address'], fd['ip_address'])  # MK
                #board_ip, name, fd['mac_address']) #MK
                #fd['ip_addr'], name)
            self.change_domain_state(name, state)
            return state
        except:
            LOG.debug(_("deactivate -> activate fails"))
            self.destroy_domain(name)
            raise

    def destroy_domain(self, name):
        """remove name instance from domains list
           and power down the corresponding Tilera board"""
        fd = self.find_domain(name)
        if fd == []:
            print "destroy_domain: no such domain"
            raise exception.NotFound("No such domain %s" % name)

        try:
            tilera_boards.deactivate_board(fd['board_id'])
            print "--> after deactivate board"
            self.domains.remove(fd)
            print "domains: "
            print self.domains
            print "boards: "
            print tilera_boards.boards
            self.store_domain()
            print "after storing domains"
            print self.domains
        except:
            print "what to do?"
            raise

    def create_domain(self, xml_dict, bpath):
        """add a domain to domains list
           and activate a idle Tilera board"""
        LOG.debug(_("1////////////////////"))  # MK
        fd = self.find_domain(xml_dict['name'])
        if fd != []:
            print 'domain with the same name already exists'
            raise
            #MK
            #raise exception.NotFound("same name already exists")
        print "create_domain: before get_idle_board"

        board_id = tilera_boards.get_idle_board()
        if board_id == -1:
            print ('No idle tilera board exits')
            raise exception.NotFound("No free boards available")

        #MK
        board_ip = tilera_boards.find_ip_w_id(board_id)

        new_dom = {'board_id': board_id,
                    'name': xml_dict['name'],
                    'memory_kb': xml_dict['memory_kb'], \
                    'vcpus': xml_dict['vcpus'], \
                    'mac_address': xml_dict['mac_address'], \
                    'ip_address': xml_dict['ip_address'], \
                    'dhcp_server': xml_dict['dhcp_server'], \
                    'image_id': xml_dict['image_id'], \
                    'kernel_id': xml_dict['kernel_id'], \
                    'ramdisk_id': xml_dict['ramdisk_id'], \
                     'status': power_state.NOSTATE}
        self.domains.append(new_dom)
        print new_dom  # MK
        self.change_domain_state(new_dom['name'], power_state.NOSTATE)

        #MK
        cmd = "mount -o loop " + bpath + "/root /tftpboot/fs_" \
            + str(board_id)
        print cmd
        path1 = bpath + "/root"
        path2 = "/tftpboot/fs_" + str(board_id)
        utils.execute('mount', '-o', 'loop', path1, path2)
        cmd = "cd /tftpboot/fs_" + str(board_id) + \
            "; tar -czpf ../tilera_fs_" + str(board_id) + ".tar.gz ."
        print cmd
        path1 = "/tftpboot/fs_" + str(board_id)
        os.chdir(path1)
        path2 = "../tilera_fs_" + str(board_id) + ".tar.gz"
        utils.execute('tar', '-czpf', path2, '.')
        path1 = bpath + "/../../.."
        os.chdir(path1)
        cmd = "umount -l /tftpboot/fs_" + str(board_id)
        print cmd
        path4 = "/tftpboot/fs_" + str(board_id)
        utils.execute('umount', '-l', path4)
        #_MK

        try:
            state = tilera_boards.activate_board(board_id,
                board_ip, new_dom['name'], new_dom['mac_address'], \
                new_dom['ip_address'])  # MK
                #board_ip, new_dom['name'], new_dom['mac_address']) #MK
        except:
            self.domains.remove(new_dom)  # MK
            tilera_boards.free_board(board_id)
            raise exception.NotFound("Failed to boot Tilera board %s" \
                % board_id)

        print "BEFORE last self.change_domain_state +++++++++++++++++"  # MK
        self.change_domain_state(new_dom['name'], state)
        return state

    def change_domain_state(self, name, state):
        l = self.find_domain(name)
        if l == []:
            raise exception.NotFound("No such domain exists")
        i = self.domains.index(l)
        self.domains[i]['status'] = state
        print "change_domain_state: to new state %s" % str(state)
        self.store_domain()

    def store_domain(self):
        # store fake domains to the file
        print "store fake domains to the file"
        print "-------"
        print self.domains
        print "-------"
        print self.fp
        self.fp.seek(0)
        pickle.dump(self.domains, self.fp)
        print "after successful pickle.dump"

    def find_domain(self, name):
        print "find_domain: self.domains %s" % name
        print self.domains
        for item in self.domains:
            if item['name'] == name:
                return item
        print "domain does not exist\n"
        return []

    def list_domains(self):
        if self.domains == []:
            return []
        return [x['name'] for x in self.domains]

    def get_domain_info(self, instance_name):
        domain = self.find_domain(instance_name)
        if domain != []:
            return [domain['status'], domain['memory_mb'], \
                    domain['memory_mb'], \
                    domain['vcpus'], \
                    100]
        else:
            return [power_state.NOSTATE, '', '', '', '']
            #raise exception.NotFound("get_domain_info: No such doamin %s" \
            #                          % instance_name)
#_MK


def get_connection(read_only):
    # These are loaded late so that there's no need to install these
    # libraries when not using tilera.
    # Cheetah is separate because the unit tests want to load Cheetah,
    # but not tilera.
    #MK
    #global tilera
    #if tilera is None:
    #    tilera = __import__('tilera')
    #_MK
    global libxml2
    if libxml2 is None:
        libxml2 = __import__('libxml2')
    _late_load_cheetah()
    return tileraConnection(read_only)


def _late_load_cheetah():
    global Template
    if Template is None:
        t = __import__('Cheetah.Template', globals(), locals(), ['Template'],
                       -1)
        Template = t.Template


def _get_net_and_mask(cidr):
    net = IPy.IP(cidr)
    return str(net.net()), str(net.netmask())


def _get_net_and_prefixlen(cidr):
    net = IPy.IP(cidr)
    return str(net.net()), str(net.prefixlen())


def _get_ip_version(cidr):
        net = IPy.IP(cidr)
        return int(net.version())


class tileraConnection(object):

    def __init__(self, read_only):
        #self.tilera_uri = self.get_uri()

        self.tilera_xml = open(FLAGS.tilera_xml_template).read()
        self.interfaces_xml \
            = open(FLAGS.tilera_injected_network_template).read()
        self.cpuinfo_xml = open(FLAGS.cpuinfo_xml_template).read()
        self._wrapped_conn = None
        self.read_only = read_only

        #MK
        fw_class = utils.import_class(FLAGS.firewall_driver)
        self.tilera_firewall_driver = \
            fw_class(get_connection=self._get_connection)
        #self.nwfilter = NWFilterFirewall(self._get_connection)

        #if not FLAGS.tilera_firewall_driver:
        #    self.tilera_firewall_driver = self.nwfilter
        #    self.nwfilter.handle_security_groups = True
        #else:
        #    self.tilera_firewall_driver \
        #        = utils.import_object(FLAGS.tilera_firewall_driver)
        #
        #_MK

    def init_host(self, host):
        # Adopt existing VM's running here
        ctxt = context.get_admin_context()
        for instance in db.instance_get_all_by_host(ctxt, host):
            try:
                LOG.debug(_('Checking state of %s'), instance['name'])
                state = self.get_info(instance['name'])['state']
            except exception.NotFound:
                state = power_state.SHUTOFF

            LOG.debug(_('Current state of %(name)s was %(state)s.'),
                          {'name': instance['name'], 'state': state})
            db.instance_set_state(ctxt, instance['id'], state)

            if state == power_state.SHUTOFF:
                # TODO(soren): This is what the compute manager does when you
                # terminate # an instance. At some point I figure we'll have a
                # "terminated" state and some sort of cleanup job that runs
                # occasionally, cleaning them out.
                db.instance_destroy(ctxt, instance['id'])

            if state != power_state.RUNNING:
                continue
            self.firewall_driver.prepare_instance_filter(instance)
            self.firewall_driver.apply_instance_filter(instance)

    def _get_connection(self):
        #MK
        #if not self._wrapped_conn or not self._test_connection():
        #    LOG.debug(_('Connecting to libvirt: %s'), self.tilera_uri)
        #    self._wrapped_conn = self._connect(self.tilera_uri,
        #                                       self.read_only)
        self._wrapped_conn = fake_doms
        #_MK
        return self._wrapped_conn
    _conn = property(_get_connection)

    #def get_uri(self):
    #    if FLAGS.tilera_type == 'uml':
    #        uri = FLAGS.tilera_uri or 'uml:///system'
    #    elif FLAGS.tilera_type == 'xen':
    #        uri = FLAGS.tilera_uri or 'xen:///'
    #    else:
    #        uri = FLAGS.tilera_uri or 'qemu:///system'
    #    return uri

    def list_instances(self):
        return self._conn.list_domains()  # MK

    def destroy(self, instance, cleanup=True):
        try:
            self._conn.destroy_domain(instance['name'])
            db.instance_set_state(context.get_admin_context(),
                                  instance['id'], power_state.SHUTDOWN)
        except Exception as _err:
            pass
            # If the instance is already terminated, we're still happy

        #self.firewall_driver.unfilter_instance(instance)

        if cleanup:
            self._cleanup(instance)

        return True

    def _cleanup(self, instance):
        target = os.path.join(FLAGS.instances_path, instance['name'])
        instance_name = instance['name']
        LOG.info(_('instance %(instance_name)s: deleting instance files'
                ' %(target)s') % locals())
        if os.path.exists(target):
            shutil.rmtree(target)

    @exception.wrap_exception
    def attach_volume(self, instance_name, device_path, mountpoint):
        raise exception.APIError("attach_volume not supported for tilera.")

    def detach_volume(self, instance_name, mountpoint):
        raise exception.APIError("detach_volume not supported for tilera.")

    def snapshot(self, instance, image_id):
        """ Create snapshot from a running VM instance """
        raise NotImplementedError(
            _("Instance snapshotting is not supported for libvirt"
              "at this time"))

    @exception.wrap_exception
    def reboot(self, instance):
        timer = utils.LoopingCall(f=None)

        def _wait_for_reboot():
            try:
                state = self._conn.reboot_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: rebooted'), instance['name'])
                    timer.stop()
            except:
                LOG.exception(_('_wait_for_reboot failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def pause(self, instance, callback):
        raise exception.APIError("pause not supported for tilera.")

    @exception.wrap_exception
    def unpause(self, instance, callback):
        raise exception.APIError("unpause not supported for tilera.")

    @exception.wrap_exception
    def suspend(self, instance, callback):
        raise exception.APIError("suspend not supported for tilera")

    @exception.wrap_exception
    def resume(self, instance, callback):
        raise exception.APIError("resume not supported for tilera")

    @exception.wrap_exception
    def rescue(self, instance):
        self.destroy(instance, False)

        xml_dict = self.to_xml_dict(instance, rescue=True)
        rescue_images = {'image_id': FLAGS.tilera_rescue_image_id,
                         'kernel_id': FLAGS.tilera_rescue_kernel_id,
                         'ramdisk_id': FLAGS.tilera_rescue_ramdisk_id}
        #self._create_image(instance, xml, '.rescue', rescue_images)
        #self._conn.createXML(xml, 0)

        timer = utils.LoopingCall(f=None)

        def _wait_for_rescue():
            try:
                state = self._conn.reboot_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: rescued'), instance['name'])
                    timer.stop()
            except:
                LOG.exception(_('_wait_for_rescue failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def unrescue(self, instance):
        # NOTE(vish): Because reboot destroys and recreates an instance using
        #             the normal xml file, we can just call reboot here
        self.reboot(instance)

    @exception.wrap_exception
    def spawn(self, instance):
        LOG.debug(_("<============= spawn of tilera =============>"))  # MK
        xml_dict = self.to_xml_dict(instance)
        db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.NOSTATE,
                              'launching')

        #self.tilera_firewall_driver.setup_basic_filtering(instance)#MK
        self.tilera_firewall_driver.prepare_instance_filter(instance)
        #self._create_image(instance, xml)
        #self._conn.createXML(xml, 0)
        LOG.debug(_("instance %s: is running"), instance['name'])
        self.tilera_firewall_driver.apply_instance_filter(instance)

        suffix = ''

        def basepath(fname='', suffix=suffix):
            return os.path.join(FLAGS.instances_path,
                                instance['name'],
                                fname + suffix)

        # ensure directories exist and are writable
        #utils.execute('mkdir -p %s' % basepath(suffix=''))
        #utils.execute('chmod 0777 %s' % basepath(suffix=''))
        utils.execute('mkdir', '-p', basepath(suffix=''))
        utils.execute('chmod', '0777', basepath(suffix=''))

        LOG.info(_('instance %s: Creating image'), instance['name'])
        f = open(basepath('tilera.xml'), 'w')
        #f.write(tilera_xml) #####BUG?
        f.close()

        # NOTE(vish): No need add the suffix to console.log
        os.close(os.open(basepath('console.log', ''),
                         os.O_CREAT | os.O_WRONLY, 0660))

        user = manager.AuthManager().get_user(instance['user_id'])
        project = manager.AuthManager().get_project(instance['project_id'])

        disk_images = None  # MK
        if not disk_images:
            disk_images = {'image_id': instance['image_id'],
                           'kernel_id': instance['kernel_id'],
                           'ramdisk_id': instance['ramdisk_id']}

        #if disk_images['kernel_id']:
        #    fname = '%08x' % int(disk_images['kernel_id'])
        #    self._cache_image(fn=self._fetch_image,
        #                      target=basepath('kernel'),
        #                      fname=fname,
        #                      image_id=disk_images['kernel_id'],
        #                      user=user,
        #                      project=project)
        #    if disk_images['ramdisk_id']:
        #        fname = '%08x' % int(disk_images['ramdisk_id'])
        #        self._cache_image(fn=self._fetch_image,
        #                          target=basepath('ramdisk'),
        #                          fname=fname,
        #                          image_id=disk_images['ramdisk_id'],
        #                          user=user,
        #                          project=project)

        #root_fname = '%08x' % int(disk_images['image_id'])
        #size = FLAGS.minimum_root_size
        #if instance['instance_type'] == 'm1.tiny' or suffix == '.rescue':
        #    size = None
        #    root_fname += "_sm"

        #self._cache_image(fn=self._fetch_image,
        #                  target=basepath('disk'),
        #                  fname=root_fname,
        #                  cow=FLAGS.use_cow_images,
        #                  image_id=disk_images['image_id'],
        #                  user=user,
        #                  project=project,
        #                  size=size)
        #type_data = \
        #    instance_types.get_instance_type(instance['instance_type'])

        #if type_data['local_gb']:
        #    self._cache_image(fn=self._create_local,
        #                      target=basepath('disk.local'),
        #                      fname="local_%s" % type_data['local_gb'],
        #                      cow=FLAGS.use_cow_images,
        #                      local_gb=type_data['local_gb'])

        #MK
        #Test: copying original tilera images
        #utils.execute('cp /tftpboot/tilera_fs %s/root' % basepath(suffix=''))
        utils.execute('cp', '/tftpboot/tilera_fs_1G', '/tftpboot/tilera_fs')
        path_root = basepath(suffix='') + "/root"
        utils.execute('cp', '/tftpboot/tilera_fs', path_root)
        #_MK

        #def execute(cmd, process_input=None, check_exit_code=True):
        #    return utils.execute(cmd=cmd,
        #                         process_input=process_input,
        #                         check_exit_code=check_exit_code)
        ### _END_OF_CHANGE

        # For now, we assume that if we're not using a kernel, we're using a
        # partitioned disk image where the target partition is the first
        # partition
        target_partition = None
        if not instance['kernel_id']:
            target_partition = "1"

        key = str(instance['key_data'])
        net = None
        network_ref = db.network_get_by_instance(context.get_admin_context(),
                                                 instance['id'])
        if network_ref['injected']:
            admin_context = context.get_admin_context()
            address = db.instance_get_fixed_address(admin_context, \
                instance['id'])
            address_v6 = None
            if FLAGS.use_ipv6:
                address_v6 = db.instance_get_fixed_address_v6(admin_context,
                    inst['id'])

            interfaces_info = {'address': address,
                               'netmask': network_ref['netmask'],
                               'gateway': network_ref['gateway'],
                               'broadcast': network_ref['broadcast'],
                               'dns': network_ref['dns'],
                               'address_v6': address_v6,
                               'gateway_v6': network_ref['gateway_v6'],
                               'netmask_v6': network_ref['netmask_v6'],
                               'use_ipv6': FLAGS.use_ipv6}

            net = str(Template(self.interfaces_xml,
                searchList=[interfaces_info]))
        if key or net:
            inst_name = instance['name']
            img_id = instance.image_id
            if key:
                LOG.info(_('instance %(inst_name)s: injecting key into'
                        ' image %(img_id)s') % locals())
            if net:
                LOG.info(_('instance %(inst_name)s: injecting net into'
                        ' image %(img_id)s') % locals())
            try:
                #MK
                #disk.inject_data(basepath('disk'), key, net,
                disk.inject_data(basepath('root'), key, net,
                                 partition=target_partition,
                                 nbd=FLAGS.use_cow_images)
            except Exception as e:
                # This could be a windows image, or a vmdk format disk
                LOG.warn(_('instance %(inst_name)s: ignoring error injecting'
                        ' data into image %(img_id)s (%(e)s)') % locals())

        if FLAGS.tilera_type == 'uml':
            utils.execute('sudo', 'chown', 'root', basepath('disk'))

        #Back to spawn
        bpath = basepath(suffix='')

        timer = utils.LoopingCall(f=None)

        def _wait_for_boot():
            try:
                print xml_dict  # MK
                state = self._conn.create_domain(xml_dict, bpath)
                LOG.debug(_('~~~~~~ current state = %s ~~~~~~') % state)  # MK
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: booted'), instance['name'])
                    timer.stop()
            except:
                LOG.exception(_('instance %s: failed to boot'),
                              instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'],
                                      power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_boot
        return timer.start(interval=0.5, now=True)

    def _flush_xen_console(self, virsh_output):
        LOG.info(_('virsh said: %r'), virsh_output)
        virsh_output = virsh_output[0].strip()

        if virsh_output.startswith('/dev/'):
            LOG.info(_("cool, it's a device"))
            out, err = utils.execute('sudo', 'dd',
                                     "if=%s" % virsh_output,
                                     'iflag=nonblock',
                                     check_exit_code=False)
            return out
        else:
            return ''

    def _append_to_file(self, data, fpath):
        LOG.info(_('data: %(data)r, fpath: %(fpath)r') % locals())
        fp = open(fpath, 'a+')
        fp.write(data)
        return fpath

    def _dump_file(self, fpath):
        fp = open(fpath, 'r+')
        contents = fp.read()
        LOG.info(_('Contents of file %(fpath)s: %(contents)r') % locals())
        return contents

    @exception.wrap_exception
    def get_console_output(self, instance):
        console_log = os.path.join(FLAGS.instances_path, instance['name'],
                                   'console.log')

        utils.execute('sudo', 'chown', os.getuid(), console_log)

        if FLAGS.tilera_type == 'xen':
            # Xen is special
            virsh_output = utils.execute('virsh', 'ttyconsole',
                                         instance['name'])
            data = self._flush_xen_console(virsh_output)
            fpath = self._append_to_file(data, console_log)
        else:
            fpath = console_log

        return self._dump_file(fpath)

    @exception.wrap_exception
    def get_ajax_console(self, instance):
        #MK
        raise NotImplementedError()
        #def get_open_port():
        #    start_port, end_port = FLAGS.ajaxterm_portrange.split("-")
        #    for i in xrange(0, 100):  # don't loop forever
        #        port = random.randint(int(start_port), int(end_port))
        #        # netcat will exit with 0 only if the port is in use,
        #        # so a nonzero return value implies it is unused
        #        cmd = 'netcat', '0.0.0.0', port, '-w', '1'
        #        try:
        #            stdout, stderr = utils.execute(*cmd, process_input='')
        #        except exception.ProcessExecutionError:
        #            return port
        #    raise Exception(_('Unable to find an open port'))

        #def get_pty_for_instance(instance_name):
        #    virt_dom = self._conn.lookupByName(instance_name)
        #    xml = virt_dom.XMLDesc(0)
        #    dom = minidom.parseString(xml)

        #    for serial in dom.getElementsByTagName('serial'):
        #        if serial.getAttribute('type') == 'pty':
        #            source = serial.getElementsByTagName('source')[0]
        #            return source.getAttribute('path')
        #port = get_open_port()
        #token = str(uuid.uuid4())
        #host = instance['host']

        #ajaxterm_cmd = 'sudo socat - %s' \
        #               % get_pty_for_instance(instance['name'])

        #cmd = '%s/tools/ajaxterm/ajaxterm.py --command "%s" -t %s -p %s' \
        #      % (utils.novadir(), ajaxterm_cmd, token, port)

        #subprocess.Popen(cmd, shell=True)
        #return {'token': token, 'host': host, 'port': port}
        #_MK

    _image_sems = {}

    def _cache_image(self, fn, target, fname, cow=False, *args, **kwargs):
        #MK
        raise NotImplementedError()
        """Wrapper for a method that creates an image that caches the image.

        This wrapper will save the image into a common store and create a
        copy for use by the hypervisor.

        The underlying method should specify a kwarg of target representing
        where the image will be saved.

        fname is used as the filename of the base image.  The filename needs
        to be unique to a given image.

        If cow is True, it will make a CoW image instead of a copy.
        """
        #if not os.path.exists(target):
        #    base_dir = os.path.join(FLAGS.instances_path, '_base')
        #    if not os.path.exists(base_dir):
        #        os.mkdir(base_dir)
        #        os.chmod(base_dir, 0777)
        #    base = os.path.join(base_dir, fname)
        #    if not os.path.exists(base):
        #        fn(target=base, *args, **kwargs)
        #    if cow:
        #        utils.execute('qemu-img create -f qcow2 -o '
        #                      'cluster_size=2M,backing_file=%s %s'
        #                      % (base, target))
        #    else:
        #        utils.execute('cp %s %s' % (base, target))

    def _fetch_image(self, target, image_id, user, project, size=None):
        """Grab image and optionally attempt to resize it"""
        #MK
        raise NotImplementedError()
        #images.fetch(image_id, target, user, project)
        #if size:
        #    disk.extend(target, size)

    def _create_local(self, target, local_gb):
        """Create a blank image of specified size"""
        #MK
        raise NotImplementedError()
        #utils.execute('truncate %s -s %dG' % (target, local_gb))
        # TODO(vish): should we format disk by default?

    def _create_image(self, inst, libvirt_xml, suffix='', disk_images=None):
        #MK
        raise NotImplementedError()

    def to_xml_dict(self, instance, rescue=False):
        # TODO(termie): cache?
        LOG.debug(_('instance %s: starting toXML method'), instance['name'])
        network = db.project_get_network(context.get_admin_context(),
                                         instance['project_id'])
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        # FIXME(vish): stick this in db
        instance_type = instance['instance_type']
        #instance_type = instance_types.INSTANCE_TYPES[instance_type]
        instance_type = instance_types.get_instance_type(instance_type)
        ip_address = db.instance_get_fixed_address(context.get_admin_context(),
                                                   instance['id'])
        # Assume that the gateway also acts as the dhcp server.
        dhcp_server = network['gateway']
        gateway_v6 = network['gateway_v6']

        if FLAGS.tilera_allow_project_net_traffic:
            if FLAGS.use_ipv6:
                net, mask = _get_net_and_mask(network['cidr'])
                net_v6, prefixlen_v6 = _get_net_and_prefixlen(
                                           network['cidr_v6'])
                extra_params = ("<parameter name=\"PROJNET\" "
                            "value=\"%s\" />\n"
                            "<parameter name=\"PROJMASK\" "
                            "value=\"%s\" />\n"
                            "<parameter name=\"PROJNETV6\" "
                            "value=\"%s\" />\n"
                            "<parameter name=\"PROJMASKV6\" "
                            "value=\"%s\" />\n") % \
                              (net, mask, net_v6, prefixlen_v6)
            else:
                net, mask = _get_net_and_mask(network['cidr'])
                extra_params = ("<parameter name=\"PROJNET\" "
                            "value=\"%s\" />\n"
                            "<parameter name=\"PROJMASK\" "
                            "value=\"%s\" />\n") % \
                              (net, mask)
        else:
            extra_params = "\n"
        if FLAGS.use_cow_images:
            driver_type = 'qcow2'
        else:
            driver_type = 'raw'

        xml_info = {'type': FLAGS.tilera_type,
                    'name': instance['name'],
                    'basepath': os.path.join(FLAGS.instances_path,
                                             instance['name']),
                    'memory_kb': instance_type['memory_mb'] * 1024,
                    'vcpus': instance_type['vcpus'],
                    'bridge_name': network['bridge'],
                    'mac_address': instance['mac_address'],
                    'ip_address': ip_address,
                    'dhcp_server': dhcp_server,
                    'extra_params': extra_params,
                    'image_id': instance['image_id'],  # MK
                    'kernel_id': instance['kernel_id'],  # MK
                    'ramdisk_id': instance['ramdisk_id'],  # MK
                    'rescue': rescue,
                    'local': instance_type['local_gb'],
                    'driver_type': driver_type}

        if gateway_v6:
            xml_info['gateway_v6'] = gateway_v6 + "/128"

        #MK
        #if not rescue:
        #    if instance['kernel_id']:
        #        xml_info['kernel'] = xml_info['basepath'] + "/kernel"

        #    if instance['ramdisk_id']:
        #        xml_info['ramdisk'] = xml_info['basepath'] + "/ramdisk"

        #    xml_info['disk'] = xml_info['basepath'] + "/disk"

        xml = str(Template(self.tilera_xml, searchList=[xml_info]))
        LOG.debug(_('instance %s: finished toXML method'),
                        instance['name'])

        #return xml
        #_MK
        print xml_info
        return xml_info  # MK

    def get_info(self, instance_name):
        try:
            (state, max_mem, mem, num_cpu, cpu_time) \
                = self._conn.get_domain_info(instance_name)
        except:
            raise exception.NotFound(_("Instance %s not found")
                                     % instance_name)
        return {'state': state,
                'max_mem': max_mem,
                'mem': mem,
                'num_cpu': num_cpu,
                'cpu_time': cpu_time}

    def get_diagnostics(self, instance_name):
        raise exception.APIError("diagnostics are not supported for libvirt")

    def get_disks(self, instance_name):
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.

        Returns a list of all block devices for this domain.
        """
        #MK
        raise NotImplementedError()
        #domain = self._conn.lookupByName(instance_name)
        ## TODO(devcamcar): Replace libxml2 with etree.
        #xml = domain.XMLDesc(0)
        #doc = None

        #try:
        #    doc = libxml2.parseDoc(xml)
        #except:
        #    return []

        #ctx = doc.xpathNewContext()
        #disks = []

        #try:
        #    ret = ctx.xpathEval('/domain/devices/disk')

        #    for node in ret:
        #        devdst = None

        #        for child in node.children:
        #            if child.name == 'target':
        #                devdst = child.prop('dev')

        #        if devdst == None:
        #            continue

        #        disks.append(devdst)
        #finally:
        #    if ctx != None:
        #        ctx.xpathFreeContext()
        #    if doc != None:
        #        doc.freeDoc()

        #return disks
        #_MK

    def get_interfaces(self, instance_name):
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.

        Returns a list of all network interfaces for this instance.
        """
        #MK
        raise NotImplementedError()
        #domain = self._conn.lookupByName(instance_name)
        ## TODO(devcamcar): Replace libxml2 with etree.
        #xml = domain.XMLDesc(0)
        #doc = None

        #try:
        #    doc = libxml2.parseDoc(xml)
        #except:
        #    return []

        #ctx = doc.xpathNewContext()
        #interfaces = []

        #try:
        #    ret = ctx.xpathEval('/domain/devices/interface')

        #    for node in ret:
        #        devdst = None

        #        for child in node.children:
        #            if child.name == 'target':
        #                devdst = child.prop('dev')

        #        if devdst == None:
        #            continue

        #        interfaces.append(devdst)
        #finally:
        #    if ctx != None:
        #        ctx.xpathFreeContext()
        #    if doc != None:
        #        doc.freeDoc()

        #return interfaces
        #_MK

    def get_vcpu_total(self):
        """Get vcpu number of physical computer.

        :returns: the number of cpu core.

        """

        # On certain platforms, this will raise a NotImplementedError.
        try:
            #MK
            #return multiprocessing.cpu_count()
            return tilera_boards.get_tilera_hw_info('vcpus')  # 10
            #_MK
        except NotImplementedError:
            LOG.warn(_("Cannot get the number of cpu, because this "
                       "function is not implemented for this platform. "
                       "This error can be safely ignored for now."))
            return 0

    def get_memory_mb_total(self):
        """Get the total memory size(MB) of physical computer.

        :returns: the total amount of memory(MB).

        """

        #MK
        #if sys.platform.upper() != 'LINUX2':
        #    return 0

        #meminfo = open('/proc/meminfo').read().split()
        #idx = meminfo.index('MemTotal:')
        ## transforming kb to mb.
        #return int(meminfo[idx + 1]) / 1024
        return tilera_boards.get_tilera_hw_info('memory_mb')  # 16218
        #_MK

    def get_local_gb_total(self):
        """Get the total hdd size(GB) of physical computer.

        :returns:
            The total amount of HDD(GB).
            Note that this value shows a partition where
            NOVA-INST-DIR/instances mounts.

        """

        #MK
        #hddinfo = os.statvfs(FLAGS.instances_path)
        #return hddinfo.f_frsize * hddinfo.f_blocks / 1024 / 1024 / 1024
        return tilera_boards.get_tilera_hw_info('local_gb')  # 917
        #_MK

    def get_vcpu_used(self):
        """ Get vcpu usage number of physical computer.

        :returns: The total number of vcpu that currently used.

        """

        total = 0
        #MK
        #for dom_id in self._conn.listDomainsID():
        #    dom = self._conn.lookupByID(dom_id)
        #    total += len(dom.vcpus()[1])
        for dom_id in self._conn.list_domains():
            total += 1
        #_MK
        return total

    def get_memory_mb_used(self):
        """Get the free memory size(MB) of physical computer.

        :returns: the total usage of memory(MB).

        """

        #MK
        #if sys.platform.upper() != 'LINUX2':
        #    return 0

        #m = open('/proc/meminfo').read().split()
        #idx1 = m.index('MemFree:')
        #idx2 = m.index('Buffers:')
        #idx3 = m.index('Cached:')
        #avail = (int(m[idx1 + 1]) + int(m[idx2 + 1]) \
        #    + int(m[idx3 + 1])) / 1024
        #return  self.get_memory_mb_total() - avail
        return tilera_boards.get_tilera_hw_info('memory_mb_used')  # 476
        #_MK

    def get_local_gb_used(self):
        """Get the free hdd size(GB) of physical computer.

        :returns:
           The total usage of HDD(GB).
           Note that this value shows a partition where
           NOVA-INST-DIR/instances mounts.

        """

        #MK
        #hddinfo = os.statvfs(FLAGS.instances_path)
        #avail = hddinfo.f_frsize * hddinfo.f_bavail / 1024 / 1024 / 1024
        #return self.get_local_gb_total() - avail
        return tilera_boards.get_tilera_hw_info('local_gb_used')  # 1
        #_MK

    def get_hypervisor_type(self):
        """Get hypervisor type.

        :returns: hypervisor type (ex. qemu)

        """
        #MK
        #return self._conn.getType()
        return tilera_boards.get_tilera_hw_info('hypervisor_type')
        # 'tilera_hv'
        #_MK

    def get_hypervisor_version(self):
        """Get hypervisor version.

        :returns: hypervisor version (ex. 12003)

        """

        #MK
        #return self._conn.getVersion()
        return tilera_boards.get_tilera_hw_info('hypervisor_version')  # 1
        #_MK

    def get_cpu_info(self):
        """Get cpuinfo information.

        Obtains cpu feature from virConnect.getCapabilities,
        and returns as a json string.

        :return: see above description

        """

        #MK
        #xml = self._conn.getCapabilities()
        #xml = libxml2.parseDoc(xml)
        #nodes = xml.xpathEval('//host/cpu')
        #if len(nodes) != 1:
        #    raise exception.Invalid(_("Invalid xml. '<cpu>' must be 1,"
        #                              "but %d\n") % len(nodes)
        #                              + xml.serialize())

        #cpu_info = dict()
        #arch_nodes = xml.xpathEval('//host/cpu/arch')
        #if arch_nodes:
        #    cpu_info['arch'] = arch_nodes[0].getContent()
        #model_nodes = xml.xpathEval('//host/cpu/model')
        #if model_nodes:
        #    cpu_info['model'] = model_nodes[0].getContent()
        #vendor_nodes = xml.xpathEval('//host/cpu/vendor')
        #if vendor_nodes:
        #    cpu_info['vendor'] = vendor_nodes[0].getContent()
        #topology_nodes = xml.xpathEval('//host/cpu/topology')
        #topology = dict()
        #if topology_nodes:
        #    topology_node = topology_nodes[0].get_properties()
        #    while topology_node:
        #        name = topology_node.get_name()
        #        topology[name] = topology_node.getContent()
        #        topology_node = topology_node.get_next()
        #
        #    keys = ['cores', 'sockets', 'threads']
        #    tkeys = topology.keys()
        #    if set(tkeys) != set(keys):
        #        ks = ', '.join(keys)
        #        raise exception.Invalid(_("Invalid xml: topology"
        #                             "(%(topology)s) must have "
        #                             "%(ks)s") % locals())
        #
        #feature_nodes = xml.xpathEval('//host/cpu/feature')
        #
        #features = list()
        #for nodes in feature_nodes:
        #    features.append(nodes.get_properties().getContent())
        #cpu_info['topology'] = topology
        #cpu_info['features'] = features
        #return utils.dumps(cpu_info)
        return tilera_boards.get_tilera_hw_info('cpu_info')  # 'TILEPro64'
        #_MK

    def block_stats(self, instance_name, disk):
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.
        """
        #MK
        raise NotImplementedError()
        #domain = self._conn.lookupByName(instance_name)
        #return domain.blockStats(disk)
        #_MK

    def interface_stats(self, instance_name, interface):
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.
        """
        #MK
        raise NotImplementedError()
        #domain = self._conn.lookupByName(instance_name)
        #return domain.interfaceStats(interface)
        #_MK

    def get_console_pool_info(self, console_type):
        #TODO(mdragon): console proxy should be implemented for libvirt,
        #               in case someone wants to use it with kvm or
        #               such. For now return fake data.
        return  {'address': '127.0.0.1',
                 'username': 'fakeuser',
                 'password': 'fakepassword'}

    def refresh_security_group_rules(self, security_group_id):
        self.tilera_firewall_driver.\
            refresh_security_group_rules(security_group_id)

    def refresh_security_group_members(self, security_group_id):
        self.tilera_firewall_driver.\
            refresh_security_group_members(security_group_id)

    def update_available_resource(self, ctxt, host):
        """Updates compute manager resource info on ComputeNode table.

        This method is called when nova-coompute launches, and
        whenever admin executes "nova-manage service update_resource".

        :param ctxt: security context
        :param host: hostname that compute manager is currently running

        """

        try:
            service_ref = db.service_get_all_compute_by_host(ctxt, host)[0]
        except exception.NotFound:
            raise exception.Invalid(_("Cannot update compute manager "
                                      "specific info, because no service "
                                      "record was found."))

        # Updating host information
        dic = {'vcpus': self.get_vcpu_total(),
               'memory_mb': self.get_memory_mb_total(),
               'local_gb': self.get_local_gb_total(),
               'vcpus_used': self.get_vcpu_used(),
               'memory_mb_used': self.get_memory_mb_used(),
               'local_gb_used': self.get_local_gb_used(),
               'hypervisor_type': self.get_hypervisor_type(),
               'hypervisor_version': self.get_hypervisor_version(),
               'cpu_info': self.get_cpu_info(),
               #RLK
               'cpu_arch': FLAGS.cpu_arch,
               'xpu_arch': FLAGS.xpu_arch,
               'xpus': FLAGS.xpus,
               'xpu_info': FLAGS.xpu_info,
               'net_arch': FLAGS.net_arch,
               'net_info': FLAGS.net_info,
               'net_mbps': FLAGS.net_mbps
               }

        compute_node_ref = service_ref['compute_node']
        LOG.info(_('#### RLK: cpu_arch = %s ') % FLAGS.cpu_arch)
        if not compute_node_ref:
            LOG.info(_('Compute_service record created for %s ') % host)
            dic['service_id'] = service_ref['id']
            db.compute_node_create(ctxt, dic)
        else:
            LOG.info(_('Compute_service record updated for %s ') % host)
            db.compute_node_update(ctxt, compute_node_ref[0]['id'], dic)

    def compare_cpu(self, cpu_info):
        """Checks the host cpu is compatible to a cpu given by xml.

        "xml" must be a part of libvirt.openReadonly().getCapabilities().
        return values follows by virCPUCompareResult.
        if 0 > return value, do live migration.
        'http://libvirt.org/html/libvirt-libvirt.html#virCPUCompareResult'

        :param cpu_info: json string that shows cpu feature(see get_cpu_info())
        :returns:
            None. if given cpu info is not compatible to this server,
            raise exception.

        """

        LOG.info(_('Instance launched has CPU info:\n%s') % cpu_info)
        dic = utils.loads(cpu_info)
        xml = str(Template(self.cpuinfo_xml, searchList=dic))
        LOG.info(_('to xml...\n:%s ' % xml))

        u = "http://libvirt.org/html/libvirt-libvirt.html#virCPUCompareResult"
        m = _("CPU doesn't have compatibility.\n\n%(ret)s\n\nRefer to %(u)s")
        # unknown character exists in xml, then libvirt complains
        try:
            ret = self._conn.compareCPU(xml, 0)
        except libvirt.libvirtError, e:
            ret = e.message
            LOG.error(m % locals())
            raise

        if ret <= 0:
            raise exception.Invalid(m % locals())

        return

    def ensure_filtering_rules_for_instance(self, instance_ref):
        """Setting up filtering rules and waiting for its completion.

        To migrate an instance, filtering rules to hypervisors
        and firewalls are inevitable on destination host.
        ( Waiting only for filterling rules to hypervisor,
        since filtering rules to firewall rules can be set faster).

        Concretely, the below method must be called.
        - setup_basic_filtering (for nova-basic, etc.)
        - prepare_instance_filter(for nova-instance-instance-xxx, etc.)

        to_xml may have to be called since it defines PROJNET, PROJMASK.
        but libvirt migrates those value through migrateToURI(),
        so , no need to be called.

        Don't use thread for this method since migration should
        not be started when setting-up filtering rules operations
        are not completed.

        :params instance_ref: nova.db.sqlalchemy.models.Instance object

        """

        # If any instances never launch at destination host,
        # basic-filtering must be set here.
        self.firewall_driver.setup_basic_filtering(instance_ref)
        # setting up n)ova-instance-instance-xx mainly.
        self.firewall_driver.prepare_instance_filter(instance_ref)

        # wait for completion
        timeout_count = range(FLAGS.live_migration_retry_count)
        while timeout_count:
            try:
                filter_name = 'nova-instance-%s' % instance_ref.name
                self._conn.nwfilterLookupByName(filter_name)
                break
            except libvirt.libvirtError:
                timeout_count.pop()
                if len(timeout_count) == 0:
                    ec2_id = instance_ref['hostname']
                    iname = instance_ref.name
                    msg = _('Timeout migrating for %(ec2_id)s(%(iname)s)')
                    raise exception.Error(msg % locals())
                time.sleep(1)

    def live_migration(self, ctxt, instance_ref, dest,
                       post_method, recover_method):
        """Spawning live_migration operation for distributing high-load.

        :params ctxt: security context
        :params instance_ref:
            nova.db.sqlalchemy.models.Instance object
            instance object that is migrated.
        :params dest: destination host
        :params post_method:
            post operation method.
            expected nova.compute.manager.post_live_migration.
        :params recover_method:
            recovery method when any exception occurs.
            expected nova.compute.manager.recover_live_migration.

        """

        greenthread.spawn(self._live_migration, ctxt, instance_ref, dest,
                          post_method, recover_method)

    def _live_migration(self, ctxt, instance_ref, dest,
                        post_method, recover_method):
        """Do live migration.

        :params ctxt: security context
        :params instance_ref:
            nova.db.sqlalchemy.models.Instance object
            instance object that is migrated.
        :params dest: destination host
        :params post_method:
            post operation method.
            expected nova.compute.manager.post_live_migration.
        :params recover_method:
            recovery method when any exception occurs.
            expected nova.compute.manager.recover_live_migration.

        """

        # Do live migration.
        try:
            flaglist = FLAGS.live_migration_flag.split(',')
            flagvals = [getattr(libvirt, x.strip()) for x in flaglist]
            logical_sum = reduce(lambda x, y: x | y, flagvals)

            if self.read_only:
                tmpconn = self._connect(self.libvirt_uri, False)
                dom = tmpconn.lookupByName(instance_ref.name)
                dom.migrateToURI(FLAGS.live_migration_uri % dest,
                                 logical_sum,
                                 None,
                                 FLAGS.live_migration_bandwidth)
                tmpconn.close()
            else:
                dom = self._conn.lookupByName(instance_ref.name)
                dom.migrateToURI(FLAGS.live_migration_uri % dest,
                                 logical_sum,
                                 None,
                                 FLAGS.live_migration_bandwidth)

        except Exception:
            recover_method(ctxt, instance_ref)
            raise

        # Waiting for completion of live_migration.
        timer = utils.LoopingCall(f=None)

        def wait_for_live_migration():
            """waiting for live migration completion"""
            try:
                self.get_info(instance_ref.name)['state']
            except exception.NotFound:
                timer.stop()
                post_method(ctxt, instance_ref, dest)

        timer.f = wait_for_live_migration
        timer.start(interval=0.5, now=True)

    def unfilter_instance(self, instance_ref):
        """See comments of same method in firewall_driver."""
        self.firewall_driver.unfilter_instance(instance_ref)


class FirewallDriver(object):
    def prepare_instance_filter(self, instance):
        """Prepare filters for the instance.

        At this point, the instance isn't running yet."""
        raise NotImplementedError()

    def unfilter_instance(self, instance):
        """Stop filtering instance"""
        raise NotImplementedError()

    def apply_instance_filter(self, instance):
        """Apply instance filter.

        Once this method returns, the instance should be firewalled
        appropriately. This method should as far as possible be a
        no-op. It's vastly preferred to get everything set up in
        prepare_instance_filter.
        """
        raise NotImplementedError()

    def refresh_security_group_rules(self, security_group_id):
        """Refresh security group rules from data store

        Gets called when a rule has been added to or removed from
        the security group."""
        raise NotImplementedError()

    def refresh_security_group_members(self, security_group_id):
        """Refresh security group members from data store

        Gets called when an instance gets added to or removed from
        the security group."""
        raise NotImplementedError()

    def setup_basic_filtering(self, instance):
        """Create rules to block spoofing and allow dhcp.

        This gets called when spawning an instance, before
        :method:`prepare_instance_filter`.

        """
        raise NotImplementedError()

    def _gateway_v6_for_instance(self, instance):
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        return network['gateway_v6']


class NWFilterFirewall(FirewallDriver):
    """
    This class implements a network filtering mechanism versatile
    enough for EC2 style Security Group filtering by leveraging
    libvirt's nwfilter.

    First, all instances get a filter ("nova-base-filter") applied.
    This filter provides some basic security such as protection against
    MAC spoofing, IP spoofing, and ARP spoofing.

    This filter drops all incoming ipv4 and ipv6 connections.
    Outgoing connections are never blocked.

    Second, every security group maps to a nwfilter filter(*).
    NWFilters can be updated at runtime and changes are applied
    immediately, so changes to security groups can be applied at
    runtime (as mandated by the spec).

    Security group rules are named "nova-secgroup-<id>" where <id>
    is the internal id of the security group. They're applied only on
    hosts that have instances in the security group in question.

    Updates to security groups are done by updating the data model
    (in response to API calls) followed by a request sent to all
    the nodes with instances in the security group to refresh the
    security group.

    Each instance has its own NWFilter, which references the above
    mentioned security group NWFilters. This was done because
    interfaces can only reference one filter while filters can
    reference multiple other filters. This has the added benefit of
    actually being able to add and remove security groups from an
    instance at run time. This functionality is not exposed anywhere,
    though.

    Outstanding questions:

    The name is unique, so would there be any good reason to sync
    the uuid across the nodes (by assigning it from the datamodel)?


    (*) This sentence brought to you by the redundancy department of
        redundancy.

    """

    def __init__(self, get_connection, **kwargs):
        self._libvirt_get_connection = get_connection
        self.static_filters_configured = False
        self.handle_security_groups = False

    def apply_instance_filter(self, instance):
        """No-op. Everything is done in prepare_instance_filter"""
        pass

    def _get_connection(self):
        return self._libvirt_get_connection()
    _conn = property(_get_connection)

    def nova_dhcp_filter(self):
        """The standard allow-dhcp-server filter is an <ip> one, so it uses
           ebtables to allow traffic through. Without a corresponding rule in
           iptables, it'll get blocked anyway."""

        return '''<filter name='nova-allow-dhcp-server' chain='ipv4'>
                    <uuid>891e4787-e5c0-d59b-cbd6-41bc3c6b36fc</uuid>
                    <rule action='accept' direction='out'
                          priority='100'>
                      <udp srcipaddr='0.0.0.0'
                           dstipaddr='255.255.255.255'
                           srcportstart='68'
                           dstportstart='67'/>
                    </rule>
                    <rule action='accept' direction='in'
                          priority='100'>
                      <udp srcipaddr='$DHCPSERVER'
                           srcportstart='67'
                           dstportstart='68'/>
                    </rule>
                  </filter>'''

    def nova_ra_filter(self):
        return '''<filter name='nova-allow-ra-server' chain='root'>
                            <uuid>d707fa71-4fb5-4b27-9ab7-ba5ca19c8804</uuid>
                              <rule action='accept' direction='inout'
                                    priority='100'>
                                <icmpv6 srcipaddr='$RASERVER'/>
                              </rule>
                            </filter>'''

    def setup_basic_filtering(self, instance):
        """Set up basic filtering (MAC, IP, and ARP spoofing protection)"""
        logging.info('called setup_basic_filtering in nwfilter')

        if self.handle_security_groups:
            # No point in setting up a filter set that we'll be overriding
            # anyway.
            return

        logging.info('ensuring static filters')
        self._ensure_static_filters()

        instance_filter_name = self._instance_filter_name(instance)
        self._define_filter(self._filter_container(instance_filter_name,
                                                   ['nova-base']))

    def _ensure_static_filters(self):
        if self.static_filters_configured:
            return

        self._define_filter(self._filter_container('nova-base',
                                                   ['no-mac-spoofing',
                                                    'no-ip-spoofing',
                                                    'no-arp-spoofing',
                                                    'allow-dhcp-server']))
        self._define_filter(self.nova_base_ipv4_filter)
        self._define_filter(self.nova_base_ipv6_filter)
        self._define_filter(self.nova_dhcp_filter)
        self._define_filter(self.nova_ra_filter)
        self._define_filter(self.nova_vpn_filter)
        if FLAGS.allow_project_net_traffic:
            self._define_filter(self.nova_project_filter)
            if FLAGS.use_ipv6:
                self._define_filter(self.nova_project_filter_v6)

        self.static_filters_configured = True

    def _filter_container(self, name, filters):
        xml = '''<filter name='%s' chain='root'>%s</filter>''' % (
                 name,
                 ''.join(["<filterref filter='%s'/>" % (f,) for f in filters]))
        return xml

    nova_vpn_filter = '''<filter name='nova-vpn' chain='root'>
                           <uuid>2086015e-cf03-11df-8c5d-080027c27973</uuid>
                           <filterref filter='allow-dhcp-server'/>
                           <filterref filter='nova-allow-dhcp-server'/>
                           <filterref filter='nova-base-ipv4'/>
                           <filterref filter='nova-base-ipv6'/>
                         </filter>'''

    def nova_base_ipv4_filter(self):
        retval = "<filter name='nova-base-ipv4' chain='ipv4'>"
        for protocol in ['tcp', 'udp', 'icmp']:
            for direction, action, priority in [('out', 'accept', 399),
                                                ('in', 'drop', 400)]:
                retval += """<rule action='%s' direction='%s' priority='%d'>
                               <%s />
                             </rule>""" % (action, direction,
                                              priority, protocol)
        retval += '</filter>'
        return retval

    def nova_base_ipv6_filter(self):
        retval = "<filter name='nova-base-ipv6' chain='ipv6'>"
        for protocol in ['tcp-ipv6', 'udp-ipv6', 'icmpv6']:
            for direction, action, priority in [('out', 'accept', 399),
                                                ('in', 'drop', 400)]:
                retval += """<rule action='%s' direction='%s' priority='%d'>
                               <%s />
                             </rule>""" % (action, direction,
                                              priority, protocol)
        retval += '</filter>'
        return retval

    def nova_project_filter(self):
        retval = "<filter name='nova-project' chain='ipv4'>"
        for protocol in ['tcp', 'udp', 'icmp']:
            retval += """<rule action='accept' direction='in' priority='200'>
                           <%s srcipaddr='$PROJNET' srcipmask='$PROJMASK' />
                         </rule>""" % protocol
        retval += '</filter>'
        return retval

    def nova_project_filter_v6(self):
        retval = "<filter name='nova-project-v6' chain='ipv6'>"
        for protocol in ['tcp-ipv6', 'udp-ipv6', 'icmpv6']:
            retval += """<rule action='accept' direction='inout'
                                                   priority='200'>
                           <%s srcipaddr='$PROJNETV6'
                               srcipmask='$PROJMASKV6' />
                         </rule>""" % (protocol)
        retval += '</filter>'
        return retval

    def _define_filter(self, xml):
        if callable(xml):
            xml = xml()
        # execute in a native thread and block current greenthread until done
        tpool.execute(self._conn.nwfilterDefineXML, xml)

    def unfilter_instance(self, instance):
        # Nothing to do
        pass

    def prepare_instance_filter(self, instance):
        """
        Creates an NWFilter for the given instance. In the process,
        it makes sure the filters for the security groups as well as
        the base filter are all in place.
        """
        if instance['image_id'] == FLAGS.vpn_image_id:
            base_filter = 'nova-vpn'
        else:
            base_filter = 'nova-base'

        instance_filter_name = self._instance_filter_name(instance)
        instance_secgroup_filter_name = '%s-secgroup' % (instance_filter_name,)
        instance_filter_children = [base_filter, instance_secgroup_filter_name]
        instance_secgroup_filter_children = ['nova-base-ipv4',
                                             'nova-base-ipv6',
                                             'nova-allow-dhcp-server']
        if FLAGS.use_ipv6:
            gateway_v6 = self._gateway_v6_for_instance(instance)
            if gateway_v6:
                instance_secgroup_filter_children += ['nova-allow-ra-server']

        ctxt = context.get_admin_context()

        if FLAGS.allow_project_net_traffic:
            instance_filter_children += ['nova-project']
            if FLAGS.use_ipv6:
                instance_filter_children += ['nova-project-v6']

        for security_group in db.security_group_get_by_instance(ctxt,
                                                               instance['id']):

            self.refresh_security_group_rules(security_group['id'])

            instance_secgroup_filter_children += [('nova-secgroup-%s' %
                                                         security_group['id'])]

        self._define_filter(
                    self._filter_container(instance_secgroup_filter_name,
                                           instance_secgroup_filter_children))

        self._define_filter(
                    self._filter_container(instance_filter_name,
                                           instance_filter_children))

        return

    def refresh_security_group_rules(self, security_group_id):
        return self._define_filter(
                   self.security_group_to_nwfilter_xml(security_group_id))

    def security_group_to_nwfilter_xml(self, security_group_id):
        security_group = db.security_group_get(context.get_admin_context(),
                                               security_group_id)
        rule_xml = ""
        v6protocol = {'tcp': 'tcp-ipv6', 'udp': 'udp-ipv6', 'icmp': 'icmpv6'}
        for rule in security_group.rules:
            rule_xml += "<rule action='accept' direction='in' priority='300'>"
            if rule.cidr:
                version = _get_ip_version(rule.cidr)
                if(FLAGS.use_ipv6 and version == 6):
                    net, prefixlen = _get_net_and_prefixlen(rule.cidr)
                    rule_xml += "<%s srcipaddr='%s' srcipmask='%s' " % \
                                (v6protocol[rule.protocol], net, prefixlen)
                else:
                    net, mask = _get_net_and_mask(rule.cidr)
                    rule_xml += "<%s srcipaddr='%s' srcipmask='%s' " % \
                                (rule.protocol, net, mask)
                if rule.protocol in ['tcp', 'udp']:
                    rule_xml += "dstportstart='%s' dstportend='%s' " % \
                                (rule.from_port, rule.to_port)
                elif rule.protocol == 'icmp':
                    LOG.info('rule.protocol: %r, rule.from_port: %r, '
                             'rule.to_port: %r', rule.protocol,
                             rule.from_port, rule.to_port)
                    if rule.from_port != -1:
                        rule_xml += "type='%s' " % rule.from_port
                    if rule.to_port != -1:
                        rule_xml += "code='%s' " % rule.to_port

                rule_xml += '/>\n'
            rule_xml += "</rule>\n"
        xml = "<filter name='nova-secgroup-%s' " % security_group_id
        if(FLAGS.use_ipv6):
            xml += "chain='root'>%s</filter>" % rule_xml
        else:
            xml += "chain='ipv4'>%s</filter>" % rule_xml
        return xml

    def _instance_filter_name(self, instance):
        return 'nova-instance-%s' % instance['name']


class IptablesFirewallDriver(FirewallDriver):
    def __init__(self, execute=None, **kwargs):
        from nova.network import linux_net
        self.iptables = linux_net.iptables_manager
        self.instances = {}
        self.nwfilter = NWFilterFirewall(kwargs['get_connection'])

        self.iptables.ipv4['filter'].add_chain('sg-fallback')
        self.iptables.ipv4['filter'].add_rule('sg-fallback', '-j DROP')
        self.iptables.ipv6['filter'].add_chain('sg-fallback')
        self.iptables.ipv6['filter'].add_rule('sg-fallback', '-j DROP')

    def setup_basic_filtering(self, instance):
        """Use NWFilter from libvirt for this."""
        return self.nwfilter.setup_basic_filtering(instance)

    def apply_instance_filter(self, instance):
        """No-op. Everything is done in prepare_instance_filter"""
        pass

    def unfilter_instance(self, instance):
        if self.instances.pop(instance['id'], None):
            self.remove_filters_for_instance(instance)
            self.iptables.apply()
        else:
            LOG.info(_('Attempted to unfilter instance %s which is not '
                     'filtered'), instance['id'])

    def prepare_instance_filter(self, instance):
        self.instances[instance['id']] = instance
        self.add_filters_for_instance(instance)
        self.iptables.apply()

    def add_filters_for_instance(self, instance):
        chain_name = self._instance_chain_name(instance)

        self.iptables.ipv4['filter'].add_chain(chain_name)
        ipv4_address = self._ip_for_instance(instance)
        self.iptables.ipv4['filter'].add_rule('local',
                                              '-d %s -j $%s' %
                                              (ipv4_address, chain_name))

        if FLAGS.use_ipv6:
            self.iptables.ipv6['filter'].add_chain(chain_name)
            ipv6_address = self._ip_for_instance_v6(instance)
            self.iptables.ipv6['filter'].add_rule('local',
                                                  '-d %s -j $%s' %
                                                  (ipv6_address,
                                                   chain_name))

        ipv4_rules, ipv6_rules = self.instance_rules(instance)

        for rule in ipv4_rules:
            self.iptables.ipv4['filter'].add_rule(chain_name, rule)

        if FLAGS.use_ipv6:
            for rule in ipv6_rules:
                self.iptables.ipv6['filter'].add_rule(chain_name, rule)

    def remove_filters_for_instance(self, instance):
        chain_name = self._instance_chain_name(instance)

        self.iptables.ipv4['filter'].remove_chain(chain_name)
        if FLAGS.use_ipv6:
            self.iptables.ipv6['filter'].remove_chain(chain_name)

    def instance_rules(self, instance):
        ctxt = context.get_admin_context()

        ipv4_rules = []
        ipv6_rules = []

        # Always drop invalid packets
        ipv4_rules += ['-m state --state ' 'INVALID -j DROP']
        ipv6_rules += ['-m state --state ' 'INVALID -j DROP']

        # Allow established connections
        ipv4_rules += ['-m state --state ESTABLISHED,RELATED -j ACCEPT']
        ipv6_rules += ['-m state --state ESTABLISHED,RELATED -j ACCEPT']

        dhcp_server = self._dhcp_server_for_instance(instance)
        ipv4_rules += ['-s %s -p udp --sport 67 --dport 68 '
                       '-j ACCEPT' % (dhcp_server,)]

        #Allow project network traffic
        if FLAGS.allow_project_net_traffic:
            cidr = self._project_cidr_for_instance(instance)
            ipv4_rules += ['-s %s -j ACCEPT' % (cidr,)]

        # We wrap these in FLAGS.use_ipv6 because they might cause
        # a DB lookup. The other ones are just list operations, so
        # they're not worth the clutter.
        if FLAGS.use_ipv6:
            # Allow RA responses
            gateway_v6 = self._gateway_v6_for_instance(instance)
            if gateway_v6:
                ipv6_rules += ['-s %s/128 -p icmpv6 -j ACCEPT' % (gateway_v6,)]

            #Allow project network traffic
            if FLAGS.allow_project_net_traffic:
                cidrv6 = self._project_cidrv6_for_instance(instance)
                ipv6_rules += ['-s %s -j ACCEPT' % (cidrv6,)]

        security_groups = db.security_group_get_by_instance(ctxt,
                                                            instance['id'])

        # then, security group chains and rules
        for security_group in security_groups:
            rules = db.security_group_rule_get_by_security_group(ctxt,
                                                          security_group['id'])

            for rule in rules:
                logging.info('%r', rule)

                if not rule.cidr:
                    # Eventually, a mechanism to grant access for security
                    # groups will turn up here. It'll use ipsets.
                    continue

                version = _get_ip_version(rule.cidr)
                if version == 4:
                    rules = ipv4_rules
                else:
                    rules = ipv6_rules

                protocol = rule.protocol
                if version == 6 and rule.protocol == 'icmp':
                    protocol = 'icmpv6'

                args = ['-p', protocol, '-s', rule.cidr]

                if rule.protocol in ['udp', 'tcp']:
                    if rule.from_port == rule.to_port:
                        args += ['--dport', '%s' % (rule.from_port,)]
                    else:
                        args += ['-m', 'multiport',
                                 '--dports', '%s:%s' % (rule.from_port,
                                                        rule.to_port)]
                elif rule.protocol == 'icmp':
                    icmp_type = rule.from_port
                    icmp_code = rule.to_port

                    if icmp_type == -1:
                        icmp_type_arg = None
                    else:
                        icmp_type_arg = '%s' % icmp_type
                        if not icmp_code == -1:
                            icmp_type_arg += '/%s' % icmp_code

                    if icmp_type_arg:
                        if version == 4:
                            args += ['-m', 'icmp', '--icmp-type',
                                     icmp_type_arg]
                        elif version == 6:
                            args += ['-m', 'icmp6', '--icmpv6-type',
                                     icmp_type_arg]

                args += ['-j ACCEPT']
                rules += [' '.join(args)]

        ipv4_rules += ['-j $sg-fallback']
        ipv6_rules += ['-j $sg-fallback']

        return ipv4_rules, ipv6_rules

    def refresh_security_group_members(self, security_group):
        pass

    def refresh_security_group_rules(self, security_group):
        # We use the semaphore to make sure noone applies the rule set
        # after we've yanked the existing rules but before we've put in
        # the new ones.
        with self.iptables.semaphore:
            for instance in self.instances.values():
                self.remove_filters_for_instance(instance)
                self.add_filters_for_instance(instance)
        self.iptables.apply()

    def _security_group_chain_name(self, security_group_id):
        return 'nova-sg-%s' % (security_group_id,)

    def _instance_chain_name(self, instance):
        return 'inst-%s' % (instance['id'],)

    def _ip_for_instance(self, instance):
        return db.instance_get_fixed_address(context.get_admin_context(),
                                             instance['id'])

    def _ip_for_instance_v6(self, instance):
        return db.instance_get_fixed_address_v6(context.get_admin_context(),
                                             instance['id'])

    def _dhcp_server_for_instance(self, instance):
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        return network['gateway']

    def _gateway_v6_for_instance(self, instance):
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        return network['gateway_v6']

    def _project_cidr_for_instance(self, instance):
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        return network['cidr']

    def _project_cidrv6_for_instance(self, instance):
        network = db.network_get_by_instance(context.get_admin_context(),
                                             instance['id'])
        return network['cidr_v6']


#MK
tilera_boards = _tilera_board()
fake_doms = _fake_dom()
#_MK
