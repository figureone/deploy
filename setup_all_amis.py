#!/usr/bin/env python3
#
# This script will start up a bunch of AMIs in different regions, download the learning locker build script on to each one, run it and create an AMI with the given name
#
# USAGE:
#    python setup_all_amis.py -r REGION_LIST -n NAME -d DESCRIPTION -k AWS_KEY -s AWS_SECRET -a AWS_ACCOUNT_ID
#    python setup_all_amis.py -r us-west-1,us-east-1,eu-west-1 -n "ll v2 2.0.3" -d "Learning Locker 2.0.3 from HT2 Labs" -k abc -s bcd/hyt -a 000836383
#    python setup_all_amis.py -c 1 -n "Learning Locker 2.0.5-1 from HT2 Labs" -d "Learning Locker 2.0.5 from HT2 Labs"
#
# ENVVARS
#    export AWS_AUTH_SECRET=
#    export AWS_AUTH_KEY=
#    export AWS_ACCOUNT_ID=007712106137
#
# TODO
#   Make sure we can read the keyfiles - if we can't, we shouldn't even spin up a server
#   run boto3 check on aws credentials as it uses ~/.aws/credentials
#   validate key / sg exists
#   move validate_region() data to a file
#
# REQUIREMENTS
# apt-get install awscli
# set up AWS tools - http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html
# pip install paramiko
# pip install argparse
# pip install boto3

import os
import sys
import time
import argparse
import paramiko
import boto3
from botocore.exceptions import ClientError
from multiprocessing import Process


# List of AWS supported regions
# us-east-1         : N. Virginia
# us-east-2         : Ohio
# us-west-1         : N. California
# us-west-2         : Oregon
# ca-central-1      : Canada Central
# eu-west-1         : Ireland
# eu-central-1      : Frankfurt
# eu-west-2         : London
# ap-southeast-1    : Singapore
# ap-southeast-2    : Sydney
# ap-northeast-2    : Seoul
# ap-northeast-1    : Tokyo
# ap-south-1        : Mumbai
# sa-east-1         : Sao Paulo
#
# Supported Ubuntu distros: 16.04, 17.04

################################################################
# FUNCTIONS
################################################################
def get_region_list ():
    list = [
                'us-east-1',
                'us-east-2',
                'us-west-1',
                'us-west-2',
                'ca-central-1',
                'eu-west-1',
                'eu-central-1',
                'eu-west-2',
                'ap-southeast-1',
                'ap-southeast-2',
                'ap-northeast-2',
                'ap-northeast-1',
                'ap-south-1',
                'sa-east-1'
            ]
    return list


