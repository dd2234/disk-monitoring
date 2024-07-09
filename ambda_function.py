import json
import boto3
import calendar
import os
from datetime import datetime, date, time, timedelta

# 读取环境变量
SNS_TOPIC = os.environ['SNS_TOPIC']
DATA_TRANSFER_QUOTA_MB = float(os.environ['DATA_TRANSFER_QUOTA_MB'])
INSTANCE_ID = os.environ['INSTANCE_ID']

def get_current_month_first_day_zero_time():
    """获取当前月份第一天的零点时间"""
    today = date.today()
    first_day = today.replace(day=1)
    first_day_zero_time = datetime.combine(first_day, time.min)
    return first_day_zero_time

def get_current_month_last_day_last_time():
    """获取当前月份最后一天的最后时间"""
    today = date.today()
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    last_day_last_time = datetime.combine(last_day, time(23, 59, 59))
    return last_day_last_time

def stop_instance(instance_id):
    """停止指定的EC2实例"""
    client = boto3.client('ec2')
    response = client.stop_instances(
        InstanceIds=[instance_id],
        Force=True
    )

def get_month_dto_quota():
    """获取每月数据传输配额（MB）"""
    return DATA_TRANSFER_QUOTA_MB

def get_instance_data_usage(instance_id, metric_name):
    """获取指定EC2实例的指定指标的使用数据"""
    cloudwatch = boto3.client('cloudwatch')
    start_time = get_current_month_first_day_zero_time()
    end_time = get_current_month_last_day_last_time()

    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName=metric_name,
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': instance_id
            },
        ],
        StartTime=start_time,
        EndTime=end_time,
        Period=86400,  # 每日统计一次
        Statistics=['Sum'],
        Unit='Bytes'
    )

    data_points = response['Datapoints']
    total_data_usage = sum([data_point['Sum'] for data_point in data_points])
    total_data_usage_mb = total_data_usage / (1024 * 1024)  # 转换为MB
    print(f"Total {metric_name} usage: {total_data_usage_mb} MB")
    return total_data_usage_mb

def push_notification(arn, msg):
    """发送SNS通知"""
    sns_client = boto3.client('sns')
    print(f"SNS arn: {arn}")
    response = sns_client.publish(
        TopicArn=arn,
        Message=msg,
        Subject='EC2 NetworkOut exceeded quota'
    )

def send_email(subject, body, to_email):
    """发送邮件"""
    ses_client = boto3.client('ses')
    response = ses_client.send_email(
        Source=to_email,
        Destination={
            'ToAddresses': [to_email]
        },
        Message={
            'Subject': {
                'Data': subject
            },
            'Body': {
                'Text': {
                    'Data': body
                }
            }
        }
    )
    return response

def lambda_handler(event, context):
    """Lambda函数的主处理逻辑"""
    quota_mb = get_month_dto_quota()
    total_network_out_mb = get_instance_data_usage(INSTANCE_ID, "NetworkOut")
    total_network_in_mb = get_instance_data_usage(INSTANCE_ID, "NetworkIn")
    usage_percent = (total_network_out_mb / quota_mb) * 100

    if usage_percent > 100:
        status_msg = f"流量已用完，机器已停机"
        stop_instance(INSTANCE_ID)
    else:
        status_msg = f"机器正在运行"

    msg = (f"Instance ID: {INSTANCE_ID}\n"
           f"Total NetworkOut Usage: {total_network_out_mb:.2f} MB\n"
           f"Total NetworkIn Usage: {total_network_in_mb:.2f} MB\n"
           f"Quota: {quota_mb:.2f} MB\n"
           f"Usage Percent: {usage_percent:.2f}%\n"
           f"Status: {status_msg}")
    print(msg)

    # 发送通知
    if usage_percent > 100:
        push_notification(SNS_TOPIC, msg)

    # 发送邮件报告
    email_subject = "EC2 Instance Network Usage Report"
    to_email = os.environ['EMAIL_ADDRESS']
    send_email(email_subject, msg, to_email)

    return {
        'statusCode': 200,
        'body': json.dumps('Total NetworkOut data usage from Lambda!')
    }
