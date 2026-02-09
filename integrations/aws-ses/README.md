# AWS SES Integration for netbox-notices

A self-contained AWS SAM application that provides complete email lifecycle management for the netbox-notices plugin:

- **Inbound** — Parse provider maintenance emails (SES &rarr; S3 &rarr; Lambda &rarr; NetBox API)
- **Outbound** — Deliver prepared notifications via SES with tracking
- **Tracking** — Process SES delivery events and update notification status in NetBox

## Architecture

```
                    INBOUND                           OUTBOUND
                    ───────                           ────────
Provider Email                                    NetBox API
      │                                          (prepared-notifications)
      ▼                                               │
┌──────────┐                                    ┌─────┴─────┐
│  AWS SES  │                                    │  Outbound  │
│ (Receipt) │                                    │   Lambda   │◄── EventBridge
└────┬──────┘                                    └─────┬──────┘    (schedule)
     │                                                 │
     ├──► S3 (raw email)                               │ ses:SendRawEmail
     │                                                 │ + notification_id tag
     ▼                                                 ▼
┌──────────┐                                    ┌──────────┐
│ Inbound  │                                    │  AWS SES  │
│  Lambda  │──► NetBox API                      │ (Send)    │
└──────────┘    (maintenance,                   └─────┬─────┘
                 impact,                              │
                 eventnotification)                   │
                                                      ▼
                    TRACKING                   ┌──────────────┐
                    ────────                   │Configuration │
                                               │    Set       │
              NetBox API ◄──┐                  └──────┬───────┘
         (status updates,   │                         │
          journal entries)  │                         ▼
                            │                  ┌──────────┐
                      ┌─────┴─────┐            │ SNS Topic│
                      │ Tracking  │◄───────────└──────────┘
                      │  Lambda   │
                      └───────────┘
```

## Prerequisites