def validate_region (region, distro_version):
    # ami ids
    ami_id = False
    if distro_version == "16.04":       # 16.04
        if region == "us-east-1":           # us-east-1
            ami_id = "ami-d651b8ac"
        elif region == "us-east-2":         # us-east-2
            ami_id = "ami-9686a4f3"
        elif region == "us-west-1":         # us-west-1
            ami_id = "ami-2d5c6d4d"
        elif region == "us-west-2":         # us-west-2
            ami_id = "ami-ecc63a94"
        elif region == "ca-central-1":      # ca-central
            ami_id = "ami-e59c2581"
        elif region == "eu-west-1":         # Ireland
            ami_id = "ami-17d11e6e"
        elif region == "eu-central-1":      # Frankfurt
            ami_id = "ami-5a922335"
        elif region == "eu-west-2":         # London
            ami_id = "ami-e1f2e185"
        elif region == "ap-southeast-1":    # Singapore
            ami_id = "ami-e6d3a585"
        elif region == "ap-southeast-2":    # Sydney
            ami_id = "ami-391ff95b"
        elif region == "ap-northeast-2":    # Seoul
            ami_id = "ami-0f6fb461"
        elif region == "ap-northeast-1":    # Tokyo
            ami_id = "ami-8422ebe2"
        elif region == "ap-south-1":        # Mumbai
            ami_id = "ami-08a5e367"
        elif region == "sa-east-1":         # Sao Paulo
            ami_id = "ami-a3e39ecf"
    elif distro_version == "17.04":     # 17.04
        if region == "us-east-1":           # us-east-1
            ami_id = "ami-29976653"
        elif region == "us-east-2":         # us-east-2
            ami_id = "ami-44496421"
        elif region == "us-west-1":         # us-west-1
            ami_id = "ami-67aa9b07"
        elif region == "us-west-2":         # us-west-2
            ami_id = "ami-70728c08"
        elif region == "ca-central-1":      # ca-central
            ami_id = "ami-e370c987"
        elif region == "eu-west-1":         # Ireland
            ami_id = "ami-5cc00825"
        elif region == "eu-central-1":      # Frankfurt
            ami_id = "ami-425ded2d"
        elif region == "eu-west-2":         # London
            ami_id = "ami-e2bba886"
        elif region == "ap-southeast-1":    # Singapore
            ami_id = "ami-947d0ef7"
        elif region == "ap-southeast-2":    # Sydney
            ami_id = "ami-8505e4e7"
        elif region == "ap-northeast-2":    # Seoul
            ami_id = "ami-e2a9738c"
        elif region == "ap-northeast-1":    # Tokyo
            ami_id = "ami-894983ef"
        elif region == "ap-south-1":        # Mumbai
            ami_id = "ami-b42869db"
        elif region == "sa-east-1":         # Sao Paulo
            ami_id = "ami-724f331e"

    if ami_id == False:
        print("FATAL: couldn't find ami_id for ubuntu " + distro_version + " in " + region + " - maybe this script needs updating with new starting AMIs")
        sys.exit()

    # security group and keypair - tried to create the same everywhere but feel free to override if needed
    secgroup = "ll-build"       # default SG
    kp = "llbuild-" + region    # default KP name

    # output
    print("region: " + region + "; ami_id: " + ami_id + "; SG: " + secgroup + "; KP: " + kp)
    return {"kp":kp, "sg": secgroup, "ami_id": ami_id, "region": region}


def run_on_server (hostname, region, port, username, keyfile, name, desc, enterprise_mode):
    global account_id
    global aws_key
    global aws_secret

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        #client.connect(hostname, port=port, username=username, password=password)
        client.connect(hostname, port=port, username=username, password="", pkey=None, key_filename=keyfile)

        print(hostname + " Connected to " + hostname + " in " + region)

        print(hostname + " running apt-get update")
        stdin, stdout, stderr = client.exec_command("sudo apt-get -y -q update")
        chk = stdout.read()

        print(hostname + " running dist-upgrade")
        stdin, stdout, stderr = client.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get --allow-downgrades --allow-remove-essential --allow-change-held-packages -o Dpkg::Options::='--force-confnew' -fuyq dist-upgrade")
        chk = stdout.read()

        print(hostname + " installing curl & wget")
        stdin, stdout, stderr = client.exec_command("sudo apt-get -qq -y install curl wget")
        chk = stdout.read()

        print(hostname + " getting & running deploy script")
        estr = ""
        if enterprise_mode == True:
            estr = " -e 1"
        stdin, stdout, stderr = client.exec_command("curl -o- -L http://lrnloc.kr/installv2 > deployll.sh && sudo bash deployll.sh -y 5" + estr)
        chk = stdout.read()

        print(hostname + " running AMI build script")
        #print(hostname + "sudo /tmp/deploy/create_ami.sh -y 1 -n '" + name + "' -d '" + desc + "' -a " + repr(account_id) + " -k " + aws_key + " -s " + aws_secret + " -v public -t ebs -r " + region)
        stdin, stdout, stderr = client.exec_command("sudo /tmp/deploy/create_ami.sh -y 1 -n '" + name + "' -d '" + desc + "' -a " + repr(account_id) + " -k " + aws_key + " -s " + aws_secret + " -v public -t ebs -r " + region)
        chk = stdout.read()

        print(hostname + " Finished!")

    finally:
        client.close()



################################################################
# DEFAULT VARS
################################################################
account_id = False
ami_name = False
ami_desc = False
ami_visibility = "public"
ami_datasets = []
aws_key = False
aws_secret = False
aws_regions = False
distro_version = "16.04"
build_name = "ll_py_build"
instance_size = "t2.small"
keyfile_path = "/etc/ht2keys/"
enterprise_mode = False


