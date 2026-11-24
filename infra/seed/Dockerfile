# One-off data load for the private Azure database (run as the amlens-seed Container Apps job,
# which sits inside the VNet). Build after `bash infra/seed/make-seed.sh`:
#   az acr build -r <acr> -t amlens-seed:<tag> infra/seed
FROM postgres:16-alpine
COPY seed.sql /seed.sql
COPY load.sh /load.sh
USER postgres
CMD ["sh", "/load.sh"]
