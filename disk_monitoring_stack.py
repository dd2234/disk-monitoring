from aws_cdk import core
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
import boto3

class DiskMonitoringStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # 获取所有EC2实例ID
        ec2_client = boto3.client('ec2')
        instances = ec2_client.describe_instances()
        instance_ids = [instance['InstanceId'] for reservation in instances['Reservations'] for instance in reservation['Instances']]

        # 创建IAM角色并附加CloudWatch权限
        role = iam.Role(self, "LambdaExecutionRole",
                        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"))
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ReadOnlyAccess"))

        # Lambda函数代码存放在本地
        code = _lambda.Code.from_asset("lambda")

        # 创建Lambda函数，用于检查EC2磁盘使用情况
        lambda_function = _lambda.Function(self, "DiskMonitoringFunction",
                                           runtime=_lambda.Runtime.PYTHON_3_8,
                                           handler="monitor.handler",
                                           code=code,
                                           role=role,
                                           environment={
                                               'EC2_INSTANCE_IDS': ','.join(instance_ids)
                                           })

        # 创建EventBridge事件，每5分钟触发一次Lambda函数
        rule = events.Rule(self, "Rule",
                           schedule=events.Schedule.rate(core.Duration.minutes(5)))
        rule.add_target(targets.LambdaFunction(lambda_function))

app = core.App()
DiskMonitoringStack(app, "DiskMonitoringStack")
app.synth()
