#!/usr/bin/env python
# -*- coding: utf-8 -*-

# v0.1 - 2015-11-16
# v1.0 - 2015-11-20
# Author: Anthony Cheng
# Python 2.7.8
# boto 2.38.0

# ********** Configuration Constant **********
#BOOLEAN_DRYRUN           = True
BOOLEAN_DRYRUN           = False
PROJECT_TAG              = "Stratus"
ACCESS_KEY               = ""
SECRET_KEY               = ""
REGION_NAME              = "us-east-1"
AVAIL_ZONE1              = REGION_NAME + 'b'
AVAIL_ZONE2              = REGION_NAME + 'c'
AMI_IMAGE                = "ami-60b6c60a"     #Amazon Linux AMI 2015.09.1 (HVM), SSD; us-east
VPC_CIDR                 = "10.0.2.0/24"
VPC_NAME                 = "New VPC"
VPC_SUBNET1              = "10.0.2.0/25"
VPC_SUBNET2              = "10.0.2.128/25"
VPC_TENANCY              = "default"
INSTANCE_SIZE            = "t2.micro"

DEFAULT_USER             = "ec2-user"
SG_PREFIX                = "Security Tag - Stratus"
KEY_DIR                  = "/home/"
KEY_NAME                 = "StratusKeypair.pem"
# ********************

'''
# ********** User interactive **********
print "Type CIDR block to use between /16 and /28.  E.G. 10.0.0.0/24, Press 'Enter' when finished"
VPC_CIDR = raw_input()

print "Type the Name for VPC (to use as Tag), Press 'Enter' when finished"
VPC_NAME = raw_input()
'''

import boto
import boto.rds2
import os, subprocess, time

from boto.manage.cmdshell import sshclient_from_instance
from boto.vpc import VPCConnection
vpcc = VPCConnection()

#boto.set_stream_logger("Stratus")
print "Boto Version: ", boto.Version, "\n"
# print boto.rds2.regions()

exist_vpc = vpcc.get_all_vpcs(filters = [("cidrBlock", VPC_CIDR)])

if not len(exist_vpc):
    new_vpc = vpcc.create_vpc(cidr_block = VPC_CIDR, instance_tenancy = VPC_TENANCY,
    dry_run = BOOLEAN_DRYRUN)
    aws_vpc_id = new_vpc.id
    print "No existing VPC"
    print "New VPC created: ", aws_vpc_id, "\n"
else:
    # Return 1st object from list
    aws_vpc_id = str(exist_vpc.pop(0))[4:]
    print "Identical CIDR already used. Skipped creation."
    print "Existing VPC ID: {}\n".format(aws_vpc_id)
    # Use existing VPC
    new_vpc = vpcc.get_all_vpcs(filters = [("cidrBlock", VPC_CIDR)])
'''
   # Doesn't work due to VPC dependency
    print "Requested VPC already exists! Will attempt to delete vpc and recreate"
    del_status = vpcc.delete_vpc(aws_vpc_id)
    print "Deletion Completed", del_status
'''

exist_subnet1 = vpcc.get_all_subnets(filters = [("cidrBlock", VPC_SUBNET1)])
exist_subnet2 = vpcc.get_all_subnets(filters = [("cidrBlock", VPC_SUBNET2)])

if not len(exist_subnet1):
    print "Creating new subnet ..."
    new_subnet1 = vpcc.create_subnet(aws_vpc_id, VPC_SUBNET1,AVAIL_ZONE1, dry_run = BOOLEAN_DRYRUN)
    subnet1_id = new_subnet1.id
    print "New subnet 1 ID: {}\n".format(subnet1_id)
else:
    print "Subnet with {} already exists.  Skipped creation".format(VPC_SUBNET1)
    subnet1_id = str(exist_subnet1.pop(0))[7:]
    print "Existing subnet 1 ID: {}\n".format(subnet1_id)

