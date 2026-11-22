$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$repo = 'snapp1k/family-tutor-bot'
foreach ($cmd in @('git', 'gh', 'python')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Не найдена команда $cmd. Установите Git, GitHub CLI и Python."
    }
}
& gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Сначала войдите в GitHub: gh auth login' }
$login = (& gh api user --jq '.login').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Не удалось определить GitHub аккаунт.' }
if ($login.ToLowerInvariant() -ne 'snapp1k') {
    throw "Вход выполнен как $login, требуется snapp1k. Публикация остановлена."
}
& gh repo view $repo *> $null
if ($LASTEXITCODE -eq 0) {
    throw "Репозиторий $repo уже существует. Скрипт не перезаписывает его."
}
if (-not (Test-Path '.git')) {
    & git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'git init не выполнен.' }
}
$githubId = (& gh api user --jq '.id').Trim()
& git config --local user.name $login
& git config --local user.email ("{0}+{1}@users.noreply.github.com" -f $githubId, $login)
& git add .
if ($LASTEXITCODE -ne 0) { throw 'git add не выполнен.' }
& python scripts/check_release.py
if ($LASTEXITCODE -ne 0) { throw 'Обнаружена проблема безопасности в git index.' }
& git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    & git commit -m 'Initial Family Tutor Bot release'
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось сделать коммит.' }
}
Write-Host 'Создаём ПУБЛИЧНЫЙ репозиторий и загружаем код...'
& gh repo create $repo --public --source=. --remote=origin --push --description 'Telegram family tutor with parent oversight and Ubuntu deployment'
if ($LASTEXITCODE -ne 0) { throw 'Создание или отправка репозитория завершились ошибкой.' }
Write-Host "Готово: https://github.com/$repo"
