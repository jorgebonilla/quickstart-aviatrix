import os, boto3
from urllib2 import Request, urlopen, URLError
from time import sleep
import urllib, ssl, json, logging
#Needed to load Aviatrix Python API.
from aviatrix import Aviatrix

#logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#Test deploygateway Event JSON
# {
#     "action": "deploygateway",
#     "subnet_spoke": "192.168.1.0/24",
#     "vpcid_spoke": "vpc-f940a381",
#     "region_spoke": "us-east-1",
#     "gwsize_spoke": "t2.micro",
#     "vpcid_hub": "vpc-b53cb1cd"
# }

#Testing Data:
# Deploying a t2.micro takes ~3 minutes
# Deploying a m4.xlarge takes ~3 minutes 30 seconds
#

#Test deletegateway Event JSON
# {
#     "action": "deletegateway",
#     "region_spoke": "us-east-1",
#     "vpcid_hub": "vpc-b53cb1cd",
#     "vpcid_spoke": "vpc-f940a381"
# }

#Testing Data:
# Destroying a t2.micro takes ~1 Min 30 seconds

def tag_spoke(region_spoke,vpcid_spoke,tag):
    ec2=boto3.client('ec2',region_name=region_spoke)
    ec2.create_tags(Resources = [ vpcid_spoke ], Tags = [ { 'Key': 'aviatrix-spoke', 'Value': tag } ])

def handler(event, context):
    #Read environment Variables
    controller_ip = os.environ.get("Controller_IP")
    username = os.environ.get("Username")
    password = os.environ.get("Password")
    queue_url = os.environ.get("GatewayQueueURL")

    # Receive message from SQS queue
    #body=read_queue(queue_url)
    body=event
    #Case Deploy Hub
    if body['action'] == 'deployhub':
        #Variables
        vpcid_hub = body['vpcid_hub']
        region_hub = body['region_hub']
        gwsize_hub = body['gwsize_hub']
        subnet_hub = body['subnet_hub']
        #Processing
        try:
            #Open connection to controller
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #Hub Gateway Creation
            logger.info('Creating Gateway: hub-%s', vpcid_hub)
            controller.create_gateway("AWSAccount",
                                      "1",
                                      "hub-" +vpcid_hub,
                                      vpcid_hub,
                                      region_hub,
                                      gwsize_hub,
                                      subnet_hub)
            # Deploy HA Gateway
            # logger.info('Creating HA Gateway: hub-%s', vpcid_hub)
            # controller.create_gateway("AWSAccount",
            #                           "1",
            #                           "hub-" +vpcid_hub,
            #                           vpcid_hub,
            #                           region_hub,
            #                           gwsize_hub,
            #                           subnet_hub)
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
    #Case Deploy Gateway
    elif body['action'] == 'deploygateway':
        #Variables
        subnet_spoke = body['subnet_spoke']
        vpcid_spoke = body['vpcid_spoke']
        region_spoke = body['region_spoke']
        gwsize_spoke = body['gwsize_spoke']
        vpcid_hub = body['vpcid_hub']
        #Processing
        logger.info('Processing VPC %s. Updating tag:aviatrix-spoke to processing', vpcid_spoke)
        tag_spoke(region_spoke,vpcid_spoke,'processing')
        try:
            #Open connection to controller
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #get the list of existing Spokes
            controller.list_peers_vpc_pairs()
            existing_spokes=[]
            for peers in controller.results['pair_list']:
                existing_spokes.append(peers['vpc_name2'])
            #Spoke Gateway Creation
            logger.info('Creating Gateway: spoke-%s', vpcid_spoke)
            controller.create_gateway("AWSAccount",
                                      "1",
                                      "spoke-"+vpcid_spoke,
                                      vpcid_spoke,
                                      region_spoke,
                                      gwsize_spoke,
                                      subnet_spoke)
            logger.info('Creating HA Gateway: spoke-%s', vpcid_spoke)
            #Create HA GW
            # controller.create_gateway("AWSAccount",
            #                           "1",
            #                           "spoke-"+vpcid_spoke,
            #                           vpcid_spoke,
            #                           region_spoke,
            #                           gwsize_spoke,
            #                           subnet_spoke)

            logger.info('Peering: hub-%s --> spoke-%s' % (vpcid_hub, vpcid_spoke))
            controller.peering("hub-"+vpcid_hub, "spoke-"+vpcid_spoke)
            #Creating the transitive connections
            #if len(existing_spokes) != 0:
                #Create transitive routes for each spoke
                #for spoke in existing_spokes:
                    #controller.extended_vpc_peer(Args)

            logger.info('Done Peering %s. Updating tag:aviatrix-spoke to peered', vpcid_spoke)
            tag_spoke(region_spoke,vpcid_spoke,'peered')
            return {
            'Status' : 'SUCCESS'
            }
        except URLError, e:
            logger.info('Failed request. Error: %s', controller.results)
            return {
                'Status' : 'FAILURE',
                'Error' : controller.results
            }
    #Case Delete Gateway
    elif body['action'] == 'deletegateway':
        #Variables
        region_spoke = body['region_spoke']
        vpcid_hub = body['vpcid_hub']
        vpcid_spoke = body['vpcid_spoke']
        #Processing
        logger.info('Processing unpeer of VPC %s. Updating tag:aviatrix-spoke to processing', vpcid_spoke)
        tag_spoke(region_spoke,vpcid_spoke,'processing')

        try:
            #Open connection to controller
            controller = Aviatrix(controller_ip)
            controller.login(username,password)
            #Unpeering
            logger.info('UnPeering: hub-%s --> spoke-%s' % (vpcid_hub, vpcid_spoke))
            controller.unpeering("hub-"+vpcid_hub, "spoke-"+vpcid_spoke)
            #get the list of existing Spokes
            controller.list_peers_vpc_pairs()
            existing_spokes=[]
            for peers in controller.results['pair_list']:
                existing_spokes.append(peers['vpc_name2'])
            #Delete Transitive routers

            #Spoke Gateway Delete
            logger.info('Deleting Gateway: spoke-%s', vpcid_spoke)
            controller.delete_gateway("1", "spoke-"+vpcid_spoke)

            logger.info('Done unPeering %s. Updating tag:aviatrix-spoke to unpeered', vpcid_spoke)
            tag_spoke(region_spoke,vpcid_spoke,'unpeering')
            return {
                'Status' : 'SUCCESS'
            }
        except URLError, e:
            logger.info('Failed request. Error: %s', controller.results)
            return {
                'Status' : 'FAILURE',
                'Error' : controller.results
            }
