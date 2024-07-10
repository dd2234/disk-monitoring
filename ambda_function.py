import json
import boto3
import os
from datetime import datetime, date, time, timedelta

# 读取环境变量
SNS_TOPIC = os.environ['SNS_TOPIC']
DATA_TRANSFER_QUOTA_MB = float(os.environ['DATA_TRANSFER_QUOTA_MB'])
INSTANCE_ID = os.environ['INSTANCE_ID']
EMAIL_ADDRESS = os.environ['EMAIL_ADDRESS']
REGION = os.environ['AWS_REGION']

def get_current_month_first_day_zero_time():
    """获取当前月份第一天的零点时间"""
    today = date.today()
    first_day = today.replace(day=1)
    first_day_zero_time = datetime.combine(first_day, time.min)
    return first_day_zero_time

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

def get_instance_data_usage(instance_id, metric_name, start_time, end_time):
    """获取指定EC2实例在指定时间范围内的指定指标的使用数据"""
    cloudwatch = boto3.client('cloudwatch')

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
        Period=3600,  # 每小时统计一次
        Statistics=['Sum'],
        Unit='Bytes'
    )

    data_points = response['Datapoints']
    total_data_usage = sum([data_point['Sum'] for data_point in data_points if 'Sum' in data_point])
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

def get_region_pricing(region):
    """获取指定区域的流量定价"""
    pricing_client = boto3.client('pricing', region_name='us-east-1')  # Pricing API通常在us-east-1区域
    response = pricing_client.get_products(
        ServiceCode='AmazonEC2',
        Filters=[
            {
                'Type': 'TERM_MATCH',
                'Field': 'location',
                'Value': region
            },
            {
                'Type': 'TERM_MATCH',
                'Field': 'productFamily',
                'Value': 'Data Transfer'
            }
        ]
    )

    # 检查返回的价格列表是否为空
    if not response['PriceList']:
        raise ValueError(f"No pricing information found for region: {region}")

    # 解析价格信息
    price_list = json.loads(response['PriceList'][0])
    price_per_gb = None
    for term in price_list['terms']['OnDemand'].values():
        for price_dimension in term['priceDimensions'].values():
            price_per_gb = float(price_dimension['pricePerUnit']['USD'])
            break
        if price_per_gb:
            break

    if price_per_gb is None:
        raise ValueError(f"Unable to find price per GB for region: {region}")

    # 打印区域流量基础价格
    print(f"Price per GB for region {region}: ${price_per_gb}")

    return price_per_gb

def calculate_network_cost(total_network_out_mb, price_per_gb):
    """根据AWS的流量计费规则计算流量价格"""
    total_network_out_gb = total_network_out_mb / 1024  # 转换为GB

    # 定价规则
    tier1_rate = 0.09  # 0-10TB
    tier2_rate = 0.085  # 10TB - 40TB
    tier3_rate = 0.07  # 40TB - 100TB
    tier4_rate = 0.05  # 超过100TB

    if total_network_out_gb <= 10 * 1024:
        cost = total_network_out_gb * tier1_rate
    elif total_network_out_gb <= 40 * 1024:
        cost = (10 * 1024 * tier1_rate) + ((total_network_out_gb - 10 * 1024) * tier2_rate)
    elif total_network_out_gb <= 100 * 1024:
        cost = (10 * 1024 * tier1_rate) + (30 * 1024 * tier2_rate) + ((total_network_out_gb - 40 * 1024) * tier3_rate)
    else:
        cost = (10 * 1024 * tier1_rate) + (30 * 1024 * tier2_rate) + (60 * 1024 * tier3_rate) + ((total_network_out_gb - 100 * 1024) * tier4_rate)

    return cost

def lambda_handler(event, context):
    """Lambda函数的主处理逻辑"""
    start_time = get_current_month_first_day_zero_time()
    end_time = datetime.utcnow()
    
    quota_mb = get_month_dto_quota()
    total_network_out_mb = get_instance_data_usage(INSTANCE_ID, "NetworkOut", start_time, end_time)
    total_network_in_mb = get_instance_data_usage(INSTANCE_ID, "NetworkIn", start_time, end_time)
    usage_percent = (total_network_out_mb / quota_mb) * 100

    if usage_percent > 100:
        status_msg = f"流量已用完，机器已停机"
        stop_instance(INSTANCE_ID)
    else:
        status_msg = f"机器正在运行"

    try:
        # 获取指定区域的流量定价
        price_per_gb = get_region_pricing(REGION)
    except ValueError as e:
        # 处理获取定价信息失败的情况
        price_per_gb = 0.12  # 使用默认价格或其他适当处理
        print(f"Using default price per GB: ${price_per_gb}")
        print(str(e))
    
    # 计算流量费用
    network_cost = calculate_network_cost(total_network_out_mb, price_per_gb)
    
    msg = (f"Instance ID: {INSTANCE_ID}\n"
           f"Total NetworkOut Usage: {total_network_out_mb:.2f} MB\n"
           f"Total NetworkIn Usage: {total_network_in_mb:.2f} MB\n"
           f"Quota: {quota_mb:.2f} MB\n"
           f"Usage Percent: {usage_percent:.2f}%\n"
           f"Status: {status_msg}\n"
           f"Estimated Network Cost: ${network_cost:.2f}")
    print(msg)

    # 发送通知
    if usage_percent > 100:
        push_notification(SNS_TOPIC, msg)

    # 发送邮件报告
    email_subject = "EC2 Instance Network Usage Report"
    send_email(email_subject, msg, EMAIL_ADDRESS)

    return {
        'statusCode': 200,
        'body': json.dumps('Total NetworkOut data usage from Lambda!')
    }