- **AWS CLI** configured with appropriate credentials
- **AWS SAM CLI** (`pip install aws-sam-cli`)
- **Python 3.12** (for local testing)
- **NetBox** with the netbox-notices plugin installed and the outgoing notifications feature configured
- **AWS SES** — domain verified for sending (see [Email Authentication](#email-authentication) below); for inbound, domain also needs MX records pointing to SES
- **Network** — Lambda functions must be able to reach the NetBox API over HTTPS. If NetBox is not publicly accessible, see [VPC Deployment](#vpc-deployment)

## Quick Start

### 1. Clone and configure

```bash
cd integrations/aws-ses/

# Review and edit parameters in samconfig.toml (optional)
# Or pass them at deploy time
```

### 2. Build

```bash
sam build
```

### 3. Deploy

```bash
sam deploy --guided
```

You will be prompted for:

| Parameter | Description |
|-----------|-------------|
| `NetBoxUrl` | Your NetBox URL (e.g. `https://netbox.example.com`) |
| `NetBoxApiToken` | API token with write access to the notices plugin |
| `SesReceiptDomain` | Domain for inbound emails (leave empty to skip inbound) |
| `SesFromAddress` | Verified sender address for outbound emails |
| `SesConfigSetName` | Name for the SES Configuration Set (default: `netbox-notices-tracking`) |
| `EnableOutboundPolling` | Enable scheduled polling: `true` or `false` (default: `true`) |
| `OutboundPollInterval` | How often to poll for ready notifications (default: `rate(5 minutes)`) |
| `InboundS3BucketName` | Globally unique S3 bucket name for inbound emails |
| `WebhookSecret` | Shared secret for NetBox webhook signature verification (leave empty to disable webhook) |
| `VpcSubnetIds` | Comma-separated private subnet IDs for VPC deployment (leave empty to skip) |
| `VpcSecurityGroupIds` | Comma-separated security group IDs for VPC deployment (leave empty to skip) |

### 4. Activate the SES Receipt Rule Set (Inbound only)

SES receipt rule sets must be activated manually:

```bash
aws ses set-active-receipt-rule-set \
  --rule-set-name netbox-notices-ses-inbound-rules
```

> **Note:** Only one receipt rule set can be active per AWS account in a given region. If you have an existing active rule set, add the receipt rule to it instead.

### 5. Verify it works

**Outbound (polling):** Create a PreparedNotification in NetBox, approve it (status &rarr; ready), and wait for the next poll interval. The Lambda will pick it up, send via SES, and update the status to `sent`.

**Outbound (webhook):** Approve a PreparedNotification — the NetBox Event Rule fires immediately, and the Lambda sends within seconds.

**Tracking:** After the email is delivered, SES publishes a Delivery event to SNS, which triggers the tracking Lambda to update the notification status to `delivered`.

**Inbound:** Forward a provider maintenance email to your SES receipt domain. The Lambda will parse it and create a Maintenance event in NetBox.

## Configuration Reference

### Environment Variables

All Lambda functions share:

| Variable | Description |
|----------|-------------|
| `NETBOX_URL` | NetBox base URL |
| `NETBOX_API_TOKEN` | API token for NetBox |

**Inbound-specific:**

| Variable | Description |
|----------|-------------|
| `S3_BUCKET_NAME` | S3 bucket where SES stores raw emails |
| `PROVIDER_MAP` | JSON object mapping email domains to parser names (optional, has sensible defaults) |

**Outbound-specific:**

| Variable | Description |
|----------|-------------|
| `SES_FROM_ADDRESS` | Verified sender email address |
| `SES_CONFIGURATION_SET` | SES Configuration Set name for tracking |
| `WEBHOOK_SECRET` | Shared secret for validating NetBox webhook signatures (optional) |

### Provider Map

The inbound Lambda identifies providers by matching the sender's email domain. The default map covers major providers:

| Domain | Provider |
|--------|----------|
| `zayo.com` | zayo |
| `colt.net` | colt |
| `verizonbusiness.com` | verizon |
| `cogentco.com` | cogent |
| `aquacomms.com` | aquacomms |
| `arelion.com` | arelion |
| `amazon.com` | aws |
| `bso.co` | bso |
| `equinix.com` | equinix |
| `lumen.com` | lumen |
| `momentumtelecom.com` | momentum |
| `superonline.net` | seaborn |
| `tisparkle.com` | sparkle |
| `telstra.com` | telstra |

Override by setting the `PROVIDER_MAP` environment variable to a JSON object:

```json
{
  "zayo.com": "zayo",
  "customcarrier.com": "genericprovider"
}
```

### SES Event &rarr; NetBox Status Mapping

| SES Event | NetBox Action |
|-----------|---------------|
| Delivery | Status &rarr; `delivered` |
| Bounce | Status &rarr; `failed` |
| Complaint | Status &rarr; `failed` |
| Reject | Status &rarr; `failed` |
| Rendering Failure | Status &rarr; `failed` |
| Send | Journal entry (informational) |
| Open | Journal entry (informational) |
| Click | Journal entry (informational) |
| DeliveryDelay | Journal entry (informational) |

## Manual Setup

If you prefer to set up resources manually instead of using SAM:

### Step 1: Create the S3 Bucket

Create an S3 bucket for inbound emails with a 30-day lifecycle policy. Add a bucket policy allowing SES to write objects:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSESPuts",
      "Effect": "Allow",
      "Principal": { "Service": "ses.amazonaws.com" },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::YOUR-BUCKET/*",
      "Condition": {
        "StringEquals": { "AWS:SourceAccount": "YOUR-ACCOUNT-ID" }
      }
    }
  ]
}
```

### Step 2: Create the SES Configuration Set

1. Go to **SES &rarr; Configuration sets &rarr; Create set**
2. Name it `netbox-notices-tracking`
3. Add an **Event destination**:
   - Name: `sns-tracking`
   - Events: Send, Delivery, Bounce, Complaint, Reject, Open, Click, Rendering Failure, Delivery Delay
   - Destination: SNS topic (create one, allow SES to publish to it)

### Step 3: Create Lambda Functions

Create three Lambda functions (Python 3.12, 256 MB, 120s timeout) from the `functions/` directories. Set the environment variables as described above.

**IAM policies needed:**

- **Inbound:** `s3:GetObject` on the inbound email bucket
- **Outbound:** `ses:SendRawEmail`
- **Tracking:** No additional policies (only calls NetBox API)

### Step 4: Wire Up Triggers

- **Inbound:** SES receipt rule &rarr; S3 action (store email) + Lambda action (invoke inbound function)
- **Outbound (polling):** EventBridge scheduled rule &rarr; invoke outbound function every N minutes
- **Outbound (webhook):** API Gateway HTTP API &rarr; POST /webhook/outbound &rarr; invoke outbound function. Set `WEBHOOK_SECRET` env var on the Lambda to match the secret in the NetBox Webhook.
- **Tracking:** SNS subscription on the tracking topic &rarr; invoke tracking function

### Step 5: Create SES Receipt Rule (Inbound)

1. Go to **SES &rarr; Email receiving &rarr; Rule sets**
2. Create a rule set and add a rule with:
   - Recipient: your inbound domain
   - Actions: S3 (deliver to bucket) then Lambda (invoke inbound function)
3. Set the rule set as active

## Local Testing with SAM

Use the provided test events for local invoke:

```bash
# Build first
sam build

# Test inbound (requires S3 bucket with a test email)
sam local invoke InboundFunction -e events/inbound_ses.json

# Test outbound — scheduled poll (requires NetBox to be reachable)
sam local invoke OutboundFunction -e events/outbound_schedule.json

# Test outbound — webhook trigger (signature will fail without valid HMAC)
sam local invoke OutboundFunction -e events/outbound_webhook.json

# Test tracking events
sam local invoke TrackingFunction -e events/tracking_delivery.json
sam local invoke TrackingFunction -e events/tracking_bounce.json
sam local invoke TrackingFunction -e events/tracking_open.json
```

Override environment variables for local testing:

```bash
sam local invoke OutboundFunction -e events/outbound_schedule.json \
  --env-vars '{"OutboundFunction": {"NETBOX_URL": "http://localhost:8008", "NETBOX_API_TOKEN": "your-token", "SES_FROM_ADDRESS": "test@example.com", "SES_CONFIGURATION_SET": ""}}'
```

## Outbound Delivery Mode

The outbound Lambda supports two independent trigger modes. You choose one or both at deploy time:

| Mode | Trigger | Latency | Controlled by |
|------|---------|---------|---------------|
| **Polling** | EventBridge schedule | Up to poll interval | `EnableOutboundPolling` (default `true`) |
| **Webhook** | NetBox Event Rule | Seconds | `WebhookSecret` (default empty = off) |

### Choosing a mode

| Scenario | Parameters |
|----------|-----------|
| **Polling only** (default) | `EnableOutboundPolling=true` |
| **Webhook only** | `EnableOutboundPolling=false`, `WebhookSecret=<secret>` |
| **Both** (belt-and-suspenders) | `EnableOutboundPolling=true`, `WebhookSecret=<secret>` |

When both are enabled, the webhook provides near-instant delivery while the schedule acts as a safety net for any notifications the webhook might miss (the schedule simply skips already-sent notifications).

### Enabling the Webhook

Set the `WebhookSecret` parameter during deployment. This creates an API Gateway HTTP API endpoint and outputs the URL:

```bash
# Webhook only
sam deploy --parameter-overrides \
  EnableOutboundPolling=false \
  WebhookSecret=my-secret-value ...

# Both modes
sam deploy --parameter-overrides \
  WebhookSecret=my-secret-value ...
```

After deployment, the stack outputs a `WebhookUrl` like:
```
https://abc123.execute-api.us-east-1.amazonaws.com/prod/webhook/outbound
```

### Configuring NetBox

1. Go to **Operations &rarr; Webhooks** and create a new Webhook:

   | Field | Value |
   |-------|-------|
   | Name | `SES Outbound Delivery` |
   | Payload URL | `https://abc123.execute-api.../prod/webhook/outbound` (from stack outputs) |
   | HTTP method | `POST` |
   | HTTP content type | `application/json` |
   | Secret | Same value as `WebhookSecret` parameter |

2. Go to **Operations &rarr; Event Rules** and create a new Event Rule:

   | Field | Value |
   |-------|-------|
   | Name | `Send notification on ready` |
   | Object types | `Notices > Prepared notification` |
   | Events | `Object updated` |
   | Conditions | `{"and": [{"attr": "status.value", "value": "ready"}]}` |
   | Action type | `Webhook` |
   | Action | `SES Outbound Delivery` |

When a PreparedNotification transitions to `ready`, NetBox fires the webhook. The Lambda validates the `X-Hook-Signature` (HMAC-SHA512), fetches the full notification from NetBox, and sends it via SES immediately.

### Security

The webhook endpoint validates every request using NetBox's built-in HMAC-SHA512 signature:

1. NetBox computes `HMAC-SHA512(secret, request_body)` and sends it in the `X-Hook-Signature` header
2. The Lambda recomputes the HMAC with the same secret and uses constant-time comparison
3. Requests with invalid or missing signatures are rejected with HTTP 403

### How It Works

```
NetBox Event Rule                    API Gateway              Outbound Lambda
     │                                   │                        │
     │ PreparedNotification              │                        │
     │ status → "ready"                  │                        │
     │                                   │                        │
     ├──── POST /webhook/outbound ──────►│                        │
     │     X-Hook-Signature: hmac...     ├───── invoke ──────────►│
     │     {event, model, data...}       │                        │
     │                                   │         ┌──────────────┤
     │                                   │         │ 1. Verify    │
     │                                   │         │    signature │
     │                                   │         │ 2. Fetch     │
     │                                   │         │    full      │
     │                                   │         │    notif.    │
     │                                   │         │ 3. Send SES  │
     │                                   │         │ 4. PATCH     │
     │                                   │         │    → "sent"  │
     │                                   │         └──────────────┤
     │                                   │◄──── 200 OK ───────────┤
```

## VPC Deployment

By default, Lambda functions run outside a VPC and access NetBox over the public internet. If NetBox is on a private network, deploy the Lambdas into a VPC with connectivity to it.

### When you need VPC

- NetBox is behind a firewall, VPN, or private subnet
- You need a predictable source IP to allowlist (via NAT Gateway Elastic IP)
- Security policy requires all traffic to stay within the AWS network

### Network requirements

Lambda functions in a VPC need **outbound internet access** for:

- **NetBox API** (HTTPS) — all three functions
- **AWS SES API** (HTTPS) — outbound function (`ses:SendRawEmail`)
- **AWS S3 API** (HTTPS) — inbound function (fetch raw email)

This requires either:

1. **NAT Gateway** in a public subnet (most common) — gives Lambda internet access and a static Elastic IP
2. **VPC Endpoints** for S3 and SES (avoids NAT for AWS services, but still need NAT or direct connectivity for NetBox if it's external)

### Setup

1. Create or identify **private subnets** with a route to a NAT Gateway
2. Create a **security group** that allows outbound HTTPS (port 443)
3. Deploy with VPC parameters:

```bash
sam deploy --parameter-overrides \
  VpcSubnetIds=subnet-aaa,subnet-bbb \
  VpcSecurityGroupIds=sg-xxx ...
```

SAM automatically attaches the `AWSLambdaVPCAccessExecutionRole` managed policy (ENI permissions) when VPC config is present.

### Static IP for firewall allowlisting

When Lambda runs in a VPC with a NAT Gateway, all outbound traffic exits through the NAT Gateway's Elastic IP. Allowlist that IP on your firewall to grant Lambda access to NetBox:

```bash
# Find your NAT Gateway's Elastic IP
aws ec2 describe-nat-gateways --filter Name=subnet-id,Values=subnet-public \
  --query 'NatGateways[].NatGatewayAddresses[].PublicIp'
```

## Email Authentication

For outbound emails to be delivered reliably and not marked as spam, configure these DNS records for your sending domain.

### SPF (Sender Policy Framework)

SPF tells receiving mail servers that SES is authorized to send on behalf of your domain. Add a TXT record:

```
v=spf1 include:amazonses.com ~all
```

If you already have an SPF record, add `include:amazonses.com` to it.

### DKIM (DomainKeys Identified Mail)

DKIM cryptographically signs emails so recipients can verify they haven't been tampered with. SES provides Easy DKIM:

1. Go to **SES &rarr; Verified identities &rarr; your domain**
2. Under **Authentication**, select **Easy DKIM**
3. SES generates three CNAME records — add them to your DNS:

```
selector1._domainkey.example.com  CNAME  selector1.dkim.amazonses.com
selector2._domainkey.example.com  CNAME  selector2.dkim.amazonses.com
selector3._domainkey.example.com  CNAME  selector3.dkim.amazonses.com
```

Once DNS propagates, SES automatically signs all outbound emails.

### DMARC (Domain-based Message Authentication, Reporting & Conformance)

DMARC builds on SPF and DKIM to tell receivers what to do with messages that fail authentication. Add a TXT record:

```
_dmarc.example.com  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@example.com"
```

| Policy | Meaning |
|--------|---------|
| `p=none` | Monitor only (start here) |
| `p=quarantine` | Send failures to spam |
| `p=reject` | Reject failures outright |

Start with `p=none` to collect reports, then tighten to `quarantine` or `reject` once you've confirmed everything is working.

### Custom MAIL FROM domain (optional)

By default, SES uses `amazonses.com` as the MAIL FROM domain. For full SPF alignment (required for strict DMARC), configure a custom MAIL FROM:

1. Go to **SES &rarr; Verified identities &rarr; your domain &rarr; Custom MAIL FROM domain**
2. Set it to a subdomain (e.g. `mail.example.com`)
3. Add the MX and TXT records SES provides:

```
mail.example.com  MX   10 feedback-smtp.us-east-1.amazonses.com
mail.example.com  TXT  "v=spf1 include:amazonses.com ~all"
```

### Inbound MX records

For the inbound flow (receiving provider maintenance emails), point your receipt domain's MX record to SES:

```
notices.example.com  MX  10 inbound-smtp.us-east-1.amazonaws.com
```

Use the correct regional endpoint for your SES region.

## Customization

### Multiple Recipients per Notification

Each PreparedNotification can have multiple recipients. The outbound Lambda sends a single email with all recipients in the `To:` header. For individual emails per recipient, modify `_build_mime()` to iterate over recipients.

### HTML Styling

The outbound Lambda inlines CSS from the notification's `css` field into a `<style>` tag in the HTML `<head>`. For more aggressive CSS inlining (into element `style` attributes), consider adding a library like `premailer`.

## Troubleshooting

### Outbound Lambda sends but status not updated

Check CloudWatch Logs for the outbound Lambda. Common causes:
- NetBox API token doesn't have write permission
- NetBox URL is not reachable from Lambda (check VPC/security groups)

### Tracking events not arriving

1. Verify the SES Configuration Set is attached to outbound emails (check `SES_CONFIGURATION_SET` env var)
2. Verify the SNS topic policy allows SES to publish
3. Check that the Lambda has an SNS trigger subscription

### Inbound emails not parsed

1. Check S3 bucket for the raw email (SES should store it)
2. Check CloudWatch Logs for the inbound Lambda
3. Verify the sender matches a provider in the provider map
4. Ensure the email format is supported by `circuit-maintenance-parser`

### SES sending in sandbox

New SES accounts start in sandbox mode (can only send to verified addresses). Request production access in the SES console.

### Permission errors

Ensure the NetBox API token has permission to:
- Read/write `notices.maintenance`, `notices.impact`, `notices.eventnotification`
- Read/write `notices.preparednotification`
- Create `extras.journalentry`
