"""Make the inbound handler importable without AWS or a live NetBox."""

import os
import sys
from pathlib import Path

os.environ.setdefault("NETBOX_URL", "https://netbox.example.com")
os.environ.setdefault("NETBOX_API_TOKEN", "test-token")
os.environ.setdefault("S3_BUCKET_NAME", "inbound-test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions" / "inbound"))
