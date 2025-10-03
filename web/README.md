# DEPLOY


gcloud run deploy demetereye-web \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 256Mi --cpu 1 \
  --port 8080