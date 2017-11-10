import os, boto3
from urllib2 import Request, urlopen, URLError
from time import sleep
import urllib, ssl, json, logging

#Required for SSL Certificate no-verify
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

#logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Aviatrix:
    logging.basicConfig(filename="./aviatrix.log",level="INFO")

    def __init__(self,controller_ip):
        self.controller_ip = controller_ip
        self.CID = ""

    def avx_api_call(self,method,action,parameters):
        url = "https://%s/v1/api?action=%s" % (self.controller_ip,action)
        for key,value in parameters.iteritems():
            value = urllib.quote(value, safe='')
            url = url + "&%s=%s" % (key,value)
        self.url = url
        logging.info("Executing API call:%s" % self.url)
        try:
            if method == "POST":
                data = urllib.urlencode(parameters)
                response = urlopen(self.url, data=data, context=ctx)
            else:
                response = urlopen(self.url, context=ctx)
            json_response = response.read()
            logging.info("HTTP Response: %s" % json_response)
            self.result = json.loads(json_response)
            if self.result['return'] == False:
                self.results = self.result['reason']
            else:
                self.results = self.result['results']
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

def handler(event, context):
    #Read environment Variables
    controller_ip = os.environ.get("Controller_IP")
    username = os.environ.get("Username")
    password = os.environ.get("Password")
    queue_url = os.environ.get("GatewayQueueURL")

    # Receive message from SQS queue
    try:
        # Create SQS client
        sqs = boto3.client('sqs')
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        body = json.loads(message['Body'])

        #Delete received message from queue
        sqs.delete_message(
             QueueUrl=queue_url,
             ReceiptHandle=receipt_handle
         )
        logging.info('Received and deleted message: %s', body)
    except URLError, e:
        print 'Failed request. Error:', e
        return {
            'Status' : 'FAILURE',
            'Error' : e
        }
    if body['action'] == 'deployhub':
        vpc_hub = body['vpc_hub']
        region_hub = body['region_hub']
        gwsize_hub = body['gwsize_hub']
        subnet_hub = body['subnet_hub']

        #Deploy Hub Gateway
        try:
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
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
        except URLError, e:
            logger.info('Failed request. Error: %s', controller.results)
            return {
                'Status' : 'FAILURE',
                'Error' : controller.results
            }
    elif body['action'] == 'deploygateway':
        subnet_spoke = body['subnet_spoke']
        vpcid_spoke = body['vpcid_spoke']
        region_spoke = body['region_spoke']
        gwsize_spoke = body['gwsize_spoke']
        vpc_hub = body['vpc_hub']

        logger.info('Processing VPC %s', vpcid_spoke)

        #Open connection to controller
        try:
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
            ec2=boto3.client('ec2',region_name=region_spoke)
            ec2.create_tags(Resources = [ vpcid_spoke ], Tags = [ { 'Key': 'aviatrix-spoke', 'Value': 'peered' } ])
            return {
            'Status' : 'SUCCESS'
            }
        except URLError, e:
            logger.info('Failed request. Error: %s', controller.results)
            return {
                'Status' : 'FAILURE',
                'Error' : controller.results
            }
    elif body['action'] == 'deletegateway':
        subnet_spoke = body['subnet_spoke']
        vpcid_spoke = body['vpcid_spoke']
        region_spoke = body['region_spoke']
        gwsize_spoke = body['gwsize_spoke']
        vpc_hub = body['vpc_hub']

        logger.info('Processing unpeer of VPC %s', vpcid_spoke)

        #Open connection to controller
        try:
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #Unpeering
            logger.info('UnPeering: hub-%s --> spoke-%s' % (vpc_hub, vpcid_spoke))
            controller.unpeering("hub-"+vpc_hub, "spoke-"+vpcid_spoke)
            #Spoke Gateway Delete
            logger.info('Deleting Gateway: spoke-%s', vpcid_spoke)
            controller.delete_gateway("1", "spoke-"+vpcid_spoke)

            logger.info('Done unPeering %s. Updating tag:aviatrix-spoke to unpeered', vpcid_spoke)
            ec2=boto3.client('ec2',region_name=region_spoke)
            ec2.create_tags(Resources = [ vpcid_spoke ], Tags = [ { 'Key': 'aviatrix-spoke', 'Value': 'unpeered' } ])
            return {
                'Status' : 'SUCCESS'
            }
        except URLError, e:
            logger.info('Failed request. Error: %s', controller.results)
            return {
                'Status' : 'FAILURE',
                'Error' : controller.results
            }
