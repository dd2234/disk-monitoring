AWSTemplateFormatVersion: '2010-09-09'
Resources:
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties: 
      AssumeRolePolicyDocument: 
        Version: '2012-10-17'
        Statement: 
          - Effect: Allow
            Principal: 
              Service: 
                - lambda.amazonaws.com
            Action: 
              - sts:AssumeRole
      Path: "/"
      Policies:
        - PolicyName: "LambdaExecutionPolicy"
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: "arn:aws:logs:*:*:*"
              - Effect: Allow
                Action:
                  - ec2:DescribeInstances
                  - ec2:DescribeVolumes
                  - cloudwatch:GetMetricStatistics
                Resource: "*"

  DiskMonitoringFunction:
    Type: AWS::Lambda::Function
    Properties:
      Handler: monitor.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Runtime: python3.8
      Code:
        S3Bucket: !Ref CodeS3Bucket
        S3Key: !Ref CodeS3Key
      Environment:
        Variables:
          EC2_INSTANCE_IDS: !Ref Ec2InstanceIds

  CloudWatchEventRule:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: "rate(1 hour)"
      Targets:
        - Arn: !GetAtt DiskMonitoringFunction.Arn
          Id: "DiskMonitoringFunction"

  LambdaInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt DiskMonitoringFunction.Arn
      Action: "lambda:InvokeFunction"
      Principal: "events.amazonaws.com"

Parameters:
  CodeS3Bucket:
    Type: String
    Description: "The name of the S3 bucket containing the Lambda deployment package"
  CodeS3Key:
    Type: String
    Description: "The S3 key of the Lambda deployment package"
  Ec2InstanceIds:
    Type: String
    Description: "Comma-separated list of EC2 instance IDs to monitor"