if not len(exist_subnet2):
    print "Creating new subnet2 ..."
    new_subnet2 = vpcc.create_subnet(aws_vpc_id, VPC_SUBNET2,AVAIL_ZONE2, dry_run = BOOLEAN_DRYRUN)
    subnet2_id = new_subnet2.id
    print "New subnet 2 ID: {}\n".format(subnet2_id)
else:
    print "Subnet with {} already exists.  Skipped creation".format(VPC_SUBNET2)
    subnet2_id = str(exist_subnet2.pop(0))[7:]
    print "Existing subnet 2 ID: {}\n".format(subnet2_id)


# ********** Connections **********
def connect():
    ec2_connect = boto.ec2.connect_to_region(REGION_NAME)
    rds_connect = boto.rds2.connect_to_region(REGION_NAME)
    vpc_connect = boto.vpc.connect_to_region(REGION_NAME)

#    ec2_connect = boto.ec2.connect_to_region(REGION_NAME,
#    aws_access_key_id = ACCESS_KEY, aws_secret_access_key = SECRET_KEY)
#    rds_connect = boto.rds2.connect_to_region(REGION_NAME,
#    aws_access_key_id = ACCESS_KEY, aws_secret_access_key = SECRET_KEY)
#    vpc_connect = boto.vpc.connect_to_region(REGION_NAME,
#    aws_access_key_id = ACCESS_KEY, aws_secret_access_key = SECRET_KEY)

    return ec2_connect, rds_connect, vpc_connect

ec2_connect, rds_connect, vpc_connect = connect()
# ********************


# ********** VPC Block **********
print "********** VPC Block **********\n"
#print "VPC Access to Zone:", vpc_connect.get_all_zones()

vpc_connect.modify_vpc_attribute(aws_vpc_id, enable_dns_support = True)
vpc_connect.modify_vpc_attribute(aws_vpc_id, enable_dns_hostnames = True)

# Create Routing Table
new_route_table = vpc_connect.create_route_table(aws_vpc_id, dry_run = BOOLEAN_DRYRUN)

try:
    vpc_connect.associate_route_table(new_route_table.id, subnet1_id)
except Exception as e:
    print "Alert: {}.\n".format(e.message)
else:
    print "Subnet1 is successfully associated with Route Table.\n"

try:
    vpc_connect.associate_route_table(new_route_table.id, subnet2_id)
except Exception as e:
    print "Alert: {}.\n".format(e.message)
else:
    print "Subnet2 is successfully associated with Route Table.\n"

try:
    inet_gateway = vpc_connect.create_internet_gateway(dry_run = BOOLEAN_DRYRUN)
except Exception as e:
    print "GW Create Alert: {}.\n".format(e.message)
else:
    print "New Internet Gateway created: {}\n".format(inet_gateway)

try:
    vpc_connect.attach_internet_gateway(inet_gateway.id, aws_vpc_id)
except Exception as e:
   print "GW Attach Alert: {}.\n".format(e.message)
else:
   print "Attach GW to VPC: Success\n"

# To-do: check for existing IGW to use as ID instead
try:
    inet_gw_route_status = vpc_connect.create_route(new_route_table.id,
    destination_cidr_block = "0.0.0.0/0", gateway_id = inet_gateway.id,
    dry_run = BOOLEAN_DRYRUN)
except Exception as e:
   print "GW Route Alert: {}.\n".format(e.message)
else:
   print "Default Internet Route for Gateway created: Success\n"

exist_sec_group = ec2_connect.get_all_security_groups(filters=[("group-name", SG_PREFIX)])
print "Exist SG: ", exist_sec_group

