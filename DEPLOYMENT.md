# AWS deployment (office account)

Deployed and verified live -- not just written. See `MIGRATION_NOTES.md`
for what was verified about the app itself; this covers the AWS side.

## Live URL

**http://pcrf-fms-alb-45409179.us-east-1.elb.amazonaws.com**

Plain HTTP for now (see "Known gaps" below) -- `AibasedDatafraudDetection.com`
was the intended domain but has no Route 53 hosted zone in this AWS
account yet, so DNS + HTTPS were deferred rather than block the deploy.

## What was actually verified after deploying

- `GET /api/health` -> `{"status":"ok"}`
- `GET /api/kpis` returns real numbers from the migrated data
  (501,118 subscribers, 546,030 `subscribers_daily` rows -- row count
  matched exactly between local Postgres and RDS after `pg_restore`).
- `GET /api/demask/encryption/methods` -> `demo_cipher`, `aes_token`,
  `fernet` all registered, `configured: true` (proves the SSM-sourced
  `ENCRYPTION_KEY` made it into the running container).
- `/dashboard` and `/dashboard/demask` both return the built SPA
  (`200`, `text/html`) through the same container's SPA fallback route.
- ECS service `pcrf-fms-service` reached steady state, 1/1 tasks
  running, ALB target group reports the task `healthy`.

## Resources created (account 486872284508, region us-east-1)

| Resource | Name / ID |
|---|---|
| VPC | `vpc-0ab55b3b45f43395d` (account's existing default VPC -- not created by this deploy) |
| ECR repo | `pcrf-fms` -- `486872284508.dkr.ecr.us-east-1.amazonaws.com/pcrf-fms` |
| RDS instance | `pcrf-fms-db` (Postgres 16.15, `db.t3.micro`, single-AZ, **not publicly accessible**) |
| RDS subnet group | `pcrf-fms-db-subnets` |
| Security groups | `pcrf-fms-alb-sg` (`sg-0c6a739e6abbedb4a`), `pcrf-fms-ecs-sg` (`sg-07850bc6d6704dc9d`), `pcrf-fms-rds-sg` (`sg-0aaa1627341904a7a`) |
| ECS cluster | `pcrf-fms-cluster` (EC2-backed) |
| ECS capacity provider | `pcrf-fms-cp` (wraps the ASG, managed scaling) |
| Auto Scaling Group | `pcrf-fms-asg` (min=max=desired=1, `t3.medium`) |
| Launch template | `pcrf-fms-lt` |
| ECS task definition | `pcrf-fms` (currently revision 1) |
| ECS service | `pcrf-fms-service` |
| ALB | `pcrf-fms-alb` |
| ALB target group | `pcrf-fms-tg` (health check `/api/health`) |
| IAM roles | `pcrf-fms-ecs-instance-role` (+ instance profile of the same name), `pcrf-fms-ecs-execution-role` (has an inline `pcrf-fms-ssm-read` policy scoped to `/pcrf-fms/*`), `pcrf-fms-ecs-task-role` (currently empty -- add S3/SES permissions here if those features get turned on) |
| SSM parameters | `/pcrf-fms/DATABASE_URL`, `/pcrf-fms/ENCRYPTION_KEY` (both `SecureString`), `/pcrf-fms/ENCRYPTION_PROVIDER`, `/pcrf-fms/ALLOWED_ORIGINS` (both `String`) |
| CloudWatch log group | `/ecs/pcrf-fms` |

## Redeploying after a code change

```bash
bash deploy/redeploy.sh
```

Builds the image, pushes a new tag to ECR, registers a new task
definition revision, and forces a new ECS deployment.

## Known gaps -- fix before treating this as production-ready

1. **No domain / no HTTPS.** The app is served over plain HTTP at the
   ALB's own DNS name. To add `AibasedDatafraudDetection.com`: create
   a Route 53 hosted zone for it in this account, point the domain's
   registrar nameservers at that zone's 4 NS records, request an ACM
   cert (DNS-validated), add an HTTPS listener on the ALB, redirect
   HTTP->HTTPS, and update `/pcrf-fms/ALLOWED_ORIGINS` in SSM to the
   `https://` URL.

2. **The app has zero authentication, and it's open to the entire
   internet.** This was an explicit, discussed decision to move fast,
   not an oversight -- the ALB security group (`pcrf-fms-alb-sg`)
   allows `0.0.0.0/0` on 80/443, and there is no login anywhere in
   `backend/app` or `frontend/src`. The Demask page can reverse real
   subscriber ID masking. **Close this soon** -- options, cheapest to
   most work: (a) restrict `pcrf-fms-alb-sg` to your office IP/VPN
   CIDR, (b) add HTTP Basic Auth at the ALB listener, (c) add real
   app-level auth (e.g. Cognito, or a login page + session/JWT
   middleware in FastAPI).

3. **S3 ingestion and SES daily-report email are not configured** --
   `INGEST_S3_BUCKET` and the SES vars were intentionally left unset
   (confirmed safe: the ingest poller no-ops with an empty bucket, and
   the report scheduler catches and logs failures rather than
   crashing). Add an S3 bucket + `pcrf-fms-ecs-task-role` permissions
   for it, and verify an SES sender identity, if/when those features
   are needed.

4. **Single instance, no redundancy.** ASG is min=max=desired=1 and
   RDS is single-AZ. Fine for a first deploy; revisit
   (Multi-AZ RDS, ASG size >1) once this is truly relied on.

5. **`db.t3.micro` / `t3.medium` sizing is a starting guess**, not
   load-tested. Watch CloudWatch metrics and resize
   (`aws rds modify-db-instance` / update the launch template +
   refresh the ASG) if needed.
