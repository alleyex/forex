Set-Location "C:\git_repos\forex"
$env:QT_OPENGL = "software"
$env:LOG_LEVEL = "INFO"
$env:TOKEN_FILE = "C:\git_repos\forex\token.json"

& "C:\git_repos\forex\.venv311\Scripts\python.exe" -m forex.app.cli.live
