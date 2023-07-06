#!/usr/bin/env python3

# clone-vdi.py 
#
# Purpose: clones existing VM and starts it.                        
# 
# Usage: python3 clone-vdi.py
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
    host = "169.254.169.254"
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
    print("Clone-VDI.py -- A Script by Nelson O. for locally cloning on VMs on the HC3 Scale System.")
    VDIname = input("Please enter the name for this new VDI!: ")
    VDIdesc = input("Please enter the name for WHO this VDI will be assigned to: ")
    print("         # Departments!         ")
    print("________________________________")
    print("- dept 1")
    print("- dept 2")
    print("- dept 3")
    print("- dept 4")
    print("- dept 5")
    print("________________________________")
    vtags = input("Please enter the department the user is apart of: ")
    
    
    vmUUID = "UUID-GOES-HERE" #W11P-GoldenImage
   #vmUUID = "UUID-GOES-HERE" #W10GoldenImage
    

    print(">> Cloning "+ str(vmUUID)+" ...")
    vm_clone_attrs = {
        'template': {
            'name': VDIname,
            'description': 'Assigned to: '+str(VDIdesc),
            'operatingSystem': 'os_windows_server_2012',
            'netDevs': [{
                'type': 'VIRTIO',
                'vlan': 1 #VLAN 1 for physical work stations , 2 for VDI
            }],
            'machineType': 'scale-uefi-tpm-9.2',
            'cpuType': 'HC1150-9.2',
            'tags': ",".join(['VDI', vtags])
        }
    }
    connection.request('POST', '{0}/VirDomain/{1}/clone'.format(
        url, vmUUID), json.dumps(vm_clone_attrs), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])
    cloneUUID = result['createdUUID']
    
    print(">>> Successfully Cloned "+ str(vmUUID) +" to "+str(VDIname))
    print(">> Starting "+str(VDIname)+"...")
    start_vm = [{
        'actionType': 'START',
        'virDomainUUID': cloneUUID
    }]
    connection.request(
        'POST', '{0}/VirDomain/action'.format(url), json.dumps(start_vm), rest_opts)
    result = get_response(connection)
    wait_for_task_completion(connection, result['taskTag'])

    print("VDI Name:  "+str(VDIname))
    print("vm UUID:   "+str(cloneUUID))
    print("vmUUID is used for various API requests.")

    return 0

if __name__ == '__main__':
    exit(main())
