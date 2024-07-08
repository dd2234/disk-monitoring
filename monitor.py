import boto3
import os
from datetime import datetime, timedelta

def handler(event, context):
    ec2 = boto3.client('ec2')
    cloudwatch = boto3.client('cloudwatch')
    ec2_instance_ids = os.environ['EC2_INSTANCE_IDS'].split(',')

    for ec2_instance_id in ec2_instance_ids:
        # 获取实例的磁盘使用情况
        response = ec2.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [ec2_instance_id]}])
        for volume in response['Volumes']:
            volume_id = volume['VolumeId']
            metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/EBS',
                MetricName='VolumeWriteOps',
                Dimensions=[{'Name': 'VolumeId', 'Value': volume_id}],
                StartTime=datetime.utcnow() - timedelta(minutes=5),
                EndTime=datetime.utcnow(),
                Period=300,
                Statistics=['Sum']
            )
            if metrics['Datapoints']:
                usage = metrics['Datapoints'][0]['Sum']
                print(f"Instance {ec2_instance_id} volume {volume_id} usage: {usage}")

        # 获取实例的CPU使用情况
        cpu_metrics = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': ec2_instance_id}],
            StartTime=datetime.utcnow() - timedelta(minutes=5),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )
        if cpu_metrics['Datapoints']:
            cpu_usage = cpu_metrics['Datapoints'][0]['Average']
            print(f"Instance {ec2_instance_id} CPU usage: {cpu_usage}%")

        # 获取实例的内存使用情况
        memory_metrics = cloudwatch.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='mem_used_percent',
            Dimensions=[{'Name': 'InstanceId', 'Value': ec2_instance_id}],
            StartTime=datetime.utcnow() - timedelta(minutes=5),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )
        if memory_metrics['Datapoints']:
            memory_usage = memory_metrics['Datapoints'][0]['Average']
            print(f"Instance {ec2_instance_id} memory usage: {memory_usage}%")
