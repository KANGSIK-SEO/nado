#!/usr/bin/env python3
"""b3-1: AWS 서울 리전 VPC/공개 서브넷/IGW/보안 그룹/Ubuntu EC2 CloudFormation 생성기.
실행 후 template.yaml을 검토해 `aws cloudformation deploy`한다.
HTTP 80은 공개, SSH 22는 MyIpCidr만 허용한다. 종료는 delete-stack 후 EBS/EIP/Billing을 확인한다."""
from pathlib import Path
import argparse
T='''AWSTemplateFormatVersion: '2010-09-09'
Description: least privilege public nginx practice
Parameters:
  KeyName: {Type: AWS::EC2::KeyPair::KeyName}
  MyIpCidr: {Type: String, Default: 203.0.113.10/32}
Resources:
  VPC: {Type: AWS::EC2::VPC, Properties: {CidrBlock: 10.0.0.0/16, Tags: [{Key: Name, Value: nado-vpc}]}}
  IGW: {Type: AWS::EC2::InternetGateway}
  Attach: {Type: AWS::EC2::VPCGatewayAttachment, Properties: {VpcId: !Ref VPC, InternetGatewayId: !Ref IGW}}
  Subnet: {Type: AWS::EC2::Subnet, Properties: {VpcId: !Ref VPC, CidrBlock: 10.0.1.0/24, MapPublicIpOnLaunch: true, AvailabilityZone: ap-northeast-2a}}
  Routes: {Type: AWS::EC2::RouteTable, Properties: {VpcId: !Ref VPC}}
  Default: {Type: AWS::EC2::Route, DependsOn: Attach, Properties: {RouteTableId: !Ref Routes, DestinationCidrBlock: 0.0.0.0/0, GatewayId: !Ref IGW}}
  Association: {Type: AWS::EC2::SubnetRouteTableAssociation, Properties: {SubnetId: !Ref Subnet, RouteTableId: !Ref Routes}}
  SG: {Type: AWS::EC2::SecurityGroup, Properties: {GroupDescription: HTTP public SSH restricted, VpcId: !Ref VPC, SecurityGroupIngress: [{IpProtocol: tcp, FromPort: 80, ToPort: 80, CidrIp: 0.0.0.0/0}, {IpProtocol: tcp, FromPort: 22, ToPort: 22, CidrIp: !Ref MyIpCidr}]}}
  EC2: {Type: AWS::EC2::Instance, Properties: {ImageId: '{{resolve:ssm:/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id}}', InstanceType: t3.micro, KeyName: !Ref KeyName, SubnetId: !Ref Subnet, SecurityGroupIds: [!GetAtt SG.GroupId], BlockDeviceMappings: [{DeviceName: /dev/sda1, Ebs: {VolumeSize: 10, DeleteOnTermination: true}}], UserData: {Fn::Base64: |\n          #!/bin/bash\n          apt-get update -y && apt-get install -y nginx\n          printf 'Hello Cloud\\n' > /var/www/html/index.html\n          printf 'OK\\n' > /var/www/html/health\n          systemctl enable --now nginx\n          }}}
Outputs:
  HealthUrl: {Value: !Sub 'http://${EC2.PublicIp}/health'}
'''
V='''#!/usr/bin/env bash
set -euo pipefail
STACK="${1:?stack name}"; REGION="${AWS_REGION:-ap-northeast-2}"
URL=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query "Stacks[0].Outputs[?OutputKey=='HealthUrl'].OutputValue" --output text)
curl --fail --show-error "$URL"; echo "200 OK: $URL"
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('infra'));a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);(a.out/'template.yaml').write_text(T,encoding='utf-8');(a.out/'verify.sh').write_text(V,encoding='utf-8');(a.out/'verify.sh').chmod(0o750);(a.out/'cleanup-checklist.txt').write_text('EC2 terminated\nEBS deleted\nElastic IP released\nIGW detached/deleted\nVPC/subnet/routes deleted\nBilling 확인\n',encoding='utf-8');print('생성 완료:',a.out.resolve())
if __name__=='__main__':main()
