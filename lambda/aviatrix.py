from urllib2 import Request, urlopen, URLError
from time import sleep
import urllib, ssl, json, logging

#Required for SSL Certificate no-verify
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


class Aviatrix:
    logging.basicConfig(filename="./aviatrix.log",level="INFO")

    def __init__(self,controller_ip):
        self.controller_ip = controller_ip
        self.CID = ""

    def avx_api_call(self,method,action,parameters):
        url = "https://%s/v1/api?action=%s" % (self.controller_ip,action)
        for key,value in parameters.iteritems():
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
                quit()
        except URLError, e:
            print 'Failed request. Error:', e

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