################################################################
# READ CLI VARS
################################################################
parser = argparse.ArgumentParser()
parser.add_argument("-r", "--regions",                  help="Region (or comma separated list of regions) to start instances in")
parser.add_argument("-n", "--name",                     help="Name of the AMI")
parser.add_argument("-d", "--description",              help="Decription for the AMI")
parser.add_argument("-k", "--key",                      help="AWS Access key")
parser.add_argument("-s", "--secret",                   help="AWS Access Secret")
parser.add_argument("-a", "--account",      type=int,   help="AWS Account ID")
parser.add_argument("-v", "--visibility",               help="visibility (public or private)")
parser.add_argument("-p", "--keypath",                  help="Path to the AWS keys")
parser.add_argument("-c", "--complete",                 help="complete region list")
parser.add_argument("-e", "--enterprise",               help="enterprise mode (set to 1 to enable)")
args = parser.parse_args()

# validate vars

# name
if not args.name or len(args.name) < 4:
    print("FATAL: no name for the AMI passed in")
    sys.exit()
ami_name = args.name

# description
if not args.description or len(args.description) < 4:
    print("FATAL: no description for the AMI passed in")
    sys.exit()
ami_desc = args.description

# visibility
if args.visibility and args.visibility == "private":
    ami_visibility = "private"

# path to the AWS keys
if args.keypath and len(args.keypath) > 4:
    keyfile_path = args.keypath

# account id
if not args.account:
    if os.environ['AWS_ACCOUNT_ID']:
        env = os.environ['AWS_ACCOUNT_ID']
        if int(env):
            account_id = env
    else:
        print("FATAL: no account id passed or in environment variable 'AWS_ACCOUNT_ID'")
        sys.exit()
else:
    account_id = args.account

# path to the keys
if os.environ['AWS_KEYFILES_PATH']:
    keyfile_path = os.environ['AWS_KEYFILES_PATH']

# enterprise
if args.enterprise == 1:
    enterprise_mode = True

# key
if not args.key or len(args.key) < 10:
    if 'AWS_AUTH_KEY' in os.environ and len(os.environ['AWS_AUTH_KEY']) > 10:
        aws_key = os.environ['AWS_AUTH_KEY']
    else:
        print("FATAL: No AWS auth key passed in or in environment variable 'AWS_AUTH_KEY'")
        sys.exit()
else:
    aws_key = args.key

# secret
if not args.secret or len(args.secret) < 10:
    if 'AWS_AUTH_SECRET' in os.environ and len(os.environ['AWS_AUTH_SECRET']) > 10:
        aws_secret = os.environ['AWS_AUTH_SECRET']
    else:
        print("FATAL: No AWS auth secret passed in or in environment variable 'AWS_AUTH_SECRET'")
        sys.exit()
else:
    aws_secret = args.secret


# regions

# 'all'
aws_regions = False
if args.complete:
    aws_regions = get_region_list()
elif not args.regions or len(args.regions) < 5:
    print("FATAL: no regions passed in")
    sys.exit()
else:
    aws_regions = args.regions.split(",")

if aws_regions:
    for region in aws_regions:
        ami_datasets.append(validate_region(region, distro_version))


print("AMI Name            : " + ami_name)
print("AMI Description     : " + ami_desc)
print("AMI visbility       : " + ami_visibility)
print("AMI temp build name : " + build_name)
print("AWS Account ID      : " + repr(account_id))
print("AWS x509 Key        : " + aws_key)
print("AWS x509 Secret     : " + aws_secret)
print("AWS regions         : " + repr(aws_regions))
print("Enterprise mode     : " + repr(enterprise_mode))
#print("AWS ami ids         : " + repr(ami_ids))
print("Warning - the security groups and keypairs must be set up in advance in validate_regions() or things WILL break")

while True:
    chk = input("Press enter to continue ")
    if str(chk) == "":
        break


################################################################
# SPIN UP AMIs
################################################################

ec2 = boto3.client("ec2", region_name=region)

# check keypair & security groups exist in every region we want to launch in
#print("Checking keypair and security group data")
### TODO

