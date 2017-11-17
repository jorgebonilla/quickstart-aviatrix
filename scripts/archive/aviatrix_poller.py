#copy paste this into lamdba
import os, sys, urllib, ssl, json, logging, boto3
from urllib2 import Request, urlopen, URLError
from time import sleep

#Required for SSL Certificate no-verify
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

#logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Aviatrix:
    def __init__(self,controller_ip):
        self.controller_ip = controller_ip
        self.CID = ""

    def avx_api_call(self,method,action,parameters):
        url = "https://%s/v1/api?action=%s" % (self.controller_ip,action)
        for key,value in parameters.iteritems():
            value = urllib.quote(value, safe='')
            url = url + "&%s=%s" % (key,value)
        self.url = url
        logger.info("Executing API call:%s" % self.url)
        try:
            if method == "POST":
                data = urllib.urlencode(parameters)
                response = urlopen(self.url, data=data, context=ctx)
            else:
                response = urlopen(self.url, context=ctx)
            json_response = response.read()
            logger.info("HTTP Response: %s" % json_response)
            self.result = json.loads(json_response)
            if self.result['return'] == False:
                return {
                    'Status' : 'FAILURE',
                    'Error' : self.result['reason']
                }
        except URLError, e:
            print 'Failed request. Error:', e
            return {
                'Status' : 'FAILURE',
                'Error' : e
            }

    def login(self,username,password):
        self.avx_api_call("GET","login",{ "username": username,
                                          "password": password })
        if self.result['return'] == True:
            self.CID = self.result['CID']

    def admin_email(self,email):
        self.avx_api_call("GET","add_admin_email_addr", { "CID": self.CID,
                                                          "admin_email": email })

    def change_password(self,account,username,old_password,password):
        self.avx_api_call("GET","change_password", { "CID": self.CID,
                                                     "account_name": account,
                                                     "user_name": username,
                                                     "old_password": old_password,
                                                     "password": password })

    def initial_setup(self,subaction):
        self.avx_api_call("POST","initial_setup", { "subaction": subaction, "CID": self.CID })
        sleep(self.result['results'])

    def setup_account_profile(self,account,password,email,cloud_type,aws_account_number,aws_role_arn,aws_role_ec2):
        self.avx_api_call("POST","setup_account_profile", { "CID": self.CID,
                                                            "account_name": account,
                                                            "account_password": password,
                                                            "account_email": email,
                                                            "cloud_type": cloud_type,
                                                            "aws_iam": "true",
                                                            "aws_account_number": aws_account_number,
                                                            "aws_role_arn": aws_role_arn,
                                                            "aws_role_ec2": aws_role_ec2 })

    def setup_customer_id(self,customer_id):
        self.avx_api_call("GET","setup_customer_id", { "CID": self.CID,
                                                       "customer_id": customer_id })

    def create_gateway(self,account,cloud_type,gw_name,vpc_id,vpc_region,vpc_size,vpc_net):
        self.avx_api_call("POST","connect_container", { "CID": self.CID,
                                                        "account_name": account,
                                                        "cloud_type": cloud_type,
                                                        "gw_name": gw_name,
                                                        "vpc_id": vpc_id,
                                                        "vpc_reg": vpc_region,
                                                        "vpc_size": vpc_size,
                                                        "vpc_net": vpc_net })
    def delete_gateway(self,cloud_type,gw_name):
        self.avx_api_call("GET","delete_container", { "CID": self.CID,
                                                      "cloud_type": cloud_type,
                                                      "gw_name": gw_name })
    def peering(self,vpc_name1,vpc_name2):
        self.avx_api_call("GET","peer_vpc_pair", { "CID": self.CID,
                                                   "vpc_name1": vpc_name1,
                                                   "vpc_name2": vpc_name2 })
    def unpeering(self,vpc_name1,vpc_name2):
        self.avx_api_call("GET","unpeer_vpc_pair", { "CID": self.CID,
                                                   "vpc_name1": vpc_name1,
                                                   "vpc_name2": vpc_name2 })


