import json
import boto3
import os
import time
from datetime import datetime
import re

s3 = boto3.client("s3")
BUCKET_NAME = os.getenv("BUCKET_NAME")
UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD")
CLIENT_PREFIX = os.getenv("CLIENT_PREFIX", "default")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "png", "jpg", "jpeg", "eml", "msg", "txt", "gif"}

def build_response(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps({ "body": message }) if isinstance(message, str) else json.dumps(message)
    }

def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return build_response(200, {"message": "CORS preflight OK"})

    try:
        body = json.loads(event.get("body", "{}"))
        path = event.get("path", "")

        if path.endswith("/notify"):
            print("Received upload confirmation:")
            print(json.dumps(body, indent=2))
            return build_response(200, { "message": "Upload logged successfully" })

        if body.get("password") != UPLOAD_PASSWORD:
            return build_response(401, { "error": "Unauthorized: Incorrect password" })

        files = body.get("files", [])
        if not files:
            return build_response(400, { "error": "No files provided" })
        if len(files) > 10:
            return build_response(400, { "error": "Maximum 10 files allowed" })

        presigned_files = []
        timestamp = int(time.time())
        date_folder = datetime.now().strftime("%Y-%m-%d")

        for file in files:
            name = file.get("name")
            ctype = file.get("type", "application/octet-stream")
            ext = name.split(".")[-1].lower()

            if ext not in ALLOWED_EXTENSIONS:
                return build_response(400, { "error": f"Invalid file type: {name}" })

            safe_name = re.sub(r"[^\w\.-]", "_", name)
            key = f"{date_folder}/{timestamp}_{safe_name}"

            url = s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": BUCKET_NAME,
                    "Key": key,
                    "ContentType": ctype,
                    "Metadata": {
                        "client": CLIENT_PREFIX,
                        "original-filename": name
                    }
                },
                ExpiresIn=3600
            )

            presigned_files.append({ "name": name, "url": url, "key": key })

        return build_response(200, { "message": "Presigned URLs generated", "files": presigned_files })

    except Exception as e:
        return build_response(500, { "error": str(e) })