# start instances
print("[*] Starting servers")
instance_datasets = {}
i = 0
for ami_data in ami_datasets:
    ami_id = ami_data['ami_id']
    region = ami_data['region']

    res = boto3.resource('ec2', region_name=region)

    # start the instance
    print("ImageId=" + ami_id + ", MinCount=1, MaxCount=1, InstanceType=instance_size, SecurityGroups=[" + ami_data['sg'] + "], KeyName=" + ami_data['kp'])
    instance = res.create_instances(ImageId=ami_id, MinCount=1, MaxCount=1, InstanceType=instance_size, SecurityGroups=[ami_data['sg']], KeyName=ami_data['kp'])
    print("....Initiated instance id: " + instance[0].id + " in " + region + " with name: " + build_name)

    instance_datasets[instance[0].id] = {"region":region, "instance_id": instance[0].id, "kp": ami_data['kp']}

    # set the name tag
    instance[0].create_tags(Tags=[{'Key': 'Name', 'Value': build_name}])

    i += 1
print("[*] initited all servers, waiting for them to start")


################################################################
# servers can take a while to start so we go into a loop waiting for them to start
################################################################
startedInstances = {}
public_ips = {}
c = 0
while True:
    c += 1
    i = 0
    for iid, instance_data in instance_datasets.items():

        # get the list of boxes that are running and called whatever the build nam
        session = boto3.Session(region_name=instance_data['region'])
        sec2 = session.resource('ec2', instance_data['region'])
        instances = sec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']},{'Name':'tag:Name', 'Values':[build_name]}])

        # check if we found it
        found = False
        for instance in instances:
            found = True

        if found == False:
            print("....Waiting for server " + repr(instance_data['instance_id']) + " in " + repr(instance_data['region']) + " to start....")
        elif instance_data['instance_id'] not in startedInstances:
            # get public IP now it's started
            ec2 = boto3.client('ec2', region_name=instance_data['region'])
            response = ec2.describe_instances(InstanceIds=[iid])
            public_ip = response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Association']['PublicDnsName']
            if not public_ip or len(public_ip) < 7:
                print("[*] FATAL - instance " + instance_data['instance_id'] + " in region '" + instance_data['region'] + "' doesn't have a public ip - can't continue")
                sys.exit()

            print("[*] Started instance " + instance_data['instance_id'])
            public_ips[instance_data['instance_id']] = public_ip
            startedInstances[instance_data['instance_id']] = instance_data
        i += 1

    # if we have the same number of running instances as we should have - exit the loop
    if len(startedInstances) >= len(instance_datasets):
        break

    # we don't want to itterate forever so bail out if this has taken too long
    if c > 30:
        print("[*] Servers seem to be taking too long to start, exiting")
        sys.exit()

    # wait for 10s before retrying
    time.sleep(10)
print("[*] All servers alive")

# sleep for 2 mins - this is just to make damn sure everything is working. AWS is a bit weird
sleeptime = 60
print("[*] Sleeping for " + repr(sleeptime) + " seconds to make sure the servers are running and not mis-reporting")
time.sleep(sleeptime)


################################################################
# multithreading :: run install & AMI process on each server
################################################################
print("[*] Going into threading mode for running commands on servers")
ec2 = boto3.resource('ec2')
threads = []
if __name__ == '__main__':
    for iid, instance_data in instance_datasets.items():
        # get the hostname
        hostname = public_ips[instance_data['instance_id']]

        # get keyfile
        ssh_keyfile = keyfile_path + instance_data['kp'] + ".pem"

        p = Process(target=run_on_server, args=(hostname, instance_data['region'], 22, 'ubuntu', ssh_keyfile, ami_name, ami_desc, enterprise_mode))
        p.start()
        threads.append(p)


################################################################
# Terminate servers
################################################################
if __name__ == '__main__':
    for p in threads:
        p.join()

    for iid, instance_data in instance_datasets.items():
        print("[*] terminating instance " + instance_data['instance_id'] + " in " + instance_data['region'])

        session = boto3.Session(region_name=instance_data['region'])
        ec2 = session.resource('ec2', instance_data['region'])
        instances = ec2.instances.filter(InstanceIds=[instance_data['instance_id']]).terminate()

    # finish
    print("[*] All Done!")