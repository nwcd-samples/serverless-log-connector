######################################
# refer to
# https://github.com/ccampo133/rds-logs-to-s3
# https://github.com/awslabs/rds-support-tools/tree/master/database-logs/move-rds-logs-to-s3
# why do i make some change?
# 1.incremental appending 
# 2.support big size file
# 3.add s3 prefix to easy to query by athena
# 4.gzip
######################################
from __future__ import print_function
import boto3
import botocore
from botocore.exceptions import ClientError
from datetime import datetime
import io
import gzip

# change it to your region code
region = "cn-northwest-1"


# initialize
rds_client = boto3.client('rds', region_name=region)
s3client = boto3.client('s3', region_name=region)
# used to save status info
dynamodb = boto3.client('dynamodb', region_name=region)


def copy_logs_from_rds_to_s3(rds_instance_name: str,
                             s3_bucket_name: str,
                             log_name_prefix: str):
    last_writen_key = rds_instance_name + "_" + "last_writen"

    last_written_time = 0
    last_written_this_run = 0
    backup_start_time = datetime.now()

    # check if the S3 bucket exists and is accessible
    try:
        s3client.head_bucket(Bucket=s3_bucket_name)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response['ResponseMetadata']['HTTPStatusCode'])
        if error_code == 404:
            print("Error: Bucket name provided not found")
            raise e
        else:
            print("Error: Unable to access bucket name, error: " + e.response['Error']['Message'])
            raise e

    # get the config file, if the config isn't present this is the first run
    try:
        # query last_written_time
        wr = dynamodb.get_item(TableName='db_log_to_s3', Key={'db_log_name': {'S': last_writen_key}})
        if 'Item' in wr:
            last_written_time = int(wr['Item']['mark']['S'])

        print("Found marker from last log download, retrieving log files with lastWritten time after %s" % str(
            last_written_time))
    except botocore.exceptions.ClientError as e:
        print("Failed to access dynamodb  table db_log_to_s3: ", e)
        raise e

    # copy the logs in batches to s3
    copied_file_count = 0
    log_marker = ""
    more_logs_remaining = True
    while more_logs_remaining:
        db_logs = rds_client.describe_db_log_files(DBInstanceIdentifier=rds_instance_name,
                                                   FilenameContains=log_name_prefix,
                                                   FileLastWritten=last_written_time, Marker=log_marker)
        if 'Marker' in db_logs and db_logs['Marker'] != "":
            log_marker = db_logs['Marker']
        else:
            more_logs_remaining = False

        # copy the logs in this batch
        for dbLog in db_logs['DescribeDBLogFiles']:
            print("FileNumber: ", copied_file_count + 1)
            print("Downloading log file: %s found and with LastWritten value of: %s " % (
                dbLog['LogFileName'], dbLog['LastWritten']))
            if int(dbLog['LastWritten']) > last_written_this_run:
                last_written_this_run = int(dbLog['LastWritten'])

            log_file_key = f"{rds_instance_name}-{dbLog['LogFileName']}"

            # get last mark
            lr = dynamodb.get_item(TableName='db_log_to_s3', Key={'db_log_name': {'S': log_file_key}})
            if 'Item' in lr:
                marker = lr['Item']['mark']['S']
            else:
                marker = '0'

            # download the log file

            try:
                part = 0
                while True:
                    log_file = rds_client.download_db_log_file_portion(DBInstanceIdentifier=rds_instance_name,
                                                                       LogFileName=dbLog['LogFileName'], Marker=marker)
                    print(f"download log file {dbLog['LogFileName']}")

                    log_file_data = log_file['LogFileData']
                    marker = log_file['Marker']

                    log_file_data_cleaned = log_file_data.encode(errors='ignore')
                    my_gzipped_bytes = gzip.compress(log_file_data_cleaned)
                    content = io.BytesIO(my_gzipped_bytes)
                    # upload the log file to S3

                    time_prefix = backup_start_time.strftime('%Y-%m-%dT%H:%M')
                    o_name = f"db={rds_instance_name}/ingestion_time={time_prefix}/{dbLog['LogFileName']}/{part}.log.gzip"

                    s3client.put_object(Bucket=s3_bucket_name, Key=o_name, Body=content)
                    print(f"Uploaded {dbLog['LogFileName']}:{part} to S3 {s3_bucket_name}")
                    part += 1
                    if not log_file['AdditionalDataPending']:
                        break
            except Exception as e:
                print("File download failed: ", e)
                continue
            finally:
                dynamodb.put_item(TableName='db_log_to_s3', Item={
                    'db_log_name': {'S': log_file_key},
                    'mark': {'S': marker}
                })

            copied_file_count += 1
            print("Uploaded log file %s to S3 bucket %s" % (dbLog['LogFileName'], s3_bucket_name))

    print("Copied ", copied_file_count, "file(s) to s3")

    # Update the last written time in the config
    if last_written_this_run > 0:
        try:
            dynamodb.put_item(TableName='db_log_to_s3', Item={
                'db_log_name': {'S': last_writen_key},
                'mark': {'S': str(last_written_this_run)}
            })
        except botocore.exceptions.ClientError as e:
            print(
                f"Failed to set last_written_this_run: {last_written_this_run}, error {e.response['Error']['Message']}")
            raise e

    print("Log file export complete")

if __name__ == '__main__':
    response = rds_client.describe_db_instances()
    db_instances_name = [item['DBInstanceIdentifier'] for item in response['DBInstances']]
    for db in db_instances_name:
        print(f"process {db} ....")
        copy_logs_from_rds_to_s3(db, "tx-rds-audit", "audit")
        print(f"success to sync log file for {db} ....")
