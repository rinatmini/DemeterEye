# DEPLOY


gcloud run deploy demetereye-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 512Mi --cpu 1 \
  --port 8080 \
  --set-env-vars MONGO_DB=demetereye \
  --set-secrets MONGO_URI=MONGO_URI:latest,JWT_SECRET=JWT_SECRET:latest
