# Deploying PM Strategy Copilot to Azure App Service

## Architecture

```
Azure App Service (Linux, Python 3.11, Code)
├── /home/site/wwwroot/        ← app code (deployed via GitHub Actions)
├── /home/pm_agent_data/       ← persistent JSON data (survives redeploys)
└── /home/pm_agent_inbox/      ← persistent inbox uploads
```

The app auto-detects Azure via the `WEBSITE_SITE_NAME` env variable (set automatically by Azure) and redirects `DATA_DIR` and `INBOX_DIR` to the persistent `/home` mount.

---

## Manual Steps

### 1. Create the App Service (Portal)

1. Go to **Azure Portal → Create a resource → Web App**
2. Fill in:
   | Setting | Value |
   |---------|-------|
   | **Subscription** | your subscription |
   | **Resource Group** | create new or pick existing |
   | **Name** | `pm-strategy-copilot` (globally unique) |
   | **Publish** | **Code** |
   | **Runtime stack** | **Python 3.11** |
   | **Operating System** | **Linux** |
   | **Region** | your nearest region |
   | **App Service Plan** | **B1** or higher (Free/F1 may time out on Streamlit) |
3. Click **Review + Create → Create**

### 2. Configure Environment Variables (Portal)

1. Go to **App Service → Settings → Environment variables**
2. Add the following:

   | Name | Value |
   |------|-------|
   | `OPENAI_API_KEY` | your Azure OpenAI API key |
   | `AZURE_OPENAI_ENDPOINT` | `https://<resource>.openai.azure.com/` |
   | `AZURE_OPENAI_DEPLOYMENT` | your deployment name (e.g. `gpt-5-mini`) |
   | `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` |
   | `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

3. Click **Apply**

### 3. Set Startup Command (CLI — one time)

Run this from your terminal (not the portal):

```bash
az login

az webapp config set \
  --name pm-strategy-copilot \
  --resource-group <your-resource-group> \
  --startup-file "bash startup.sh"
```

### 4. Set Up GitHub Actions (CI/CD)

1. In **Azure Portal → App Service → Overview**, click **Download publish profile**
2. In your **GitHub repo → Settings → Secrets and variables → Actions**, create:
   - `AZURE_WEBAPP_PUBLISH_PROFILE` — paste the downloaded XML content
3. Edit `.github/workflows/azure-deploy.yml`:
   - Set `APP_NAME` to your App Service name
   - Set `RESOURCE_GROUP` to your resource group name
4. Push to `main` — the workflow deploys automatically

### 5. Verify

1. Browse to `https://pm-strategy-copilot.azurewebsites.net`
2. The Streamlit app should load within 30–60 seconds on first deploy
3. If you see errors, check logs:
   ```bash
   az webapp log tail --name pm-strategy-copilot --resource-group <your-rg>
   ```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **"Application Error"** after deploy | Verify startup command was set via CLI. Check logs with `az webapp log tail`. |
| **Timeout / 502** | Upgrade plan to B1+. Free tier is too slow for Streamlit. |
| **Dependencies not found** | Ensure `SCM_DO_BUILD_DURING_DEPLOYMENT=true` in env vars. |
| **Data lost after redeploy** | Data is in `/home/pm_agent_data/` — verify it exists via SSH. |
| **OpenAI errors** | Confirm `OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` are set in Environment variables. |

## Persistent Storage Note

On Azure App Service Linux, the `/home` directory is backed by Azure Storage and persists across restarts and redeployments. Your JSON data files (requests, insights, day plans, etc.) are stored under `/home/pm_agent_data/` automatically when running on Azure.

**Backup recommendation:**
```bash
az webapp ssh --name pm-strategy-copilot --resource-group <rg>
# then: tar czf /tmp/backup.tar.gz /home/pm_agent_data/
```
