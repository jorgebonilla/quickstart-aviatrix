import os
import boto3
import json
import logging
from urllib2 import Request, urlopen, URLError
#Needed to load Aviatrix Python API.
from aviatrix import Aviatrix
#Needed for Lambda Custom call
import cfn_resource

handler = cfn_resource.Resource()

#logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

@handler.create
def controller(event,context):
    #Read environment Variables
    controller_ip = os.environ.get("Controller_IP")
    username = os.environ.get("Username")
    private_ip = os.environ.get("Private_IP")
    admin_email = os.environ.get("Admin_Email")
    password = os.environ.get("Password")
    account = os.environ.get("Account")
    aviatrixroleapp = os.environ.get("AviatrixRoleApp")
    aviatrixroleec2 = os.environ.get("AviatrixRoleEC2")
    vpcid_hub = os.environ.get("VPC")
    subnet_hub = os.environ.get("SubnetParam")
    region_hub = os.environ.get("Region")
    gwsize_hub = os.environ.get("GatewaySizeParam")
    gateway_queue = os.environ.get("GatewayQueue")
    gatewaytopic = os.environ.get("GatewayTopic")

    #Start the Controller Initialization process
    try:
        controller = Aviatrix(controller_ip)
        controller.login(username,private_ip)
        controller.admin_email(admin_email)
        controller.change_password(username,username,private_ip,password)
        controller.login(username,password)
        controller.initial_setup("run")
        logger.info('Done with Initial Controller Setup')
    except URLError, e:
        logger.info('Failed request. Error: %s', controller.results)
        return {
            'Status' : 'FAILURE',
            'Error' : controller.results
        }
    # #Account Setup
    try:
        controller = Aviatrix(controller_ip)
        controller.login(username,password)

        controller.setup_account_profile("AWSAccount",
                                         password,
                                         admin_email,
                                         "1",
                                         account,
                                         aviatrixroleapp,
                                         aviatrixroleec2)
        logger.info('Done with Account creation')
        message = {}
    except URLError, e:
        logger.info('Failed request. Error: %s', controller.results)
        return {
            'Status' : 'FAILURE',
            'Error' : controller.results
        }
    #Gather necessary info to deploy Hub GW
    message['action'] = 'deployhub'
    message['vpcid_hub'] = vpcid_hub
    message['region_hub'] = region_hub
    message['gwsize_hub'] = gwsize_hub
    message['subnet_hub'] = subnet_hub
    logger.info('Creating Hub VPC %s. Sending SQS message', message['vpcid_hub'])

    #Add New Hub Gateway to SQS
    sqs = boto3.resource('sqs')
    sns = boto3.client('sns')
    queue = sqs.get_queue_by_name(QueueName=gateway_queue)
    response = queue.send_message(MessageBody=json.dumps(message))
    sns.publish(
        TopicArn=gatewaytopic,
        Subject='Create Hub Gateway',
        Message=json.dumps(message)
    )
    return {
        "PhysicalResourceId": "arn:aws:fake:myID"
    }