if not len(exist_sec_group):
    try:
        sec_group = ec2_connect.create_security_group(
        name = SG_PREFIX, description = "Security Group for " + PROJECT_TAG,
        vpc_id = aws_vpc_id, dry_run = BOOLEAN_DRYRUN)
    except Exception as e:
        print "Alert: {}.\n".format(e.message)
    else:
        sec_group_id = sec_group.id
        print "SG ID: ", sec_group_id
        print "Security Group: {} created.\n".format(sec_group)
        sec_group.authorize(ip_protocol = 'tcp', from_port = 22,
        to_port = 22, cidr_ip = "0.0.0.0/0")
        sec_group.authorize(ip_protocol = 'tcp', from_port = 80,
        to_port = 80, cidr_ip = "0.0.0.0/0")
        sec_group.authorize(ip_protocol = 'tcp', from_port = 443,
        to_port = 443, cidr_ip = "0.0.0.0/0")
else:
    # I can't find a way to get Security Group ID so have to delete & recreate; sad face becuase delete doesn't work
    # yet so have to create.  This will result in error later.
    sec_group_name = str(exist_sec_group.pop(0))[14:]
    print "Name to delete: ", sec_group_name
    # To-do: Below does NOT work
    # ec2_connect.delete_security_group(name = sec_group_name)
    # Re-create etc.
# ********************


# ********** SSH KEY Block **********
print "********** SSH KEY Block **********\n"

# Create Key Pair on the account
try:
    new_key_pair = ec2_connect.create_key_pair(PROJECT_TAG+"Keypair", dry_run = BOOLEAN_DRYRUN)
except Exception as e:
    print "Alert: {}.\n".format(e.message)
    new_key_pair_id = PROJECT_TAG + "Keypair"
else:
    print "SSH Keypair: {}  created.\n".format(new_key_pair)
    new_key_pair_id = new_key_pair.name
    # Try to save the new key
    try:
        new_key_pair.save(KEY_DIR)
    except Exception as e:
        print "Alert: {}.\n".format(e.message)
        print "SSH Key is NOT saved!\n"
    else:
        print "SSH Keypair saved in {}\n".format(KEY_DIR)
        cmd = "sudo chmod 400 " + KEY_DIR + KEY_NAME
        os.system(cmd)
# ********************


# ********** EC2 Block **********
# http://www.saltycrane.com/blog/2010/03/how-list-attributes-ec2-instance-python-and-boto/
print "********** EC2 Block **********\n"

try:
    subnet1_interface_Spec = boto.ec2.networkinterface.NetworkInterfaceSpecification(
    subnet_id = subnet1_id, associate_public_ip_address = True)
    # Got some error later; so had to remove this:
    # groups = sec_group_id,
    subnet1_interface = boto.ec2.networkinterface.NetworkInterfaceCollection(subnet1_interface_Spec)
except Exception as e:
    print "\nAlert: {}.\n".format(e.message)
else:
    print "Interface for subnet 1 prepared.\n"

try:
    subnet2_interface_Spec = boto.ec2.networkinterface.NetworkInterfaceSpecification(
    subnet_id = subnet2_id, associate_public_ip_address = True)

    subnet2_interface = boto.ec2.networkinterface.NetworkInterfaceCollection(subnet2_interface_Spec)
except Exception as e:
    print "\nAlert: {}.\n".format(e.message)
else:
    print "Interface for subnet 2 prepared.\n"

ec2_reserve1 = ec2_connect.run_instances (
image_id = AMI_IMAGE, key_name = new_key_pair_id,
instance_type = INSTANCE_SIZE, placement = AVAIL_ZONE1,
network_interfaces = subnet1_interface, dry_run = BOOLEAN_DRYRUN)

ec2_reserve2 = ec2_connect.run_instances (
image_id = AMI_IMAGE, key_name = new_key_pair_id,
instance_type = INSTANCE_SIZE, placement = AVAIL_ZONE2,
network_interfaces = subnet2_interface, dry_run = BOOLEAN_DRYRUN)

# Got this error message:
# Network interfaces and an instance-level subnet ID may not be specified on the same request
# So had to remove this:
# subnet_id = subnet1_id, security_group_ids = [sec_group_id],
# Also no need for subnet info as that's already specified in the subnet interface setting
# Ref. https://github.com/aws/aws-sdk-php/issues/231
# Ref. https://github.com/aws/aws-cli/issues/518
# Ref. http://stackoverflow.com/questions/19029588/how-to-auto-assign-public-ip-to-ec2-instance-with-boto

