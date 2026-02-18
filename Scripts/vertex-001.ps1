$PROJECT_ID = (gcloud config get-value project).Trim()
$APP_SA     = "smeops-api-sa@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects get-iam-policy $PROJECT_ID `
  --flatten="bindings[].members" `
  --format="table(bindings.role, bindings.members)" `
  --filter "bindings.members:serviceAccount:$APP_SA"

