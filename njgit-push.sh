#!/bin/bash

if [[ $(whoami) != "njobvu" ]]; then
  echo "This script is only for user: njobvu"
  exit 1
fi

read -p "GitHub repo name: " REPO
read -p "Commit message: " MSG

git init
git add .
git commit -m "$MSG"
git branch -M main
git remote add origin https://github.com/njobvulabs/$REPO
git fetch origin
git merge origin/main --allow-unrelated-histories --no-edit
git push -u origin main
