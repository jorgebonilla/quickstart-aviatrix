import unittest
from  aviatrix_poller import *

class Aviatrix_Poller_Test(unittest.TestCase):
  def test_find_subnets(self):
    region_id='us-east-1'
    vpc_id='vpc-afdee5d7'
    result=find_subnets(region_id,vpc_id)
    self.assertIs(type(result), list)
    for subnet in result:
        self.assertEquals(subnet['SubnetId'][:6],'subnet')
        self.assertEquals(subnet['Name'][:8],'Unittest')


if __name__ == '__main__':
  unittest.main()
