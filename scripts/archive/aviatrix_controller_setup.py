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
                quit()
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
    region_hub = os.environ.get("Region")
    gwsize_hub = os.environ.get("GatewaySizeParam")
    first_run = os.environ.get("first_run")
    setup_run = os.environ.get("setup_run")

    #Determine the Subnet given the VPCID
    ec2=boto3.client('ec2',region_name=region_hub)
    vpcs=ec2.describe_vpcs(Filters=[
        { 'Name': 'vpc-id', 'Values': [ vpc_hub ] }
    ])
    for vpc_peering in vpcs['Vpcs']:
        subnet_hub = vpc_peering['CidrBlock']

    #Start the Controller Initialization process
    controller = Aviatrix(controller_ip)
    controller.login(username,private_ip)
    controller.admin_email(admin_email)
    controller.change_password(username,username,private_ip,password)
    controller.login(username,password)
    controller.initial_setup("run")
    logger.info('Done with Initial Controller Setup')

    # #Account Setup
    # #this step will not be needed with the Marketplace AMI
    controller = Aviatrix(controller_ip)
    controller.login(username,password)
    controller.setup_customer_id("jorge-trial-1495122121.16")

    controller.setup_account_profile("AWSAccount",
                                     password,
                                     admin_email,
                                     "1",
                                     account,
                                     AviatrixRoleApp,
                                     AviatrixRoleEC2)
    controller.create_gateway("AWSAccount",
                              "1",
                              "hub-" +vpc_hub,
                              vpc_hub,
                              region_hub,
                              gwsize_hub,
                              subnet_hub)
    logger.info('Done with Hub Deployment')
    return {
        'Status' : 'SUCCESS'
    }
