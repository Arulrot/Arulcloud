import boto3

REGION = 'ap-south-1'

client = boto3.client('cognito-idp', region_name=REGION)

# Just list all user pools (or check describe_user_pool if you know the ID)
response = client.list_user_pools(MaxResults=10)
print(response)
