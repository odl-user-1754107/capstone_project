echo "Starting automated code push to GitHub..."
git config --global --add safe.directory C:/LabFiles/Capstone-Project/src/ui
git config --global user.email "odl_user_1754107@sandboxailabs1012.onmicrosoft.com"
git config --global user.name "odl_user_1754107"

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "Error: Not a git repository. Please initialize git first."
    exit 1
fi

git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "No changes to commit."
    exit 0
fi

# Commit
echo "Committing changes..."
COMMIT_MESSAGE="Automated commit: Updated web application - $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MESSAGE"

# Push to the main branch 
echo "Pushing to remote repository..."
CURRENT_BRANCH=$(git branch --show-current)
git push https://github.com/odl-user-1754107/capstone_project.git "$CURRENT_BRANCH"

echo "Successfully pushed changes to GitHub!"
echo "Commit message: $COMMIT_MESSAGE"
echo "Branch: $CURRENT_BRANCH"