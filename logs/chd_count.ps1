$files = Get-ChildItem 'C:\teste\*.chd'
$sum = ($files | Measure-Object Length -Sum).Sum
Write-Output ("CHDs: " + $files.Count + " | Total: " + [math]::Round($sum/1GB,1) + " GB")
