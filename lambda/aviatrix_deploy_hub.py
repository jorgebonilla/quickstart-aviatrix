from aviatrix import Aviatrix

controller = Aviatrix("34.212.17.238")
controller.login("admin","Aviatrix123%23")
#This might not be needed with the AWS utility AMI
#controller.setup_customer_id("jorge-trial-1495122121.16")
# controller.setup_account_profile("AWS_Account",
#                                  "Aviatrix123%23",
#                                  "jorge@aviatrix.com",
#                                  "1",
#                                  "910395570553",
#                                  "arn:aws:iam::910395570553:role/aviatrix-role-app",
#                                  "arn:aws:iam::910395570553:role/aviatrix-ec2-app")
# controller.create_gateway("AWS_Account",
#                           "1",
#                           "testGW",
#                           "vpc-079bf161",
#                           "us-west-2",
#                           "t2.micro",
#                           "10.0.1.0/24")
