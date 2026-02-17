# PowerShell Script to Deploy to Hugging Face Spaces
# Run this from the HF Space directory

param(
    [string]$SourcePath = "C:\DataScience_AI_folder\Portfolio\web_scrapper"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deploying to Hugging Face Spaces" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path ".git")) {
    Write-Host "[ERROR] Not in a git repository. Please run this from your HF Space directory." -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] Copying main app file..." -ForegroundColor Yellow
Copy-Item "$SourcePath\huggingface_app.py" -Destination "app.py" -Force
Write-Host "  ✓ app.py created" -ForegroundColor Green

Write-Host "[2/6] Copying video_engine folder..." -ForegroundColor Yellow
if (Test-Path "video_engine") {
    Remove-Item "video_engine" -Recurse -Force
}
Copy-Item "$SourcePath\video_engine" -Destination "video_engine" -Recurse -Force
Write-Host "  ✓ video_engine/ copied" -ForegroundColor Green

Write-Host "[3/6] Copying requirements.txt..." -ForegroundColor Yellow
Copy-Item "$SourcePath\requirements_hf.txt" -Destination "requirements.txt" -Force
Write-Host "  ✓ requirements.txt created" -ForegroundColor Green

Write-Host "[4/6] Copying packages.txt..." -ForegroundColor Yellow
Copy-Item "$SourcePath\packages.txt" -Destination "packages.txt" -Force
Write-Host "  ✓ packages.txt created" -ForegroundColor Green

Write-Host "[5/6] Copying README.md..." -ForegroundColor Yellow
Copy-Item "$SourcePath\README_SPACES.md" -Destination "README.md" -Force
Write-Host "  ✓ README.md created" -ForegroundColor Green

Write-Host "[6/6] Creating .gitignore..." -ForegroundColor Yellow
@"
__pycache__/
*.py[cod]
*.db
*.db-wal
*.db-shm
*.log
temp_storage/
.env
"@ | Out-File -FilePath ".gitignore" -Encoding utf8 -Force
Write-Host "  ✓ .gitignore created" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Files copied successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Add secrets in HF Space settings:" -ForegroundColor White
Write-Host "   - BUNNY_API_KEY" -ForegroundColor Gray
Write-Host "   - BUNNY_LIBRARY_ID" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Commit and push:" -ForegroundColor White
Write-Host "   git add ." -ForegroundColor Gray
Write-Host "   git commit -m 'Deploy video scraper'" -ForegroundColor Gray
Write-Host "   git push" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Wait for HF Spaces to build (check Logs tab)" -ForegroundColor White
Write-Host ""
