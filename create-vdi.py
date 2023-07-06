#!/usr/bin/env python3

# create-vdi.py 
#
# Purpose: Demonstrate basic PXE Booting VM Creation using the Scale Computing REST API
#
# Usage: python3 create-vdi.py
#

import base64
import getpass
import http.client as http
import json
import ssl


class InternalException(Exception):
    pass


class TaskException(InternalException):
    def __init__(self, tag, message, parameters):
        self.tag = tag
        self.message = message
        self.parameters = parameters

    def __str__(self):
        return '%s "%s" %s' % (self.tag, self.message, self.parameters)


class HTTPResponseException(InternalException):
    def __init__(self, response):
        self.response = response
        self.body = response.read()

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self.response.status) + ": " + str(self.body)


def get_host():
    host = "169.254.254.254"
    if not host:
        print('Failed to get host or IP')
        exit(2)
    return host


def get_credentials():
    username = "admin0"
    if not username:
        print('Failed to get username')
        exit(2)
    password = getpass.getpass("Password: ")
    if not password:
        print('Failed to get password')
        exit(2)
    return str(base64.b64encode(bytes('{0}:{1}'.format(username, password), 'utf-8')), 'utf-8')


def get_connection(host):
    timeout = 120
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.verify_mode = ssl.CERT_NONE

    return http.HTTPSConnection(host, timeout=timeout, context=context)


def get_response(connection):
    response = connection.getresponse()
    if response.status != http.OK:
        raise HTTPResponseException(response)

    return json.loads(response.read().decode("utf-8"))


def wait_for_task_completion(connection, task_id):
    inprogress = True
    while inprogress:
        connection.request(
            'GET', '{0}/{1}'.format(url, 'TaskTag/{0}'.format(task_id)), None, rest_opts)
        task_status = get_response(connection)[0]
        if task_status['state'] == 'ERROR':
            raise TaskException(
                task_id, task_status['formattedMessage'], task_status['messageParameters'])
        if task_status['state'] == 'COMPLETE':
            inprogress = False


host = get_host()
url = 'https://{0}/rest/v1'.format(host)
credentials = 'Basic {0}'.format(get_credentials())
rest_opts = {
    'Content-Type': 'application/json',
    'Authorization': credentials,
    'Connection': 'keep-alive'
}


def main():
    connection = get_connection(host)
    print("Create-VDI.py -- A Script by Nelson O.")
    VDIname = input("Please enter the name for this new VDI!: ")
    VDIdesc = input("Please enter the name for WHO this VDI will be assigned to: ")
    print("         # Departments!         ")
    print("________________________________")
    print("- Accounting (ACCT)")
    print("- Administration (ADMIN)")
    print("- FSR (FSR)")
    print("- Information Technology (IT)")
    print("- Teller / Call Center (MPTCC)")
    print("________________________________")

    vtags = input("Please enter the department the user is apart of: ")
    #VDIip = input("Please enter the IP that will be given to the VDI! : ")
    default_vm = {
        'dom': {
            'name': VDIname,
            'description': 'Assigned to: '+str(VDIdesc),
            'operatingSystem': 'os_windows_server_2012',
            'mem': 8589934592,  # 8GiB
            'numVCPU': 2,
            'blockDevs': [{
                'capacity': 107374182400,  # 100GB
                'type': 'VIRTIO_DISK',
                'cacheMode': 'WRITETHROUGH'
            }],
            'netDevs': [{
                'type': 'VIRTIO',
                'vlan': 1 #VLAN 1 for physical work stations , 2 for VDI
            }],
            'machineType': 'scale-uefi-tpm-9.2',
            'cpuType': 'HC1150-9.2'
        },
        'options': {
            #   attachGuestToolsISO == true
            #  attachclientbootISO = true
        }
    }

    print(">> Create '"+str(VDIname)+"' VM..")
    connection.request(
        'POST', '{0}/VirDomain'.format(url), json.dumps(default_vm), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])
    vmUUID = result['createdUUID']

    print("| Attaching clientboot iso for '"+str(VDIname)+"'..")
    block_device_attrs = {
        'virDomainUUID': vmUUID,
        'capacity': 57671680,
        #'path': "scribe/UUID-HERE",  #clientboot.iso
        'path': "scribe/UUID-HERE", #pxe1.iso
        'slot': -1,
        'type': 'IDE_CDROM',
        'cacheMode': 'WRITETHROUGH'
    }
    connection.request('POST', '{0}/VirDomainBlockDevice'.format(url), json.dumps(
        block_device_attrs), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])

    print(">> Start '"+ str(VDIname) + "' VM..")
    start_vm = [{
        'actionType': 'START',
        'virDomainUUID': vmUUID
    }]
    connection.request(
        'POST', '{0}/VirDomain/action'.format(url), json.dumps(start_vm), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])

    # Create a list of cluster nodes without the one the VM is running on
    connection.request('GET', '{0}/Node'.format(url), None, rest_opts)
    nodes = get_response(connection)
    if len(nodes) > 1:
        print(">> Live migrate VM '"+str(VDIname)+"' to another node (load balance)")
        # Get VM Info to determine which node the VM is currently running on
        connection.request(
            'GET', '{0}/VirDomain/{1}'.format(url, vmUUID), None, rest_opts)
        result = get_response(connection)
        vm = result[0]

        nodeUUIDs = [node['uuid']
                     for node in nodes if node['uuid'] != vm['nodeUUID']]
        migrate_vm_to_node = [{
            'actionType': 'LIVEMIGRATE',
            'nodeUUID': nodeUUIDs[0],  # just use the first node in the list
            'virDomainUUID': vmUUID
        }]
        connection.request('POST', '{0}/VirDomain/action'.format(url), json.dumps(
            migrate_vm_to_node), rest_opts)
        result = get_response(connection)
        wait_for_task_completion(connection, result['taskTag'])

    print(">> Stop VM '"+str(VDIname)+"'..")
    stop_vm = [{
        'actionType': 'STOP',
        'virDomainUUID': vmUUID
    }]
    connection.request(
        'POST', '{0}/VirDomain/action'.format(url), json.dumps(stop_vm), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])

    print(">> Update VM '"+str(VDIname)+"' properties")
    edit_vm_attrs = {
        'name': default_vm['dom']['name'],
        'numVCPU': 4,
        'tags': ",".join(['VDI', vtags])
    }
    connection.request(
        'PATCH', '{0}/VirDomain/{1}'.format(url, vmUUID), json.dumps(edit_vm_attrs), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])

    print(">> Starting '"+ str(VDIname) + "' VM again..")
    start_vm = [{
        'actionType': 'START',
        'virDomainUUID': vmUUID
    }]
    connection.request(
        'POST', '{0}/VirDomain/action'.format(url), json.dumps(start_vm), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])


    print("VDI Name:  "+str(VDIname))
    print("vm UUID:   "+str(vmUUID))
    print("vmUUID is used for various API requests.")

    return 0

if __name__ == '__main__':
    exit(main())
