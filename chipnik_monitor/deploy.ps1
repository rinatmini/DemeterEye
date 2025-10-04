gcloud run deploy demetereye-monitor `
  --source . `
  --region us-central1 `
  --allow-unauthenticated `
  --min-instances 0 --max-instances 2 `
  --memory 512Mi --cpu 1 `
  --port 8080