def handler(event,context):
    #Read environment Variables
    controller_ip = os.environ.get("controller_ip")
    username = os.environ.get("username")
    private_ip = os.environ.get("private_ip")
    admin_email = os.environ.get("admin_email")
    password = os.environ.get("password")
    account = os.environ.get("Account")
    AviatrixRoleApp = os.environ.get("AviatrixRoleApp")
    AviatrixRoleEC2 = os.environ.get("AviatrixRoleEC2")
    vpc_hub = os.environ.get("VPC")
    subnet_hub = os.environ.get("Subnet")
    region_hub = os.environ.get("Region")
    gwsize_hub = os.environ.get("GatewaySizeParam")
    first_run = os.environ.get("first_run")
    setup_run = os.environ.get("setup_run")

    #Gather all the regions
    ec2=boto3.client('ec2',region_name='us-east-1')
    regions=ec2.describe_regions()
    for region in regions['Regions']:
        region_id=region['RegionName']
        logger.info('Checking region: %s',region_id)
        ec2=boto3.client('ec2',region_name=region_id)

        #Find VPCs with Tag:aviatrix-spoke = true
        #Create Gateway for it and Peer, when done change the Tag:aviatrix-spoke = peered
        vpcs=ec2.describe_vpcs(Filters=[
            { 'Name': 'state', 'Values': [ 'available' ] },
            { 'Name': 'tag:aviatrix-spoke', 'Values': [ 'true' ] }
        ])
        for vpc_peering in vpcs['Vpcs']:
            subnet_spoke = vpc_peering['CidrBlock']
            vpcid_spoke = vpc_peering['VpcId']
            region_spoke = region_id
            gwsize_spoke = 't2.micro'
            logger.info('Found VPC %s waiting to be peered. Processing', vpcid_spoke)

            #Open connection to controller
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #Spoke Gateway Creation
            logger.info('Creating Gateway: spoke-%s', vpcid_spoke)
            controller.create_gateway("AWSAccount",
                                      "1",
                                      "spoke-"+vpcid_spoke,
                                      vpcid_spoke,
                                      region_spoke,
                                      gwsize_spoke,
                                      subnet_spoke)
            logger.info('Peering: hub-%s --> spoke-%s' % (vpc_hub, vpcid_spoke))
            controller.peering("hub-"+vpc_hub, "spoke-"+vpcid_spoke)

            logger.info('Done Peering %s. Updating tag:aviatrix-spoke to peered', vpcid_spoke)
            ec2.create_tags(Resources = [ vpcid_spoke ], Tags = [ { 'Key': 'aviatrix-spoke', 'Value': 'peered' } ])

        #Find VPCs with Tag:aviatrix-spoke = false
        #Delete Peer and Gateway for this VPC, when done change the Tag:aviatrix-spoke = unpeered
        vpcs=ec2.describe_vpcs(Filters=[
            { 'Name': 'state', 'Values': [ 'available' ] },
            { 'Name': 'tag:aviatrix-spoke', 'Values': [ 'false' ] }
        ])
        for vpc_peering in vpcs['Vpcs']:
            subnet_spoke = vpc_peering['CidrBlock']
            vpcid_spoke = vpc_peering['VpcId']
            region_spoke = region_id
            gwsize_spoke = 't2.micro'
            logger.info('Found VPC %s waiting to be unpeered. Processing', vpcid_spoke)

            #Open connection to controller
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #Unpeering
            logger.info('UnPeering: hub-%s --> spoke-%s' % (vpc_hub, vpcid_spoke))
            controller.unpeering("hub-"+vpc_hub, "spoke-"+vpcid_spoke)
            #Spoke Gateway Delete
            logger.info('Deleting Gateway: spoke-%s', vpcid_spoke)
            controller.delete_gateway("1", "spoke-"+vpcid_spoke)


            logger.info('Done unPeering %s. Updating tag:aviatrix-spoke to unpeered', vpcid_spoke)
            ec2.create_tags(Resources = [ vpcid_spoke ], Tags = [ { 'Key': 'aviatrix-spoke', 'Value': 'unpeered' } ])
    return {
        'Status' : 'SUCCESS'
    }
