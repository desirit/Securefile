import json
import boto3
import os
import datetime

s3 = boto3.client('s3')
bucket_name = os.environ['UPLOAD_BUCKET']  # <== Must match "UPLOAD_BUCKET" from CF
url_expiration = 3600

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        password = body.get('password')
        files = body.get('files', [])

        # Check password
        if password != os.environ['UPLOAD_PASSWORD']:
            return error_response(403, "Unauthorized")

        # Generate presigned POST for each file
        generated_urls = []
        for file in files:
            key = f"{datetime.datetime.utcnow().strftime('%Y-%m-%d/%s_')}{file['name']}"
            ctype = file.get('type', 'application/octet-stream')

            fields = {
                "acl": "private",
                "Content-Type": ctype
            }
            conditions = [
                {"acl": "private"},
                {"Content-Type": ctype}
            ]
            presigned = s3.generate_presigned_post(
                Bucket=bucket_name,
                Key=key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=url_expiration
            )
            generated_urls.append({
                'name': file['name'],
                'url': presigned['url'],
                'fields': presigned['fields'],
                'key': key
            })

        return success_response({
            "message": "Presigned POST URLs generated",
            "files": generated_urls
        })

    except Exception as e:
        print("Lambda error:", str(e))
        return error_response(500, str(e))


def success_response(body_dict):
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "*"
        },
        "body": json.dumps(body_dict)
    }

def error_response(status, message):
    return {
        "statusCode": status,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "*"
        },
        "body": json.dumps({ "error": message })
    }
