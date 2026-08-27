# Facelift Ops Kit

## Daily backup (run via Task Scheduler, 21:00)
Copies DB + run reports + briefs into timestamped backup folder.

powershell -ExecutionPolicy Bypass -File "%~dp0backup.py"

## Register scheduled tasks (run once as admin)
schtasks /Create /TN "Facelift-Watch"     /TR "python C:\Users\Raja\facelift\watch_cron.py" /SC HOURLY /ST 09:00
schtasks /Create /TN "Facelift-Backup"   /TR "powershell -File C:\Users\Raja\facelift\ops\backup.ps1" /SC DAILY /ST 21:00
schtasks /Create /TN "Facelift-Monthly-Audit" /TR "python C:\Users\Raja\facelift\care_cron.py" /SC MONTHLY /D 1 /ST 08:00
