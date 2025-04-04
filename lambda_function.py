import json
import os
import boto3
import re
import time
from datetime import datetime

s3 = boto3.client('s3')
BUCKET_NAME = os.getenv("BUCKET_NAME")
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD")

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "png", "jpg", "jpeg", "eml", "msg", "txt", "gif"}

def build_response(status_code, message):
    """
    Helper function to build a response that includes
    CORS headers for AWS_PROXY integration.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Credentials": "true"
        },
        "body": json.dumps(message)
    }

def lambda_handler(event, context):
    # Handle preflight OPTIONS request
    if event.get("httpMethod") == "OPTIONS":
        return build_response(200, {"message": "CORS preflight response"})

    try:
        # Parse request body
        body = json.loads(event.get("body") or "{}")

        # Check password
        if body.get("password") != UPLOAD_PASSWORD:
            return build_response(401, {"error": "Unauthorized: Incorrect password"})

        # Grab the files array: [ { "name": "filename.doc", "type": "application/msword" }, ... ]
        files = body.get("files", [])
        if not files:
            return build_response(400, {"error": "No files found in the request"})

        # Limit the number of files
        if len(files) > 10:
            return build_response(400, {"error": "You can upload a maximum of 10 files"})

        timestamp = int(time.time())
        date_folder = datetime.now().strftime("%Y-%m-%d")

        presigned_urls = []

        for file_obj in files:
            original_filename = file_obj["name"]
            lower_fname = original_filename.lower()
            if lower_fname.endswith(".zip"):
                return build_response(400, {"error": "ZIP files are not allowed"})

            # Check extension
            extension = original_filename.split('.')[-1].lower()
            if extension not in ALLOWED_EXTENSIONS:
                return build_response(
                    400,
                    {"error": f"Invalid file type: {original_filename}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
                )

            # Create sanitized filename
            sanitized_filename = re.sub(r'[^\w\.-]', '_', original_filename)
            s3_key = f"{date_folder}/{timestamp}_{sanitized_filename}"

            # Generate a presigned URL for PUT
            presigned_url = s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": BUCKET_NAME,
                    "Key": s3_key,
                    "Metadata": {
                        "original-filename": original_filename
                    },
                    # optional: "ContentType": file_obj.get("type", "application/octet-stream")
                },
                ExpiresIn=3600  # 1 hour
            )

            presigned_urls.append({
                "fileName": original_filename,
                "s3Key": s3_key,
                "uploadUrl": presigned_url
            })

        return build_response(
            200,
            {
                "message": "Presigned URLs generated successfully",
                "presignedUrls": presigned_urls
            }
        )

    except Exception as e:
        print(f"Error: {str(e)}")
        return build_response(500, {"error": str(e)})