ec2_instance1 = ec2_reserve1.instances[0]
print "Wait for instance1 to be running:\n"

while ec2_instance1.state != "running":
    print ". ",
    time.sleep(4)
    ec2_instance1.update()
print "Running!\n"

ec2_instance2 = ec2_reserve2.instances[0]
print "Wait for instance2 to be running:\n"

while ec2_instance2.state != "running":
    print ". ",
    time.sleep(4)
    ec2_instance2.update()
print "Running!\n"

ec2_instance1_id = ec2_instance1.id
ec2_instance2_id = ec2_instance2.id
ec2_instance1_dns = ec2_instance1.public_dns_name
ec2_instance2_dns = ec2_instance2.public_dns_name

# https://groups.google.com/forum/#!topic/boto-users/j_CfsT-o19U
ec2_connect.modify_instance_attribute(ec2_instance1_id, "groupSet", [sec_group_id])
ec2_connect.modify_instance_attribute(ec2_instance2_id, "groupSet", [sec_group_id])

bool_connection = False
while bool_connection == False:
    print "Attempt to connect  Instance 1..."
    try:
        ssh_connect = sshclient_from_instance(instance = ec2_instance1,
        ssh_key_file = KEY_DIR + KEY_NAME, user_name = DEFAULT_USER)
    except Exception as e:
        print "Alert: {}.\n".format(e.message)
        print "Waiting for SSH service...",
        time.sleep(5) # Wait for SSH service
    else:
        print "Connection to instance1 is successful\n"
        time.sleep(2)
        ssh_connect.run_pty("sudo sed -i \'s/requiretty/!requiretty/\' /etc/sudoers")
        time.sleep(4)
        print ssh_connect.run("sudo yum update -y; sudo yum groupinstall -y \"Web Server\" \"PHP Support\"; sudo yum install -y php-mysql php-xml php-mbstring php-gd; sudo service httpd start; sudo chkconfig httpd on")
        bool_connection = True
        print "\n\n ********************* Web Server Installation completed *********************\n\n"

bool_connection = False
while bool_connection == False:
    print "Attempt to connect to Instance 2..."
    try:
        ssh_connect = sshclient_from_instance(instance = ec2_instance2,
        ssh_key_file = KEY_DIR + KEY_NAME, user_name = DEFAULT_USER)
    except Exception as e:
        print "Alert: {}.\n".format(e.message)
        print "Waiting for SSH service...",
        time.sleep(5) # Wait for SSH service
    else:
        print "Connection to instance2 is successful\n"
        time.sleep(2)
        ssh_connect.run_pty("sudo sed -i \'s/requiretty/!requiretty/\' /etc/sudoers")
        time.sleep(4)
        print ssh_connect.run("sudo yum update -y; sudo yum groupinstall -y \"Web Server\" \"PHP Support\"; sudo yum install -y php-mysql php-xml php-mbstring php-gd; sudo service httpd start; sudo chkconfig httpd on")
        bool_connection = True
        print "\n\n ********************* Web Server Installation completed *********************\n\n"

# ************************* Web Service  Test ********************************

try:
    print "\n\n *************** Testing Web Service 1: ", ec2_instance1_dns, "\n\n"
    time.sleep(5)
    os.system("curl -m 3 " + ec2_instance1_dns)
except Exception as e:
        print "Alert: {}.\n".format(e.message)
else:
    print "\n\n ****************Web Service 1 testing completed. ****************\n"

try:
    print "\n\n *************** Testing Web Service 2: ", ec2_instance2_dns, "\n\n"
    time.sleep(5)
    os.system("curl -m 3 " + ec2_instance2_dns)
except Exception as e:
        print "Alert: {}.\n".format(e.message)
else:
    print "\n\n ****************Web Service 2 testing completed. ****************\n"
