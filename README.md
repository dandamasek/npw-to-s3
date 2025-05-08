# AWS infrastructure
Python 3.13.2 is higly recommended

## Upload stack
CloudFormation > Create stack > Choose an existing template > Upload a template file (upload infrastrucute.yaml)

 
## Manual Setup Guide for AWS EC2 + Lambda + S3 Infrastructure
This guide describes how to manually create the same infrastructure that can be automatically deployed using the CloudFormation template, if upload stack fails.

### 1. Create an S3 bucket for data storage

1. Log in to the AWS Management Console
2. Navigate to the S3 service
3. Click "Create bucket"
4. Enter the name "meteo_data"
5. Disable all public access blocking options for public access
6. Complete the bucket creation
7. Set a bucket policy to allow public read access:
   - Go to the bucket → Permissions → Bucket policy
   - Insert the following policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::meteo_data/*"
       }
     ]
   }
   ```

### 2. Create IAM role for EC2

1. Navigate to the IAM service
2. Create a role "ec2-s3-full-access" with AmazonS3FullAccess permission
3. Set a trust relationship with the EC2 service

### 3. Create EC2 instance

1. Navigate to the EC2 service
2. Launch a new instance with the following parameters:
   - AMI: ami-0866a3c8686eaeeba (or equivalent current Amazon Linux)
   - Instance type: t2.micro
   - Key pair: AdminKeyPair (create if it doesn't exist)
   - Security group: Allow SSH (22) and HTTPS (443) ports
   - Add 25GB EBS storage
   - IAM role: ec2-s3-full-access
   - Add tags:
     - Name: Virtual
     - schedule: 16:55-18:00
     - schedule-tz: UTC

### 4. Create Lambda functions for scheduling

Navigate to the Lambda service


First Lambda function (EC2InstanceScheduler)
- Runtime: Python 3.9
- Memory: 128 MB
- Timeout: 3 seconds
- Role: Create a new role with permission to work with EC2 (LambdaEC2ControlRole)
- Code:
```python
import boto3
import datetime

def lambda_handler(event, context):
    ec2 = boto3.resource('ec2')
    current_hour = datetime.datetime.now().hour
    
    # Sample code - customize as needed
    if current_hour == 17:
        # Start instances tagged with the appropriate tag
        instances = ec2.instances.filter(Filters=[{'Name': 'tag:schedule', 'Values': ['*16:55-18:00*']}])
        for instance in instances:
            if instance.state['Name'] == 'stopped':
                instance.start()
    elif current_hour == 18:
        # Stop instances tagged with the appropriate tag
        instances = ec2.instances.filter(Filters=[{'Name': 'tag:schedule', 'Values': ['*16:55-18:00*']}])
        for instance in instances:
            if instance.state['Name'] == 'running':
                instance.stop()
                
    return {
        'statusCode': 200,
        'body': 'EC2 instances scheduled successfully'
    }
```

## 5. Set up CloudWatch Events for scheduling

1. Navigate to the CloudWatch service
2. Create a new rule:
   - Name: ec2-cron
   - Description: ec2-cron
   - Schedule: cron(00 17,18 * * ? *)
   - Target: EC2InstanceScheduler Lambda function

## 6. Integration and testing

1. Upload your script (used for data collection) to the EC2 instance
    ```bash
    git clone https://github.com/dandamasek/Meteo-data-on-S3.git
    ```
2. Modify the script to store data in the meteo_data S3 bucket
3. Test the scheduled launching of the EC2 instance at 17:00 and 18:00 UTC
4. Verify that data is correctly saved to the S3 bucket

This configuration ensures that the EC2 instance will be started and stopped according to schedule, the script will run on the instance, and data will be stored in a publicly accessible S3 bucket.


# CONFIG_FILE
create config.py in both SERVER and CLIENT directory, and include all theese:

aws_access_key_id="<aws_access_key_id>"
aws_secret_access_key="<aws_access_key_id>"
BUCKET_NAME = "<BUCKET_NAME>"

### Keep for scraping from CHMI.cz
DIR = "CZ"
DOMAINLA = "https://opendata.chmi.cz/meteorology/weather/nwp_aladin/Lambert_2.3km/"
DOMAINCZ = "https://opendata.chmi.cz/meteorology/weather/nwp_aladin/CZ_1km/"
SUBDOMAINCZ = "/ALADCZ1K4opendata_"
SUBDOMAINLA = "/ALADLAMB4opendata_"

ALADIN_ATTRIBUTES = {
"MSLPRESSURE" : "MSLPRESSURE",
"CLSTEMPERATURE" : "CLSTEMPERATURE", 
"CLSHUMI_RELATIVE" : "CLSHUMI_RELATIVE",
"CLSWIND_SPEED" : "CLSWIND_SPEED",
"CLSWIND_DIREC" : "CLSWIND_DIREC",           
"CLSU_RAF_MOD_XFU" : "CLSU_RAF_MOD_XFU",    # not in CZ1
"CLSV_RAF_MOD_XFU" : "CLSV_RAF_MOD_XFU",
"SURFNEBUL_BASSE" : "SURFNEBUL_BASSE",
"SURFNEBUL_MOYENN" : "SURFNEBUL_MOYENN",
"SURFNEBUL_HAUTE" : "SURFNEBUL_HAUTE",
"CLS_VISICLD" : "CLS_VISICLD",
"CLS_VISIPRE" : "CLS_VISIPRE",
"SURFRAINFALL" : "SURFRAINFALL",
"SURFSNOWFALL" : "SURFSNOWFALL",
"SURFPREC_TOTAL" : "SURFPREC_TOTAL",
"PRECIP_TYPE" : "PRECIP_TYPE",
"PRECIP_TYPESEV" : "PRECIP_TYPESEV",
"SURFCAPE_POS_F00" : "SURFCAPE_POS_F00",     # not in CZ1
"SURFCIEN_POS_F00" : "SURFCIEN_POS_F00",
"SURFDIAG_FLASH" : "SURFDIAG_FLASH",         # not in CZ!
"MAXSIM_REFLECTI" : "MAXSIM_REFLECTI",
"SURFNEBUL_TOTALE" : "SURFNEBUL_TOTALE",     # good-to-have
"CLPVEIND_MOD_XFU" : "CLPVEIND_MOD_XFU",     # good-to-have
"SURFRF_SHORT_DO" : "SURFRF_SHORT_DO",       # good-to-have
"SURFRF_LONG_DO" : "SURFRF_LONG_DO",         # good-to-have
"SURF_RAYT_DIR" : "SURF_RAYT_DIR",           # good-to-have
"SUNSHINE_DUR" : "SUNSHINE_DUR",             # good-to-have
"SURFRESERV_NEIGE" : "SURFRESERV_NEIGE",     # good-to-have
}
